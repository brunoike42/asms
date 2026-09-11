from .base import BaseExporter


class TanzaniaExporter(BaseExporter):
    country_template = "tanzania_moevt"
    headers = [
        "Student ID", "Surname", "First Name",
        "DOB", "Gender", "Nationality",
        "Disability", "Orphan Status", "Class", "Status", "Academic Year",
    ]

    def row(self, student, year):
        return [
            student.nsin or student.student_id or "",
            student.last_name,
            student.first_name,
            student.date_of_birth.strftime("%Y-%m-%d") if student.date_of_birth else "",
            student.gender or "",
            student.nationality or "",
            self.yn(student.has_disability),
            self.yn(student.is_orphan),
            self.class_label(student),
            student.status,
            str(year),
        ]
