# -*- coding: utf-8 -*-
"""
Patch script — apps/visitor/admin.py
Registers VisitorWatchlistEntry in Django admin.

Run AFTER patch_visitor_models.py and AFTER makemigrations/migrate:
    py patch_visitor_admin.py
    py -m py_compile apps\visitor\admin.py
"""
import pathlib

TARGET = pathlib.Path("apps/visitor/admin.py")

ANCHOR_IMPORT = "from .models import Visitor, ExpectedVisitor, VisitorLog"
NEW_IMPORT = "from .models import Visitor, ExpectedVisitor, VisitorLog, VisitorWatchlistEntry"

ANCHOR_END = '''    def duration_minutes(self, obj):
        mins = obj.duration_minutes
        return f"{mins} min" if mins is not None else "On-site"
    duration_minutes.short_description = "Duration"'''

NEW_ADMIN = '''


@admin.register(VisitorWatchlistEntry)
class VisitorWatchlistEntryAdmin(admin.ModelAdmin):
    list_display  = ("full_name", "reason", "related_student", "is_active", "added_by")
    list_filter   = ("reason", "is_active")
    search_fields = ("full_name", "phone", "related_student__first_name", "related_student__last_name")'''


def main():
    with open(TARGET, "r", encoding="utf-8", newline="") as f:
        text = f.read()

    assert ANCHOR_IMPORT in text, "Import line doesn't match — stopping without writing anything."
    assert ANCHOR_END in text, "VisitorLogAdmin.duration_minutes doesn't match — stopping without writing anything."
    assert "VisitorWatchlistEntryAdmin" not in text, "Already patched?"

    text = text.replace(ANCHOR_IMPORT, NEW_IMPORT)
    text = text.replace(ANCHOR_END, ANCHOR_END + NEW_ADMIN)

    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"Patched {TARGET} — registered VisitorWatchlistEntry.")


if __name__ == "__main__":
    main()
