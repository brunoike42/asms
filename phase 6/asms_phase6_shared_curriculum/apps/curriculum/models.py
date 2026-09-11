"""
apps/curriculum/models.py

Phase 6, Aspect 3 — Shared Curriculum. The model shape follows the
Canvas Blueprint Course mechanic almost exactly: a published resource
has a lock decision the network sets (never the school), a version
number, and a per-school adoption row that tracks whether that school
is still in sync or has permanently diverged by editing an unlocked
item locally.

network=None on CurriculumResource means platform/NCDC-baseline content
that any school can adopt directly, not just network members — schools
without a network still need somewhere to get a starting curriculum.
"""
from django.conf import settings
from django.db import models


class ResourceType(models.TextChoices):
    SYLLABUS_TOPIC = "SYLLABUS_TOPIC", "Syllabus topic"
    SCHEME_OF_WORK = "SCHEME_OF_WORK", "Scheme of work"
    LESSON_PLAN = "LESSON_PLAN", "Lesson plan"
    QUIZ_BANK = "QUIZ_BANK", "Quiz bank"


class CurriculumSource(models.TextChoices):
    NCDC_ALIGNED = "NCDC_ALIGNED", "NCDC aligned"
    NETWORK_CUSTOM = "NETWORK_CUSTOM", "Network custom"


class ResourceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"


class CurriculumResource(models.Model):
    network = models.ForeignKey(
        "networks.Network",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="curriculum_resources",
        help_text="Null = platform/NCDC-baseline content, adoptable by any school.",
    )
    title = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=32, choices=ResourceType.choices)
    subject = models.CharField(max_length=100)
    level = models.CharField(max_length=50, help_text="Grade/form/year this applies to.")
    content = models.TextField()

    curriculum_source = models.CharField(
        max_length=32, choices=CurriculumSource.choices, default=CurriculumSource.NETWORK_CUSTOM
    )
    default_locked = models.BooleanField(
        default=False,
        help_text="Set by the network when publishing, never by a school. Locked items can never diverge.",
    )
    status = models.CharField(max_length=16, choices=ResourceStatus.choices, default=ResourceStatus.DRAFT)
    version = models.PositiveIntegerField(default=1)
    effective_from_date = models.DateField(
        null=True,
        blank=True,
        help_text="Sync waits until this date — a mid-term publish doesn't retroactively "
        "change what an enrolled cohort is already following (NCDC's own rollouts are cohort-staged).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Curriculum resource"
        verbose_name_plural = "Curriculum resources"
        ordering = ["subject", "level", "title"]

    def __str__(self):
        return f"{self.title} v{self.version}"


class CurriculumAdoption(models.Model):
    """
    One row per school per resource. adopted_version tracks what a school
    is currently synced to; is_diverged=True means a sync will skip this
    row entirely from now on — set once, by editing an unlocked item,
    and never cleared automatically (matches Blueprint: re-locking an
    item doesn't restore its sync link).
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="curriculum_adoptions")
    resource = models.ForeignKey(CurriculumResource, on_delete=models.CASCADE, related_name="adoptions")
    adopted_version = models.PositiveIntegerField()
    is_diverged = models.BooleanField(default=False)
    diverged_at = models.DateTimeField(null=True, blank=True)
    local_content = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Curriculum adoption"
        verbose_name_plural = "Curriculum adoptions"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "resource"], name="unique_adoption_per_school_resource"),
        ]

    def __str__(self):
        state = f"diverged @ v{self.adopted_version}" if self.is_diverged else f"synced @ v{self.adopted_version}"
        return f"{self.tenant} — {self.resource.title} ({state})"


class CurriculumPublishLog(models.Model):
    """Append-only — one row per publish event, mirroring NetworkQueryLog's audit shape."""

    resource = models.ForeignKey(CurriculumResource, on_delete=models.CASCADE, related_name="publish_logs")
    version = models.PositiveIntegerField()
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    published_at = models.DateTimeField(auto_now_add=True)
    synced_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Curriculum publish log"
        verbose_name_plural = "Curriculum publish logs"
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.resource.title} v{self.version} — {self.synced_count} synced, {self.skipped_count} skipped"
