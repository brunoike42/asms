from django.contrib import admin

from .models import CurriculumAdoption, CurriculumPublishLog, CurriculumResource


@admin.register(CurriculumResource)
class CurriculumResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "network", "resource_type", "subject", "level", "status", "version", "default_locked")
    list_filter = ("resource_type", "status", "default_locked", "curriculum_source")
    search_fields = ("title", "subject")


@admin.register(CurriculumAdoption)
class CurriculumAdoptionAdmin(admin.ModelAdmin):
    list_display = ("tenant", "resource", "adopted_version", "is_diverged", "diverged_at")
    list_filter = ("is_diverged", "resource")
    autocomplete_fields = ("tenant", "resource")


@admin.register(CurriculumPublishLog)
class CurriculumPublishLogAdmin(admin.ModelAdmin):
    list_display = ("resource", "version", "published_by", "published_at", "synced_count", "skipped_count")
    list_filter = ("resource",)
    readonly_fields = ("resource", "version", "published_by", "published_at", "synced_count", "skipped_count")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
