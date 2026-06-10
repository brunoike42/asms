from django.shortcuts import render, redirect, get_object_or_404
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
        cs = ClassSubject.objects.get(pk=request.POST.get("class_subject"))
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
        messages.success(request, f'Assignment "{assignment.title}" created.')
        return redirect("assignment_list")
    class_subjects = ClassSubject.objects.select_related("classroom", "subject").all()
    return render(request, "assignments/assignment_form.html", {"class_subjects": class_subjects})


@login_required
def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment.objects, pk=pk, tenant=request.tenant)
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
        AssignmentSubmission.objects, pk=submission_id, tenant=request.tenant
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
    assignment = get_object_or_404(Assignment.objects, pk=pk, tenant=request.tenant)
    assignment.status = "published"
    assignment.save()
    messages.success(request, f'Assignment "{assignment.title}" published.')
    return redirect("assignment_list")
