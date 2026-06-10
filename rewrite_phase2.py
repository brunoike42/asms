"""
Rewrites all 6 Phase 2 views.py files cleanly.
Correct imports, correct indentation, no patch artifacts.
Run from your project root: python rewrite_phase2_views.py
"""
import os

ROOT  = os.getcwd()
APPS  = os.path.join(ROOT, 'apps')

VIEWS = {}

# ── ACADEMICS ─────────────────────────────────────────────────────────────
VIEWS['academics'] = '''from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from apps.academics.models import Subject, ClassSubject, Department, TimetableSlot
from apps.students.models import ClassRoom
from apps.core.models import Term

User = get_user_model()


@login_required
def subject_list(request):
    subjects = Subject.objects.select_related("department").all()
    departments = Department.objects.all()
    return render(request, "academics/subject_list.html", {
        "subjects": subjects, "departments": departments
    })


@login_required
def subject_create(request):
    if request.method == "POST":
        dept_id = request.POST.get("department")
        Subject.objects.create(
            tenant=request.tenant,
            name=request.POST.get("name"),
            code=request.POST.get("code", ""),
            department=Department.all_objects.get(pk=dept_id) if dept_id else None,
            is_compulsory=bool(request.POST.get("is_compulsory")),
        )
        messages.success(request, "Subject created.")
        return redirect("subject_list")
    departments = Department.objects.all()
    return render(request, "academics/subject_form.html", {"departments": departments})


@login_required
def class_subject_list(request):
    class_subjects = ClassSubject.objects.select_related(
        "classroom", "subject", "teacher", "term"
    ).all()
    return render(request, "academics/class_subject_list.html", {
        "class_subjects": class_subjects
    })


@login_required
def class_subject_assign(request):
    if request.method == "POST":
        ClassSubject.objects.get_or_create(
            tenant=request.tenant,
            classroom=ClassRoom.all_objects.get(pk=request.POST.get("classroom")),
            subject=Subject.all_objects.get(pk=request.POST.get("subject")),
            term=Term.all_objects.get(pk=request.POST.get("term")),
            defaults={
                "teacher_id": request.POST.get("teacher") or None,
                "periods_per_week": int(request.POST.get("periods_per_week", 4)),
            },
        )
        messages.success(request, "Subject assigned to class.")
        return redirect("class_subject_list")
    classrooms = ClassRoom.objects.all()
    subjects = Subject.objects.all()
    terms = Term.objects.all()
    teachers = User.objects.filter(role="teacher")
    return render(request, "academics/class_subject_form.html", {
        "classrooms": classrooms, "subjects": subjects,
        "terms": terms, "teachers": teachers,
    })


@login_required
def timetable_view(request):
    class_id = request.GET.get("class")
    classrooms = ClassRoom.objects.all()
    slots = []
    selected_class = None
    if class_id:
        selected_class = get_object_or_404(
            ClassRoom.all_objects, pk=class_id, tenant=request.tenant
        )
        slots = TimetableSlot.objects.filter(
            class_subject__classroom=selected_class
        ).select_related("class_subject__subject", "class_subject__teacher").order_by("day", "period")
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    periods = range(1, 9)
    grid = {day: {p: None for p in periods} for day in days}
    for slot in slots:
        grid[slot.get_day_display()][slot.period] = slot
    return render(request, "academics/timetable.html", {
        "classrooms": classrooms, "selected_class": selected_class,
        "grid": grid, "days": days, "periods": periods,
    })
'''

# ── EXAMS ─────────────────────────────────────────────────────────────────
VIEWS['exams'] = '''from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from apps.exams.models import Exam, ExamResult, TermReport, SubjectScore
from apps.students.models import Student, ClassRoom
from apps.academics.models import Subject
from apps.core.models import Term

User = get_user_model()


@login_required
def exam_list(request):
    exams = Exam.objects.select_related("classroom", "subject", "term").order_by("-exam_date")
    classrooms = ClassRoom.objects.all()
    subjects = Subject.objects.all()
    terms = Term.objects.all()
    return render(request, "exams/exam_list.html", {
        "exams": exams, "classrooms": classrooms,
        "subjects": subjects, "terms": terms,
    })


@login_required
def exam_create(request):
    if request.method == "POST":
        from django.utils.dateparse import parse_date
        try:
            exam = Exam.objects.create(
                tenant=request.tenant,
                name=request.POST.get("name"),
                exam_type=request.POST.get("exam_type"),
                classroom=ClassRoom.all_objects.get(pk=request.POST.get("classroom")),
                subject=Subject.all_objects.get(pk=request.POST.get("subject")),
                term=Term.all_objects.get(pk=request.POST.get("term")),
                max_score=float(request.POST.get("max_score", 100)),
                exam_date=parse_date(request.POST.get("exam_date") or "") or None,
                created_by=request.user,
            )
            messages.success(request, f\'Exam "{exam.name}" created.\')
            return redirect("enter_marks", exam_id=exam.pk)
        except Exception as e:
            messages.error(request, f"Error: {e}")
    classrooms = ClassRoom.objects.all()
    subjects = Subject.objects.all()
    terms = Term.objects.all()
    return render(request, "exams/exam_form.html", {
        "classrooms": classrooms, "subjects": subjects,
        "terms": terms, "exam_types": Exam.TYPE_CHOICES,
    })


@login_required
def enter_marks(request, exam_id):
    exam = get_object_or_404(Exam.all_objects, pk=exam_id, tenant=request.tenant)
    students = Student.objects.filter(
        current_class=exam.classroom, status="active"
    ).order_by("last_name")
    existing = {r.student_id: r for r in ExamResult.objects.filter(exam=exam)}

    if request.method == "POST":
        saved = 0
        for student in students:
            score_str = request.POST.get(f"score_{student.pk}", "").strip()
            if score_str:
                try:
                    result, _ = ExamResult.all_objects.get_or_create(
                        exam=exam, student=student,
                        defaults={"tenant": request.tenant, "entered_by": request.user},
                    )
                    result.score = float(score_str)
                    result.remarks = request.POST.get(f"remarks_{student.pk}", "")
                    result.entered_by = request.user
                    result.save()
                    saved += 1
                except ValueError:
                    pass
        messages.success(request, f"{saved} marks saved.")
        return redirect("enter_marks", exam_id=exam_id)

    student_data = []
    for s in students:
        r = existing.get(s.pk)
        student_data.append({
            "student": s,
            "score": r.score if r else "",
            "grade": r.grade if r else "",
            "remarks": r.remarks if r else "",
        })
    scores = [float(r.score) for r in existing.values() if r.score is not None]
    stats = {}
    if scores:
        stats = {
            "count": len(scores),
            "avg": round(sum(scores) / len(scores), 1),
            "highest": max(scores),
            "lowest": min(scores),
            "pass_count": len([s for s in scores if (s / float(exam.max_score)) * 100 >= 50]),
        }
    return render(request, "exams/enter_marks.html", {
        "exam": exam, "student_data": student_data, "stats": stats,
    })


@login_required
def publish_exam(request, exam_id):
    exam = get_object_or_404(Exam.all_objects, pk=exam_id, tenant=request.tenant)
    exam.is_published = True
    exam.save()
    messages.success(request, f\'Results for "{exam.name}" published.\')
    return redirect("exam_list")


@login_required
def exam_results(request, exam_id):
    exam = get_object_or_404(Exam.all_objects, pk=exam_id, tenant=request.tenant)
    results = ExamResult.objects.filter(exam=exam).select_related("student").order_by("-score")
    scores = [float(r.score) for r in results if r.score is not None]
    stats = {}
    if scores:
        stats = {
            "avg": round(sum(scores) / len(scores), 1),
            "highest": max(scores),
            "lowest": min(scores),
            "count": len(scores),
            "pass_count": len([s for s in scores if (s / float(exam.max_score)) * 100 >= 50]),
        }
    return render(request, "exams/exam_results.html", {
        "exam": exam, "results": results, "stats": stats,
    })


@login_required
def compute_reports(request, term_id):
    term = get_object_or_404(Term.all_objects, pk=term_id, tenant=request.tenant)
    classrooms = ClassRoom.objects.filter(academic_year=term.academic_year)
    computed = 0
    for classroom in classrooms:
        students_in_class = Student.objects.filter(current_class=classroom, status="active")
        for student in students_in_class:
            exams = Exam.all_objects.filter(classroom=classroom, term=term, is_published=True)
            report, _ = TermReport.all_objects.get_or_create(
                student=student, term=term, tenant=request.tenant,
                defaults={"classroom": classroom},
            )
            report.classroom = classroom
            total = 0
            count = 0
            for exam in exams:
                try:
                    result = ExamResult.all_objects.get(exam=exam, student=student)
                    if result.score is not None:
                        pct = (float(result.score) / float(exam.max_score)) * 100
                        SubjectScore.all_objects.update_or_create(
                            report=report, subject=exam.subject, tenant=request.tenant,
                            defaults={
                                "total_score": result.score,
                                "max_possible": exam.max_score,
                                "percentage": pct,
                                "grade": result.grade,
                            },
                        )
                        total += pct
                        count += 1
                except ExamResult.DoesNotExist:
                    pass
            report.total_marks = total
            report.average_score = round(total / count, 2) if count else 0
            report.save()
            computed += 1
    for classroom in classrooms:
        reports = TermReport.all_objects.filter(term=term, classroom=classroom).order_by("-average_score")
        total_in_class = reports.count()
        for i, rpt in enumerate(reports, 1):
            rpt.position = i
            rpt.out_of = total_in_class
            rpt.save()
    messages.success(request, f"Reports computed for {computed} students.")
    return redirect("report_list", term_id=term_id)


@login_required
def report_list(request, term_id):
    term = get_object_or_404(Term.all_objects, pk=term_id, tenant=request.tenant)
    reports = TermReport.objects.filter(term=term).select_related(
        "student", "classroom"
    ).order_by("classroom__name", "position")
    terms = Term.objects.all()
    return render(request, "exams/report_list.html", {
        "term": term, "reports": reports, "terms": terms,
    })


@login_required
def student_report(request, report_id):
    report = get_object_or_404(TermReport.all_objects, pk=report_id, tenant=request.tenant)
    subject_scores = report.subject_scores.select_related("subject").all()
    return render(request, "exams/student_report.html", {
        "report": report, "subject_scores": subject_scores, "tenant": request.tenant,
    })


@login_required
def publish_reports(request, term_id):
    term = get_object_or_404(Term.all_objects, pk=term_id, tenant=request.tenant)
    TermReport.all_objects.filter(term=term, tenant=request.tenant).update(is_published=True)
    messages.success(request, "All reports published.")
    return redirect("report_list", term_id=term_id)
'''

# ── STAFF HR ──────────────────────────────────────────────────────────────
VIEWS['staff_hr'] = '''from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.staff_hr.models import StaffProfile, LeaveRequest, LeaveType, CPDRecord
from apps.academics.models import Department

User = get_user_model()


@login_required
def staff_list(request):
    staff = StaffProfile.objects.select_related("user", "department").filter(is_active=True)
    return render(request, "staff_hr/staff_list.html", {"staff": staff})


@login_required
def staff_detail(request, pk):
    staff = get_object_or_404(StaffProfile.all_objects, pk=pk, tenant=request.tenant)
    leaves = staff.leave_requests.all()[:10]
    cpd = staff.cpd_records.all()[:10]
    return render(request, "staff_hr/staff_detail.html", {
        "staff": staff, "leaves": leaves, "cpd": cpd,
    })


@login_required
def staff_create(request):
    if request.method == "POST":
        try:
            user = User.objects.create_user(
                username=request.POST.get("username"),
                password=request.POST.get("password", "Staff@2025"),
                first_name=request.POST.get("first_name"),
                last_name=request.POST.get("last_name"),
                email=request.POST.get("email", ""),
                role=request.POST.get("role", "teacher"),
                tenant=request.tenant,
            )
            dept_id = request.POST.get("department")
            StaffProfile.objects.create(
                tenant=request.tenant,
                user=user,
                staff_no=request.POST.get("staff_no", ""),
                department=Department.all_objects.get(pk=dept_id) if dept_id else None,
                designation=request.POST.get("designation", ""),
                employment_type=request.POST.get("employment_type", "permanent"),
                date_joined=request.POST.get("date_joined") or None,
            )
            messages.success(request, f"Staff member {user.get_full_name()} added.")
            return redirect("staff_list")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    departments = Department.objects.all()
    role_choices = [
        ("principal", "Principal"), ("teacher", "Teacher"),
        ("accountant", "Accountant"), ("counsellor", "Counsellor"),
        ("librarian", "Librarian"), ("receptionist", "Receptionist"),
        ("nurse", "Nurse"),
    ]
    return render(request, "staff_hr/staff_form.html", {
        "departments": departments, "roles": role_choices,
    })


@login_required
def leave_list(request):
    leaves = LeaveRequest.objects.select_related(
        "staff__user", "leave_type"
    ).order_by("-applied_at")
    leave_types = LeaveType.objects.all()
    return render(request, "staff_hr/leave_list.html", {
        "leaves": leaves, "leave_types": leave_types,
    })


@login_required
def leave_apply(request):
    if request.method == "POST":
        try:
            staff = StaffProfile.all_objects.get(user=request.user, tenant=request.tenant)
        except StaffProfile.DoesNotExist:
            messages.error(request, "Your staff profile was not found.")
            return redirect("leave_list")
        leave_type = LeaveType.all_objects.get(pk=request.POST.get("leave_type"))
        LeaveRequest.objects.create(
            tenant=request.tenant,
            staff=staff,
            leave_type=leave_type,
            start_date=request.POST.get("start_date"),
            end_date=request.POST.get("end_date"),
            reason=request.POST.get("reason"),
        )
        messages.success(request, "Leave application submitted.")
        return redirect("leave_list")
    leave_types = LeaveType.objects.all()
    return render(request, "staff_hr/leave_form.html", {"leave_types": leave_types})


@login_required
def leave_action(request, pk, action):
    leave = get_object_or_404(LeaveRequest.all_objects, pk=pk, tenant=request.tenant)
    if action == "approve":
        leave.status = "approved"
        leave.approved_by = request.user
        leave.approved_at = timezone.now()
        leave.save()
        messages.success(request, f"Leave approved for {leave.staff.user.get_full_name()}.")
    elif action == "reject":
        leave.status = "rejected"
        leave.rejection_reason = request.POST.get("reason", "")
        leave.save()
        messages.warning(request, "Leave rejected.")
    return redirect("leave_list")


@login_required
def cpd_list(request):
    records = CPDRecord.objects.select_related("staff__user").order_by("-start_date")
    return render(request, "staff_hr/cpd_list.html", {"records": records})


@login_required
def cpd_create(request):
    if request.method == "POST":
        try:
            staff = StaffProfile.all_objects.get(pk=request.POST.get("staff"))
        except StaffProfile.DoesNotExist:
            messages.error(request, "Staff not found.")
            return redirect("cpd_list")
        CPDRecord.objects.create(
            tenant=request.tenant,
            staff=staff,
            title=request.POST.get("title"),
            institution=request.POST.get("institution", ""),
            cpd_type=request.POST.get("cpd_type", "workshop"),
            start_date=request.POST.get("start_date"),
            end_date=request.POST.get("end_date") or None,
            hours=float(request.POST.get("hours", 0)),
            notes=request.POST.get("notes", ""),
        )
        messages.success(request, "CPD record added.")
        return redirect("cpd_list")
    all_staff = StaffProfile.objects.select_related("user").filter(is_active=True)
    return render(request, "staff_hr/cpd_form.html", {
        "all_staff": all_staff,
        "cpd_types": CPDRecord._meta.get_field("cpd_type").choices,
    })
'''

# ── LIBRARY ───────────────────────────────────────────────────────────────
VIEWS['library'] = '''from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.library.models import Book, BorrowRecord, BookCategory
from apps.students.models import Student


@login_required
def book_list(request):
    q = request.GET.get("q", "")
    category_id = request.GET.get("category", "")
    books = Book.objects.select_related("category")
    if q:
        books = books.filter(title__icontains=q) | books.filter(author__icontains=q)
    if category_id:
        books = books.filter(category_id=category_id)
    categories = BookCategory.objects.all()
    return render(request, "library/book_list.html", {
        "books": books, "categories": categories, "q": q,
    })


@login_required
def book_create(request):
    if request.method == "POST":
        category_id = request.POST.get("category")
        Book.objects.create(
            tenant=request.tenant,
            isbn=request.POST.get("isbn", ""),
            title=request.POST.get("title"),
            author=request.POST.get("author"),
            publisher=request.POST.get("publisher", ""),
            category=BookCategory.all_objects.get(pk=category_id) if category_id else None,
            edition=request.POST.get("edition", ""),
            year_published=int(request.POST.get("year_published")) if request.POST.get("year_published") else None,
            total_copies=int(request.POST.get("total_copies", 1)),
            available_copies=int(request.POST.get("total_copies", 1)),
            location=request.POST.get("location", ""),
            description=request.POST.get("description", ""),
        )
        messages.success(request, "Book added to catalogue.")
        return redirect("book_list")
    categories = BookCategory.objects.all()
    return render(request, "library/book_form.html", {"categories": categories})


@login_required
def book_detail(request, pk):
    book = get_object_or_404(Book.all_objects, pk=pk, tenant=request.tenant)
    borrows = BorrowRecord.objects.filter(book=book).select_related("student")[:10]
    return render(request, "library/book_detail.html", {"book": book, "borrows": borrows})


@login_required
def borrow_book(request):
    if request.method == "POST":
        book = get_object_or_404(Book.all_objects, pk=request.POST.get("book"), tenant=request.tenant)
        student = get_object_or_404(Student.all_objects, pk=request.POST.get("student"), tenant=request.tenant)
        if book.available_copies <= 0:
            messages.error(request, "No copies available.")
            return redirect("borrow_list")
        from datetime import timedelta, date
        due = date.today() + timedelta(days=int(request.POST.get("days", 14)))
        BorrowRecord.objects.create(
            tenant=request.tenant, book=book,
            student=student, due_date=due, issued_by=request.user,
        )
        book.available_copies -= 1
        book.save()
        messages.success(request, f\'"{book.title}" issued to {student.full_name}. Due: {due}\')
        return redirect("borrow_list")
    books = Book.objects.filter(available_copies__gt=0)
    students = Student.objects.filter(status="active")
    return render(request, "library/borrow_form.html", {"books": books, "students": students})


@login_required
def return_book(request, record_id):
    record = get_object_or_404(BorrowRecord.all_objects, pk=record_id, tenant=request.tenant)
    from datetime import date
    record.return_date = date.today()
    record.save()
    record.book.available_copies += 1
    record.book.save()
    if record.fine_amount > 0:
        messages.warning(request, f"Returned. Fine: UGX {record.fine_amount:,.0f}")
    else:
        messages.success(request, "Book returned. No fines.")
    return redirect("borrow_list")


@login_required
def borrow_list(request):
    records = BorrowRecord.objects.select_related("book", "student").order_by("-borrow_date")
    overdue = BorrowRecord.objects.filter(status="overdue").count()
    return render(request, "library/borrow_list.html", {"records": records, "overdue": overdue})
'''

# ── LMS ───────────────────────────────────────────────────────────────────
VIEWS['lms'] = '''from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.lms.models import LessonPlan, LMSResource, Quiz, QuizQuestion, QuizOption
from apps.academics.models import ClassSubject


@login_required
def lms_dashboard(request):
    class_subjects = ClassSubject.objects.select_related("classroom", "subject", "teacher").all()
    return render(request, "lms/dashboard.html", {"class_subjects": class_subjects})


@login_required
def resource_list(request, class_subject_id=None):
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    resources = LMSResource.objects.select_related("class_subject").all()
    selected_cs = None
    if class_subject_id:
        selected_cs = get_object_or_404(ClassSubject.all_objects, pk=class_subject_id, tenant=request.tenant)
        resources = resources.filter(class_subject=selected_cs)
    return render(request, "lms/resource_list.html", {
        "resources": resources, "class_subjects": class_subjects, "selected_cs": selected_cs,
    })


@login_required
def resource_create(request):
    if request.method == "POST":
        cs = ClassSubject.all_objects.get(pk=request.POST.get("class_subject"))
        LMSResource.objects.create(
            tenant=request.tenant,
            class_subject=cs,
            title=request.POST.get("title"),
            description=request.POST.get("description", ""),
            resource_type=request.POST.get("resource_type", "document"),
            external_url=request.POST.get("external_url", ""),
            week_number=int(request.POST.get("week_number")) if request.POST.get("week_number") else None,
            uploaded_by=request.user,
            file=request.FILES.get("file"),
        )
        messages.success(request, "Resource uploaded.")
        return redirect("resource_list")
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    return render(request, "lms/resource_form.html", {
        "class_subjects": class_subjects, "resource_types": LMSResource.RESOURCE_TYPES,
    })


@login_required
def lesson_plan_list(request):
    plans = LessonPlan.objects.select_related(
        "class_subject__classroom", "class_subject__subject"
    ).all()
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    return render(request, "lms/lesson_plan_list.html", {
        "plans": plans, "class_subjects": class_subjects,
    })


@login_required
def lesson_plan_create(request):
    if request.method == "POST":
        cs = ClassSubject.all_objects.get(pk=request.POST.get("class_subject"))
        LessonPlan.objects.create(
            tenant=request.tenant,
            class_subject=cs,
            title=request.POST.get("title"),
            week_number=int(request.POST.get("week_number", 1)),
            lesson_number=int(request.POST.get("lesson_number", 1)),
            objectives=request.POST.get("objectives", ""),
            content=request.POST.get("content", ""),
            activities=request.POST.get("activities", ""),
            resources_needed=request.POST.get("resources_needed", ""),
        )
        messages.success(request, "Lesson plan created.")
        return redirect("lesson_plan_list")
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    return render(request, "lms/lesson_plan_form.html", {"class_subjects": class_subjects})


@login_required
def quiz_list(request):
    quizzes = Quiz.objects.select_related(
        "class_subject__classroom", "class_subject__subject"
    ).all()
    return render(request, "lms/quiz_list.html", {"quizzes": quizzes})


@login_required
def quiz_create(request):
    if request.method == "POST":
        cs = ClassSubject.all_objects.get(pk=request.POST.get("class_subject"))
        quiz = Quiz.objects.create(
            tenant=request.tenant,
            class_subject=cs,
            title=request.POST.get("title"),
            description=request.POST.get("description", ""),
            duration_minutes=int(request.POST.get("duration_minutes", 30)),
            max_attempts=int(request.POST.get("max_attempts", 1)),
            shuffle_questions=bool(request.POST.get("shuffle_questions")),
            created_by=request.user,
        )
        messages.success(request, f\'Quiz "{quiz.title}" created.\')
        return redirect("quiz_add_questions", quiz_id=quiz.pk)
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    return render(request, "lms/quiz_form.html", {"class_subjects": class_subjects})


@login_required
def quiz_add_questions(request, quiz_id):
    quiz = get_object_or_404(Quiz.all_objects, pk=quiz_id, tenant=request.tenant)
    if request.method == "POST":
        question = QuizQuestion.objects.create(
            quiz=quiz,
            question_text=request.POST.get("question_text"),
            question_type=request.POST.get("question_type", "mcq"),
            marks=float(request.POST.get("marks", 1)),
            order=quiz.questions.count() + 1,
        )
        q_type = request.POST.get("question_type", "mcq")
        if q_type == "mcq":
            for i in range(1, 5):
                opt = request.POST.get(f"option_{i}", "").strip()
                if opt:
                    QuizOption.objects.create(
                        question=question,
                        option_text=opt,
                        is_correct=(request.POST.get("correct_option") == str(i)),
                    )
        elif q_type == "true_false":
            correct = request.POST.get("tf_answer", "True")
            QuizOption.objects.create(question=question, option_text="True", is_correct=(correct == "True"))
            QuizOption.objects.create(question=question, option_text="False", is_correct=(correct == "False"))
        messages.success(request, "Question added.")
        return redirect("quiz_add_questions", quiz_id=quiz_id)
    questions = quiz.questions.prefetch_related("options").all()
    return render(request, "lms/quiz_questions.html", {"quiz": quiz, "questions": questions})


@login_required
def quiz_publish(request, quiz_id):
    quiz = get_object_or_404(Quiz.all_objects, pk=quiz_id, tenant=request.tenant)
    quiz.is_published = True
    quiz.save()
    messages.success(request, f\'Quiz "{quiz.title}" is now live.\')
    return redirect("quiz_list")
'''

# ── ASSIGNMENTS ───────────────────────────────────────────────────────────
VIEWS['assignments'] = '''from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from apps.assignments.models import Assignment, AssignmentSubmission, AssignmentRubric
from apps.academics.models import ClassSubject
from apps.students.models import Student


@login_required
def assignment_list(request):
    assignments = Assignment.objects.select_related(
        "class_subject__classroom", "class_subject__subject"
    ).order_by("-created_at")
    return render(request, "assignments/assignment_list.html", {"assignments": assignments})


@login_required
def assignment_create(request):
    if request.method == "POST":
        from django.utils.dateparse import parse_datetime
        cs = ClassSubject.all_objects.get(pk=request.POST.get("class_subject"))
        due = parse_datetime(request.POST.get("due_date", "")) or timezone.now()
        assignment = Assignment.objects.create(
            tenant=request.tenant,
            class_subject=cs,
            title=request.POST.get("title"),
            description=request.POST.get("description"),
            instructions=request.POST.get("instructions", ""),
            max_marks=float(request.POST.get("max_marks", 100)),
            due_date=due,
            status=request.POST.get("status", "draft"),
            allow_late=bool(request.POST.get("allow_late")),
            allow_resubmit=bool(request.POST.get("allow_resubmit")),
            created_by=request.user,
            attachment=request.FILES.get("attachment"),
        )
        for c, m in zip(request.POST.getlist("criterion"), request.POST.getlist("criterion_marks")):
            if c.strip():
                AssignmentRubric.objects.create(
                    assignment=assignment, criterion=c, max_marks=float(m or 0)
                )
        messages.success(request, f\'Assignment "{assignment.title}" created.\')
        return redirect("assignment_list")
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    return render(request, "assignments/assignment_form.html", {"class_subjects": class_subjects})


@login_required
def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment.all_objects, pk=pk, tenant=request.tenant)
    submissions = assignment.submissions.select_related("student").all()
    rubrics = assignment.rubrics.all()
    students_in_class = Student.objects.filter(
        current_class=assignment.class_subject.classroom, status="active"
    )
    submitted_ids = set(submissions.values_list("student_id", flat=True))
    not_submitted = [s for s in students_in_class if s.pk not in submitted_ids]
    return render(request, "assignments/assignment_detail.html", {
        "assignment": assignment, "submissions": submissions,
        "rubrics": rubrics, "not_submitted": not_submitted,
    })


@login_required
def grade_submission(request, submission_id):
    submission = get_object_or_404(
        AssignmentSubmission.all_objects, pk=submission_id, tenant=request.tenant
    )
    if request.method == "POST":
        marks = float(request.POST.get("marks", 0))
        pct = (marks / float(submission.assignment.max_marks)) * 100
        grade = "A" if pct >= 90 else ("B" if pct >= 80 else ("C" if pct >= 70 else ("D" if pct >= 60 else ("E" if pct >= 50 else "F"))))
        submission.marks = marks
        submission.grade = grade
        submission.teacher_comment = request.POST.get("teacher_comment", "")
        submission.status = "graded"
        submission.graded_by = request.user
        submission.graded_at = timezone.now()
        submission.save()
        messages.success(request, f"Grade saved: {marks}/{submission.assignment.max_marks} — {grade}")
        return redirect("assignment_detail", pk=submission.assignment.pk)
    return render(request, "assignments/grade_submission.html", {"submission": submission})


@login_required
def publish_assignment(request, pk):
    assignment = get_object_or_404(Assignment.all_objects, pk=pk, tenant=request.tenant)
    assignment.status = "published"
    assignment.save()
    messages.success(request, f\'Assignment "{assignment.title}" published.\')
    return redirect("assignment_list")
'''

# ── Write all files ────────────────────────────────────────────────────────
print("\n═══ Rewriting Phase 2 views.py files ═══\n")
for app, content in VIEWS.items():
    path = os.path.join(APPS, app, 'views.py')
    if not os.path.isdir(os.path.join(APPS, app)):
        print(f"  ✗ apps/{app}/ not found — skipping")
        continue
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  ✓ Rewrote apps/{app}/views.py")

print("""
═══════════════════════════════════════════════════════════
  NOW RUN:
    python manage.py makemigrations
    python manage.py migrate
═══════════════════════════════════════════════════════════
""")