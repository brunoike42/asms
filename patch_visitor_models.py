# -*- coding: utf-8 -*-
"""
Patch script — apps/visitor/models.py

Adds:
  1. Visitor.photo + Visitor.id_scan_raw fields (photo badge + camera-based
     ID/MRZ scan capture — the parsed name/id_number still land in the
     existing full_name/id_number fields; this just keeps the raw scan
     payload for audit and re-parsing).
  2. New VisitorWatchlistEntry model — structured, optionally student-scoped
     ban/restriction, sitting alongside (not replacing) Visitor.is_flagged.

Run from the project root (E:\DJANGO\ASMS\asms):
    py patch_visitor_models.py
    py -m py_compile apps\visitor\models.py
    py manage.py makemigrations visitor
    py manage.py migrate
"""
import pathlib

TARGET = pathlib.Path("apps/visitor/models.py")

ANCHOR_1 = '''    phone         = models.CharField(max_length=20, blank=True)
    is_flagged    = models.BooleanField('''

REPLACEMENT_1 = '''    phone         = models.CharField(max_length=20, blank=True)
    photo         = models.ImageField(
        upload_to="visitors/photos/", null=True, blank=True,
        help_text="Captured at first check-in — printed on the visitor badge"
    )
    id_scan_raw   = models.TextField(
        blank=True,
        help_text="Raw decoded MRZ/barcode payload from a camera-based ID scan, kept for "
                   "audit and re-parsing — full_name/id_number above are the parsed fields"
    )
    is_flagged    = models.BooleanField('''

ANCHOR_2 = '''    @classmethod
    def muster_list(cls, tenant):
        """
        Returns all visitors currently on-site — for emergency evacuation roll calls.
        Usage: VisitorLog.muster_list(request.tenant)
        """
        return cls.objects.filter(tenant=tenant, status=cls.StatusChoices.CHECKED_IN).select_related("visitor")'''

NEW_MODEL = '''


# ══════════════════════════════════════════════════════
# WATCHLIST — Custody Disputes & Banned Visitors
# ══════════════════════════════════════════════════════
class VisitorWatchlistEntry(TenantModel):
    """
    Sharper-scoped alternative to Visitor.is_flagged, for restrictions that
    need a reason and, sometimes, a specific student relationship — e.g. a
    non-custodial parent restricted from picking up one particular child.
    Does not replace Visitor.is_flagged (a general ban on a known identity
    record); this is for restrictions that may predate any visit at all,
    or that are relationship-specific rather than person-general.
    Checked at check-in by name/phone in addition to Visitor.is_flagged —
    that lookup lives in the check-in view (Phase B).
    """
    class ReasonChoices(models.TextChoices):
        CUSTODY_DISPUTE = "custody_dispute", "Custody Dispute / Court Order"
        EXPELLED_STAFF  = "expelled_staff",  "Former Staff — Dismissed"
        SECURITY_THREAT = "security_threat", "Security Threat"
        OTHER           = "other",           "Other"

    full_name       = models.CharField(max_length=200)
    phone           = models.CharField(max_length=20, blank=True)
    reason          = models.CharField(max_length=20, choices=ReasonChoices.choices,
                                        default=ReasonChoices.OTHER)
    reason_detail   = models.TextField(blank=True)
    related_student = models.ForeignKey(
        "students.Student", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="visitor_watchlist_entries",
        help_text="Set when the restriction applies to one specific child only "
                   "(e.g. a custody order) — leave blank for a school-wide ban"
    )
    added_by  = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="watchlist_entries_added"
    )
    is_active = models.BooleanField(default=True)

    objects = TenantManager()

    class Meta:
        db_table     = "visitor_watchlist_entry"
        ordering     = ["full_name"]
        verbose_name = "Visitor Watchlist Entry"
        verbose_name_plural = "Visitor Watchlist Entries"

    def __str__(self):
        scope = f" — re: {self.related_student}" if self.related_student_id else " — school-wide"
        return f"{self.full_name} ({self.get_reason_display()}){scope}"
'''


def main():
    # newline="" disables universal-newline translation on both ends, so
    # whatever line endings are already in the file (this one is LF
    # throughout except a trailing CRLF on the very last line) are
    # preserved byte-for-byte instead of being silently normalized.
    with open(TARGET, "r", encoding="utf-8", newline="") as f:
        text = f.read()

    assert ANCHOR_1 in text, (
        "ANCHOR_1 not found in apps/visitor/models.py — the Visitor model's "
        "phone/is_flagged fields don't match what this patch expects. "
        "Stopping without writing anything."
    )
    assert ANCHOR_2 in text, (
        "ANCHOR_2 not found — the muster_list() method doesn't match what "
        "this patch expects. Stopping without writing anything."
    )
    assert "class VisitorWatchlistEntry" not in text, (
        "VisitorWatchlistEntry already exists in this file — patch already applied?"
    )

    text = text.replace(ANCHOR_1, REPLACEMENT_1)
    text = text.replace(ANCHOR_2, ANCHOR_2 + NEW_MODEL)

    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"Patched {TARGET} — added Visitor.photo/id_scan_raw and VisitorWatchlistEntry.")


if __name__ == "__main__":
    main()
