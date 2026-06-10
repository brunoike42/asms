from django.shortcuts import render, redirect, get_object_or_404
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
                classroom=ClassRoom.objects.get(pk=request.POST.get("classroom")),
                subject=Subject.objects.get(pk=request.POST.get("subject")),
                term=Term.objects.get(pk=request.POST.get("term")),
                max_score=float(request.POST.get("max_score", 100)),
                exam_date=parse_date(request.POST.get("exam_date") or "") or None,
                created_by=request.user,
            )
            messages.success(request, f'Exam "{exam.name}" created.')
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
    exam = get_object_or_404(Exam.objects, pk=exam_id, tenant=request.tenant)
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
                    result, _ = ExamResult.objects.get_or_create(
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
    exam = get_object_or_404(Exam.objects, pk=exam_id, tenant=request.tenant)
    exam.is_published = True
    exam.save()
    messages.success(request, f'Results for "{exam.name}" published.')
    return redirect("exam_list")


@login_required
def exam_results(request, exam_id):
    exam = get_object_or_404(Exam.objects, pk=exam_id, tenant=request.tenant)
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
    term = get_object_or_404(Term.objects, pk=term_id, tenant=request.tenant)
    classrooms = ClassRoom.objects.filter(academic_year=term.academic_year)
    computed = 0
    for classroom in classrooms:
        students_in_class = Student.objects.filter(current_class=classroom, status="active")
        for student in students_in_class:
            exams = Exam.objects.filter(classroom=classroom, term=term, is_published=True)
            report, _ = TermReport.objects.get_or_create(
                student=student, term=term, tenant=request.tenant,
                defaults={"classroom": classroom},
            )
            report.classroom = classroom
            total = 0
            count = 0
            for exam in exams:
                try:
                    result = ExamResult.objects.get(exam=exam, student=student)
                    if result.score is not None:
                        pct = (float(result.score) / float(exam.max_score)) * 100
                        SubjectScore.objects.update_or_create(
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
        reports = TermReport.objects.filter(term=term, classroom=classroom).order_by("-average_score")
        total_in_class = reports.count()
        for i, rpt in enumerate(reports, 1):
            rpt.position = i
            rpt.out_of = total_in_class
            rpt.save()
    messages.success(request, f"Reports computed for {computed} students.")
    return redirect("report_list", term_id=term_id)


@login_required
def report_list(request, term_id):
    term = get_object_or_404(Term.objects, pk=term_id, tenant=request.tenant)
    reports = TermReport.objects.filter(term=term).select_related(
        "student", "classroom"
    ).order_by("classroom__name", "position")
    terms = Term.objects.all()
    return render(request, "exams/report_list.html", {
        "term": term, "reports": reports, "terms": terms,
    })


@login_required
def student_report(request, report_id):
    report = get_object_or_404(TermReport.objects, pk=report_id, tenant=request.tenant)
    subject_scores = report.subject_scores.select_related("subject").all()
    return render(request, "exams/student_report.html", {
        "report": report, "subject_scores": subject_scores, "tenant": request.tenant,
    })


@login_required
def publish_reports(request, term_id):
    term = get_object_or_404(Term.objects, pk=term_id, tenant=request.tenant)
    TermReport.objects.filter(term=term, tenant=request.tenant).update(is_published=True)
    messages.success(request, "All reports published.")
    return redirect("report_list", term_id=term_id)
