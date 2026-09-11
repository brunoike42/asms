from django.contrib import admin

from .models import Network, NetworkAdminRole, NetworkDailyMetric, NetworkMembership, NetworkQueryLog


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "country", "status", "created_at")
    list_filter = ("type", "status", "country")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(NetworkAdminRole)
class NetworkAdminRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "network", "is_active", "invited_at")
    list_filter = ("is_active", "network")
    autocomplete_fields = ("user", "network")


@admin.register(NetworkMembership)
class NetworkMembershipAdmin(admin.ModelAdmin):
    list_display = ("tenant", "network", "joined_at", "left_at")
    list_filter = ("network",)
    autocomplete_fields = ("tenant", "network")


@admin.register(NetworkDailyMetric)
class NetworkDailyMetricAdmin(admin.ModelAdmin):
    list_display = ("network", "tenant", "date", "metric", "value")
    list_filter = ("network", "metric")
    readonly_fields = ("network", "tenant", "date", "metric", "value", "computed_at")

    def has_add_permission(self, request):
        return False  # written exclusively by tasks.compute_network_rollups

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(NetworkQueryLog)
class NetworkQueryLogAdmin(admin.ModelAdmin):
    list_display = ("user", "network", "model_label", "created_at")
    list_filter = ("network", "model_label")
    readonly_fields = ("network", "user", "model_label", "tenant_ids", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
