from .base import BaseExporter


class UgandaExporter(BaseExporter):
    country_template = "uganda_moes"
    headers = [
        "NSIN", "NIN", "Surname", "First Name", "Other Names",
        "Date of Birth", "Gender", "Nationality",
        "Disability Status", "Orphan Status", "Refugee Status", "Refugee/Pass ID",
        "Class", "Admission Number", "Enrolment Status", "Academic Year",
    ]

    def row(self, student, year):
        return [
            student.nsin or "",
            getattr(student, "nin", "") or "",
            student.last_name,
            student.first_name,
            student.middle_name or "",
            student.date_of_birth.strftime("%Y-%m-%d") if student.date_of_birth else "",
            student.gender or "",
            student.nationality or "",
            self.yn(student.has_disability),
            self.yn(student.is_orphan),
            self.yn(student.is_refugee),
            getattr(student, "refugee_or_pass_id", "") or "",
            self.class_label(student),
            student.student_id or "",
            student.status,
            str(year),
        ]

    def compliance_issues(self, tenant):
        # Uganda-specific addition: NIN required for students 16+, on top of shared checks.
        issues = super().compliance_issues(tenant)
        students = self.get_queryset(tenant)
        missing_nin_adult = [
            s for s in students
            if s.age() and s.age() >= 16 and not getattr(s, "nin", "")
        ]
        if missing_nin_adult:
            issues.append(f"{len(missing_nin_adult)} student(s) 16+ missing a National ID (NIN).")
        return issues
