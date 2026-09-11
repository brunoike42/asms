from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Student, ClassRoom, Enrollment, Guardian, ClassLevel
from .forms import StudentForm, GuardianForm, ClassRoomForm
from apps.core.mixins import require_roles


@login_required
@require_roles('school_admin', 'principal', 'receptionist')
def student_list(request):
    tenant = request.tenant
    queryset = Student.objects.filter(tenant=tenant, status='active').prefetch_related('enrollments__classroom__level')
    # Search
    q = request.GET.get('q', '')
    if q:
        queryset = queryset.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) |
            Q(student_id__icontains=q) | Q(nsin__icontains=q)
        )
    # Filter by class
    classroom_id = request.GET.get('classroom')
    if classroom_id:
        queryset = queryset.filter(enrollments__classroom_id=classroom_id, enrollments__is_active=True)

    paginator = Paginator(queryset, 25)
    page = paginator.get_page(request.GET.get('page'))
    classrooms = ClassRoom.objects.filter(tenant=tenant).select_related('level', 'academic_year')

    return render(request, 'students/student_list.html', {
        'page_obj': page,
        'classrooms': classrooms,
        'search_query': q,
        'selected_class': classroom_id,
        'total_count': queryset.count(),
    })


@login_required
def student_detail(request, pk):
    tenant = request.tenant
    user = request.user

    if user.role in (
        'school_admin',
        'principal',
        'receptionist',
    ):
        student = get_object_or_404(
            Student,
            pk=pk,
            tenant=tenant,
        )

    elif user.role == 'teacher':
        student = get_object_or_404(
            Student.objects.filter(
                tenant=tenant,
                pk=pk,
                enrollments__is_active=True,
                enrollments__classroom__class_teacher=user,
            ).distinct()
        )

    else:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    enrollment = student.enrollments.filter(
        is_active=True
    ).select_related(
        'classroom__level',
        'academic_year'
    ).first()

    guardians = student.guardians.filter(
        tenant=tenant
    )

    return render(request, 'students/student_detail.html', {
        'student': student,
        'enrollment': enrollment,
        'guardians': guardians,
    })


@login_required
@require_roles('school_admin', 'principal', 'receptionist')
def student_create(request):
    tenant = request.tenant
    form = StudentForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        student = form.save(commit=False)
        student.tenant = tenant
        # Auto-generate student ID
        if not student.student_id:
            count = Student.objects.filter(tenant=tenant).count() + 1
            student.student_id = f'{tenant.slug.upper()[:3]}{count:04d}'
        student.save()
        messages.success(request, f'Student {student.get_full_name()} created successfully.')
        return redirect('students:detail', pk=student.pk)
    return render(request, 'students/student_form.html', {
        'form': form, 'action': 'Add New Student'
    })


@login_required
@require_roles('school_admin', 'principal', 'receptionist')
def student_edit(request, pk):
    tenant = request.tenant
    student = get_object_or_404(Student, pk=pk, tenant=tenant)
    form = StudentForm(request.POST or None, request.FILES or None, instance=student)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Student record updated.')
        return redirect('students:detail', pk=student.pk)
    return render(request, 'students/student_form.html', {
        'form': form, 'student': student, 'action': 'Edit Student'
    })


@login_required
@require_roles('school_admin', 'principal', 'teacher')

def classroom_list(request):
    tenant = request.tenant
    classrooms = ClassRoom.objects.filter(tenant=tenant).select_related(
        'level', 'class_teacher', 'academic_year'
    ).prefetch_related('enrollments')
    return render(request, 'students/classroom_list.html', {'classrooms': classrooms})
