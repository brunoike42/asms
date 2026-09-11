from django.contrib import admin
from .models import Visitor, ExpectedVisitor, VisitorLog, VisitorWatchlistEntry
@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display  = ("full_name", "id_type", "id_number", "phone", "is_flagged", "visit_count")
    list_filter   = ("id_type", "is_flagged")
    search_fields = ("full_name", "id_number", "phone")
    readonly_fields = ("visit_count",)
    def visit_count(self, obj):
        return obj.visit_count
    visit_count.short_description = "Total Visits"
@admin.register(ExpectedVisitor)
class ExpectedVisitorAdmin(admin.ModelAdmin):
    list_display   = ("visitor_name", "expected_date", "purpose", "student", "status", "is_today")
    list_filter    = ("status", "expected_date")
    search_fields  = ("visitor_name", "visitor_phone", "visitor_id_number")
    date_hierarchy = "expected_date"
    def is_today(self, obj):
        return obj.is_today
    is_today.boolean = True
    is_today.short_description = "Today?"
@admin.register(VisitorLog)
class VisitorLogAdmin(admin.ModelAdmin):
    list_display  = ("visitor", "purpose", "badge_number", "check_in_time",
                     "check_out_time", "duration_minutes", "status", "signed_in_by")
    list_filter   = ("purpose", "status")
    search_fields = ("visitor__full_name", "badge_number", "vehicle_registration")
    readonly_fields = ("badge_number", "duration_minutes")
    date_hierarchy = "check_in_time"
    def duration_minutes(self, obj):
        mins = obj.duration_minutes
        return f"{mins} min" if mins is not None else "On-site"
    duration_minutes.short_description = "Duration"


@admin.register(VisitorWatchlistEntry)
class VisitorWatchlistEntryAdmin(admin.ModelAdmin):
    list_display  = ("full_name", "reason", "related_student", "is_active", "added_by")
    list_filter   = ("reason", "is_active")
    search_fields = ("full_name", "phone", "related_student__first_name", "related_student__last_name")
