from rest_framework import serializers

from .models import CurriculumAdoption, CurriculumResource


class CurriculumResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurriculumResource
        fields = [
            "id",
            "network",
            "title",
            "resource_type",
            "subject",
            "level",
            "content",
            "curriculum_source",
            "default_locked",
            "status",
            "version",
            "effective_from_date",
        ]
        read_only_fields = ["id", "status", "version"]


class CurriculumAdoptionSerializer(serializers.ModelSerializer):
    """
    Deliberately excludes local_content — this serializer backs the
    adoption *status* endpoint (who's synced, who's diverged), not a
    full-content editor. A school's own diverged content is fetched
    through its own portal, not through the network admin's status view.
    """

    school = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = CurriculumAdoption
        fields = ["id", "school", "resource", "adopted_version", "is_diverged", "diverged_at"]
        read_only_fields = fields
