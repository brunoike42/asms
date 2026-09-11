from rest_framework import serializers

from .models import Network, NetworkAdminRole, NetworkDailyMetric, NetworkQueryLog


class NetworkSerializer(serializers.ModelSerializer):
    school_count = serializers.SerializerMethodField()

    class Meta:
        model = Network
        fields = ["id", "name", "slug", "type", "country", "status", "school_count", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_school_count(self, obj):
        return obj.tenants.count()


class MemberSchoolSerializer(serializers.Serializer):
    """
    Deliberately a plain Serializer, not a ModelSerializer against the real
    Tenant model — I don't have its full field list. Exposes only what
    Appendix C already documents as Tenant's own fields, so this needs no
    changes regardless of what else is on your real Tenant model.
    """

    id = serializers.IntegerField()
    name = serializers.CharField()
    subdomain = serializers.CharField()
    status = serializers.CharField()


class AddSchoolSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField()


class NetworkAdminRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkAdminRole
        fields = ["id", "network", "user", "is_active", "invited_at"]
        read_only_fields = ["id", "invited_at"]


class NetworkQueryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkQueryLog
        fields = ["id", "network", "user", "model_label", "tenant_ids", "created_at"]
        read_only_fields = fields


class NetworkDailyMetricSerializer(serializers.ModelSerializer):
    # None when this row is the network-wide total — see the field's own
    # help_text on the model for why null carries that meaning here.
    school = serializers.SerializerMethodField()

    class Meta:
        model = NetworkDailyMetric
        fields = ["id", "school", "date", "metric", "value"]
        read_only_fields = fields

    def get_school(self, obj):
        return obj.tenant.name if obj.tenant_id else None
