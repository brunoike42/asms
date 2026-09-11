"""
generate_emis_export — pre-flight compliance check + Uganda MoES CSV generation.
Usage:
    python manage.py generate_emis_export --tenant-id 1 --year-id 2
    python manage.py generate_emis_export --tenant-id 1 --year-id 2 --template kenya_moe
    python manage.py generate_emis_export --tenant-id 1 --year-id 2 --output exports/uganda_2025.csv
"""
import csv
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.core.models import AcademicYear, Tenant
from apps.students.models import Student
from apps.emis.models import EMISSubmission
COLUMNS = {
    "uganda_moes": [
        "NSIN", "Surname", "First Name", "Other Names",
        "Date of Birth", "Gender", "Nationality",
        "Disability Status", "Orphan Status",
        "Class", "Admission Number", "Enrolment Status", "Academic Year",
    ],
    "kenya_moe": [
        "UPI", "Surname", "First Name", "Middle Name",
        "DOB", "Gender", "Nationality",
        "Special Needs", "Class", "Admission No",
        "Status", "Year",
    ],
}
class Command(BaseCommand):
    help = "Run EMIS compliance check and generate a CSV census export."
    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", type=int, required=True)
        parser.add_argument("--year-id",   type=int, required=True)
        parser.add_argument(
            "--template",
            choices=["uganda_moes", "kenya_moe", "rwanda_reb", "tanzania_moevt"],
            default="uganda_moes",
        )
        parser.add_argument("--output", type=str, default="emis_export.csv")
    def handle(self, *args, **options):
        # ── Resolve tenant + year ────────────────────────────────────────
        try:
            tenant = Tenant.objects.get(pk=options["tenant_id"])
        except Tenant.DoesNotExist:
            raise CommandError(f"Tenant {options['tenant_id']} not found.")
        try:
            year = AcademicYear.objects.get(pk=options["year_id"], tenant=tenant)
        except AcademicYear.DoesNotExist:
            raise CommandError(f"AcademicYear {options['year_id']} not found for this tenant.")
        template = options["template"]
        # ── Pre-export compliance check ──────────────────────────────────
        self.stdout.write("Running compliance check...")
        issues = []
        students = Student.objects.filter(tenant=tenant, status="active")
        missing_nsin = students.filter(nsin__isnull=True).count() + \
                       students.filter(nsin="").count()
        if missing_nsin:
            issues.append(
                f"{missing_nsin} active student(s) missing NSIN — required by ministry."
            )
        missing_gender = students.filter(gender__isnull=True).count() + \
                         students.filter(gender="").count()
        if missing_gender:
            issues.append(f"{missing_gender} student(s) missing gender field.")
        missing_dob = students.filter(date_of_birth__isnull=True).count()
        if missing_dob:
            issues.append(f"{missing_dob} student(s) missing date of birth.")
        if issues:
            self.stdout.write(self.style.WARNING(f"{len(issues)} compliance issue(s) found:"))
            for i, issue in enumerate(issues, 1):
                self.stdout.write(f"   {i}. {issue}")
            self.stdout.write(self.style.WARNING(
                "Export will proceed — resolve issues before submitting to the ministry."
            ))
        else:
            self.stdout.write(self.style.SUCCESS("Compliance check passed."))
        # ── Generate CSV ─────────────────────────────────────────────────
        output_path = options["output"]
        headers = COLUMNS.get(template, COLUMNS["uganda_moes"])
        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for student in students.select_related("class_group"):
                row = [
                    getattr(student, "nsin", "") or "",
                    student.last_name,
                    student.first_name,
                    getattr(student, "middle_name", "") or "",
                    student.date_of_birth.strftime("%Y-%m-%d") if student.date_of_birth else "",
                    getattr(student, "gender", "") or "",
                    getattr(student, "nationality", "") or "",
                    "Yes" if getattr(student, "has_disability", False) else "No",
                    "Yes" if getattr(student, "is_orphan", False) else "No",
                    str(student.class_group) if getattr(student, "class_group_id", None) else "",
                    getattr(student, "student_id", "") or "",
                    student.status,
                    str(year),
                ]
                writer.writerow(row)
        student_count = students.count()
        self.stdout.write(self.style.SUCCESS(
            f"Exported {student_count} student(s) to {output_path}"
        ))
        # ── Record the submission event ──────────────────────────────────
        EMISSubmission.objects.create(
            tenant=tenant,
            academic_year=year,
            country_template=template,
            file_path=output_path,
            compliance_issues=issues,
            status="generated",
        )
        self.stdout.write(self.style.SUCCESS("Submission record saved to EMIS module."))
        if issues:
            self.stdout.write(self.style.WARNING(
                f"Resolve {len(issues)} issue(s) before submitting the file to the ministry."
            ))
