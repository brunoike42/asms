"""
EMIS export base class.

Each country exporter defines: headers (list[str]) and row(student, year) -> list[str].
The compliance check is shared — it's about what data is missing, not how a
given ministry wants it formatted.

Note on current_class: Student has no class_group FK. Class is reached via
the active Enrollment: student.current_class returns the ClassRoom or None.
Always go through that property, never student.class_group.
"""
from apps.students.models import Student


class BaseExporter:
    country_template = None       # matches EMISSubmission.CountryTemplateChoices value
    headers = []

    def get_queryset(self, tenant):
        return (
            Student.objects
            .filter(tenant=tenant, status="active")
            .select_related()
            .prefetch_related("enrollments__classroom__level")
        )

    def row(self, student, year):
        raise NotImplementedError

    def rows(self, tenant, year):
        return [self.row(s, year) for s in self.get_queryset(tenant)]

    def compliance_issues(self, tenant):
        """
        Shared compliance check — ministry-agnostic. Country-specific
        required fields can be added by overriding this and calling super().
        """
        issues = []
        students = self.get_queryset(tenant)

        missing_nsin = students.filter(nsin="").count()
        if missing_nsin:
            issues.append(f"{missing_nsin} active student(s) missing NSIN.")

        missing_gender = students.exclude(gender__in=["M", "F", "O"]).count()
        if missing_gender:
            issues.append(f"{missing_gender} student(s) missing gender.")

        missing_dob = students.filter(date_of_birth__isnull=True).count()
        if missing_dob:
            issues.append(f"{missing_dob} student(s) missing date of birth.")

        missing_class = [s for s in students if s.current_class is None]
        if missing_class:
            issues.append(f"{len(missing_class)} student(s) have no active class enrollment.")

        refugees_missing_id = students.filter(is_refugee=True, refugee_or_pass_id="").count()
        if refugees_missing_id:
            issues.append(
                f"{refugees_missing_id} refugee student(s) missing a refugee ID / student pass number."
            )

        return issues

    @staticmethod
    def class_label(student):
        cc = student.current_class
        return str(cc) if cc else ""

    @staticmethod
    def yn(value):
        return "Yes" if value else "No"
