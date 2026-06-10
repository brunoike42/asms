from django.shortcuts import render, redirect, get_object_or_404
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
            department=Department.objects.get(pk=dept_id) if dept_id else None,
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
            classroom=ClassRoom.objects.get(pk=request.POST.get("classroom")),
            subject=Subject.objects.get(pk=request.POST.get("subject")),
            term=Term.objects.get(pk=request.POST.get("term")),
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
            ClassRoom.objects, pk=class_id, tenant=request.tenant
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
