from .base import BaseExporter


class KenyaExporter(BaseExporter):
    country_template = "kenya_moe"
    headers = [
        "UPI", "Surname", "First Name", "Middle Name",
        "DOB", "Gender", "Nationality",
        "Special Needs", "Class", "Admission No",
        "Status", "Year",
    ]

    def row(self, student, year):
        return [
            student.nsin or "",  # UPI stored in the same field as NSIN — one national-ID slot per student
            student.last_name,
            student.first_name,
            student.middle_name or "",
            student.date_of_birth.strftime("%Y-%m-%d") if student.date_of_birth else "",
            student.gender or "",
            student.nationality or "",
            self.yn(student.has_disability),
            self.class_label(student),
            student.student_id or "",
            student.status,
            str(year),
        ]
