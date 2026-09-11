"""
ASMS Visitor Management Module
Reusable visitor identity records, per-visit entry/exit log,
expected-visitor pre-registration, and muster list for emergency evacuation.
Benchmarked from: Raptor Technologies (40,000+ US K-12 schools) and iSign-In —
both use a two-table architecture: a reusable Visitor identity record
(deduplicates repeat visitors) and a per-visit VisitorLog.
ExpectedVisitor adds the parent-portal pre-registration feature (Spec Section 10).
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TenantModel, TenantManager
# ══════════════════════════════════════════════════════
# VISITOR IDENTITY
# ══════════════════════════════════════════════════════
class Visitor(TenantModel):
    """
    Reusable identity record — one per person, not one per visit.
    Repeat visitors are looked up by ID number so their history accumulates
    rather than creating duplicate records each time they arrive.
    """
    class IDTypeChoices(models.TextChoices):
        NIN      = "nin",      "National ID (NIN)"
        PASSPORT = "passport", "Passport"
        DL       = "dl",       "Drivers Licence"
        OTHER    = "other",    "Other"
    full_name     = models.CharField(max_length=200)
    id_type       = models.CharField(max_length=10, choices=IDTypeChoices.choices,
                                      default=IDTypeChoices.NIN)
    id_number     = models.CharField(max_length=50, blank=True)
    phone         = models.CharField(max_length=20, blank=True)
    photo         = models.ImageField(
        upload_to="visitors/photos/", null=True, blank=True,
        help_text="Captured at first check-in — printed on the visitor badge"
    )
    id_scan_raw   = models.TextField(
        blank=True,
        help_text="Raw decoded MRZ/barcode payload from a camera-based ID scan, kept for "
                   "audit and re-parsing — full_name/id_number above are the parsed fields"
    )
    is_flagged    = models.BooleanField(
        default=False,
        help_text="Flagged visitors trigger an alert at reception — do not allow entry without principal approval"
    )
    flag_reason   = models.TextField(blank=True)
    flag_added_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="visitors_flagged"
    )
    notes         = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table     = "visitor_visitor"
        ordering     = ["full_name"]
        verbose_name = "Visitor"
    def __str__(self):
        id_str = f"{self.get_id_type_display()}: {self.id_number}" if self.id_number else "No ID on record"
        return f"{self.full_name} ({id_str})"
    @property
    def visit_count(self):
        return self.visit_logs.count()
# ══════════════════════════════════════════════════════
# EXPECTED VISITOR (PRE-REGISTRATION)
# ══════════════════════════════════════════════════════
class ExpectedVisitor(TenantModel):
    """
    Pre-registered visitor — lets parents/staff announce a visit before arrival.
    Receptionist checks this list when the visitor arrives and links it to the
    VisitorLog. Exposed on the parent portal per Spec Section 10.
    """
    class StatusChoices(models.TextChoices):
        PENDING   = "pending",   "Expected"
        ARRIVED   = "arrived",   "Arrived"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW   = "no_show",   "No Show"
    registered_by      = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True,
        related_name="expected_visitors_registered"
    )
    visitor_name       = models.CharField(max_length=200)
    visitor_phone      = models.CharField(max_length=20, blank=True)
    visitor_id_number  = models.CharField(max_length=50, blank=True)
    expected_date      = models.DateField()
    expected_time_from = models.TimeField(null=True, blank=True)
    expected_time_to   = models.TimeField(null=True, blank=True)
    purpose            = models.CharField(max_length=255, blank=True)
    student            = models.ForeignKey(
        "students.Student", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="expected_visitors",
        help_text="Set when a parent pre-registers a visit to see their child"
    )
    status             = models.CharField(max_length=10, choices=StatusChoices.choices,
                                           default=StatusChoices.PENDING)
    notes              = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table     = "visitor_expected_visitor"
        ordering     = ["expected_date", "expected_time_from"]
        verbose_name = "Expected Visitor"
    def __str__(self):
        return f"{self.visitor_name} — {self.expected_date} ({self.get_status_display()})"
    @property
    def is_today(self):
        return self.expected_date == timezone.now().date()
# ══════════════════════════════════════════════════════
# VISIT LOG
# ══════════════════════════════════════════════════════
class VisitorLog(TenantModel):
    """
    One record per visit — created at check-in, updated at check-out.
    badge_number is auto-generated on first save (format: VB-YYYYMMDD-NNN)
    and never changes, matching the physical badge printed at reception.
    Status auto-advances to checked_out when check_out_time is set.
    """
    class PurposeChoices(models.TextChoices):
        PARENT_VISIT = "parent_visit", "Parent / Guardian Visit"
        DELIVERY     = "delivery",     "Delivery"
        CONTRACTOR   = "contractor",   "Contractor / Maintenance"
        INTERVIEW    = "interview",    "Interview / Recruitment"
        OFFICIAL     = "official",     "Official / Government"
        VENDOR       = "vendor",       "Vendor"
        OTHER        = "other",        "Other"
    class StatusChoices(models.TextChoices):
        CHECKED_IN  = "checked_in",  "Currently On-Site"
        CHECKED_OUT = "checked_out", "Checked Out"
        OVERSTAY    = "overstay",    "Overstay Alert"
    visitor              = models.ForeignKey(Visitor, on_delete=models.PROTECT,
                                              related_name="visit_logs")
    purpose              = models.CharField(max_length=15, choices=PurposeChoices.choices)
    host                 = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="visits_hosted",
        help_text="Staff member being visited"
    )
    student              = models.ForeignKey(
        "students.Student", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="visitor_visits",
        help_text="Student being visited — set for parent/guardian visits"
    )
    expected_visitor     = models.ForeignKey(
        ExpectedVisitor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="actual_visits",
        help_text="Linked pre-registration record, if visitor was expected"
    )
    check_in_time        = models.DateTimeField(default=timezone.now)
    check_out_time       = models.DateTimeField(null=True, blank=True)
    badge_number         = models.CharField(max_length=20, blank=True, editable=False)
    items_carried        = models.CharField(
        max_length=255, blank=True,
        help_text="e.g. laptop bag, toolbox, parcels — logged for security"
    )
    vehicle_registration = models.CharField(max_length=20, blank=True)
    status               = models.CharField(max_length=12, choices=StatusChoices.choices,
                                             default=StatusChoices.CHECKED_IN)
    signed_in_by         = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="visitor_logs_signed",
        help_text="Receptionist who processed this entry"
    )
    notes                = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table     = "visitor_log"
        ordering     = ["-check_in_time"]
        verbose_name = "Visitor Log Entry"
    def __str__(self):
        return (f"{self.visitor.full_name} — "
                f"{self.check_in_time:%Y-%m-%d %H:%M} ({self.get_status_display()})")
    def save(self, *args, **kwargs):
        # Auto-generate badge number on first save only
        if not self.badge_number:
            today = timezone.now().date()
            count = VisitorLog.objects.filter(
                tenant=self.tenant, check_in_time__date=today
            ).count() + 1
            self.badge_number = f"VB-{today.strftime('%Y%m%d')}-{count:03d}"
        # Auto-advance status when check_out_time is set
        if self.check_out_time and self.status in (
            self.StatusChoices.CHECKED_IN, self.StatusChoices.OVERSTAY
        ):
            self.status = self.StatusChoices.CHECKED_OUT
        super().save(*args, **kwargs)
        # Mark linked pre-registration as arrived
        if self.expected_visitor_id:
            ExpectedVisitor.objects.filter(
                pk=self.expected_visitor_id,
                status=ExpectedVisitor.StatusChoices.PENDING
            ).update(status=ExpectedVisitor.StatusChoices.ARRIVED)
    @property
    def duration_minutes(self):
        """Minutes on-site — None if still checked in."""
        if self.check_out_time:
            return int((self.check_out_time - self.check_in_time).total_seconds() / 60)
        return None
    def badge_data(self):
        """
        Returns a dict for rendering the Visitor Badge PDF (Document Register #: Visitor Badge).
        Pass this to the WeasyPrint template context.
        """
        return {
            "badge_number":  self.badge_number,
            "visitor_name":  self.visitor.full_name,
            "purpose":       self.get_purpose_display(),
            "host":          str(self.host) if self.host_id else "—",
            "student":       str(self.student) if self.student_id else "—",
            "check_in_time": self.check_in_time.strftime("%d %b %Y %H:%M"),
            "date":          self.check_in_time.strftime("%d %b %Y"),
        }
    @classmethod
    def muster_list(cls, tenant):
        """
        Returns all visitors currently on-site — for emergency evacuation roll calls.
        Usage: VisitorLog.muster_list(request.tenant)
        """
        return cls.objects.filter(tenant=tenant, status=cls.StatusChoices.CHECKED_IN).select_related("visitor")


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

