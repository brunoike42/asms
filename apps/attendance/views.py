"""
ASMS Attendance Views
Teachers mark daily attendance per class.
Every absent mark triggers parent SMS + risk score update.
"""
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db.models import Count, Q
from datetime import date, timedelta
from .models import AttendanceRecord, AttendanceSummary
from apps.students.models import ClassRoom, Enrollment, Student
from apps.core.models import Term
from apps.core.mixins import require_roles
from apps.communication.services import send_absence_notification


@login_required
def attendance_home(request):
    """Landing page — teacher selects class and date."""
    tenant = request.tenant
    # Teachers see their own classes; admins see all
    if request.user.role in ('teacher',):
        classrooms = ClassRoom.objects.filter(
            tenant=tenant, class_teacher=request.user
        ).select_related('level', 'academic_year')
    else:
        classrooms = ClassRoom.objects.filter(
            tenant=tenant
        ).select_related('level', 'academic_year')

    today = date.today()
    # Today's marking status per class
    marked_today = {}
    for cls in classrooms:
        first_student = Enrollment.objects.filter(
            classroom=cls, is_active=True
        ).values_list('student_id', flat=True).first()
        if first_student:
            marked = AttendanceRecord.objects.filter(
                tenant=tenant,
                student_id=first_student,
                date=today,
            ).exists()
            marked_today[cls.pk] = marked

    return render(request, 'attendance/home.html', {
        'classrooms': classrooms,
        'today': today,
        'marked_today': marked_today,
    })


@login_required
def mark_attendance(request, classroom_pk):
    """
    Mark attendance for all students in a class for a given date.
    GET  → shows the register form
    POST → saves records, triggers SMS for absent students
    """
    tenant = request.tenant
    classroom = get_object_or_404(ClassRoom, pk=classroom_pk, tenant=tenant)

    # Date from query param or today
    date_str = request.GET.get('date') or request.POST.get('date')
    try:
        mark_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        mark_date = date.today()

    # Get all enrolled students
    enrollments = Enrollment.objects.filter(
        classroom=classroom, is_active=True
    ).select_related('student').order_by('student__last_name', 'student__first_name')

    if not enrollments.exists():
        messages.warning(request, 'No students enrolled in this class.')
        return redirect('attendance:home')

    # Check if already marked
    first_student = enrollments.first().student
    already_marked = AttendanceRecord.objects.filter(
        tenant=tenant, student=first_student, date=mark_date
    ).exists()

    if request.method == 'POST':
        submitted = request.POST
        absent_students = []
        saved_count = 0

        for enrollment in enrollments:
            student = enrollment.student
            field_name = f'status_{student.pk}'
            status = submitted.get(field_name, 'P')
            notes  = submitted.get(f'notes_{student.pk}', '')

            record, created = AttendanceRecord.objects.update_or_create(
                tenant=tenant,
                student=student,
                date=mark_date,
                defaults={
                    'classroom': classroom,
                    'status': status,
                    'marked_by': request.user,
                    'notes': notes,
                }
            )
            saved_count += 1

            # Collect absent students for SMS
            if status == 'A' and not record.parent_notified:
                absent_students.append((student, record))

        # Send SMS for absences
        sms_sent = 0
        for student, record in absent_students:
            primary_guardian = student.guardians.filter(
                tenant=tenant, receives_sms=True
            ).order_by('-is_primary').first()
            if primary_guardian and primary_guardian.phone_primary:
                sent = send_absence_notification(
                    student=student,
                    date=mark_date,
                    parent_phone=primary_guardian.phone_primary,
                    tenant=tenant,
                )
                if sent:
                    record.parent_notified = True
                    record.notification_sent_at = timezone.now()
                    record.save()
                    sms_sent += 1

        # Update summaries
        current_term = Term.objects.filter(tenant=tenant, is_current=True).first()
        if current_term:
            for enrollment in enrollments:
                summary, _ = AttendanceSummary.objects.get_or_create(
                    tenant=tenant,
                    student=enrollment.student,
                    term=current_term,
                )
                summary.update_from_records()

        msg = f'Attendance saved for {saved_count} students on {mark_date.strftime("%d %b %Y")}.'
        if absent_students:
            msg += f' {len(absent_students)} absence(s) recorded.'
        if sms_sent:
            msg += f' {sms_sent} parent SMS sent.'
        messages.success(request, msg)
        return redirect('attendance:home')

    # GET — load existing records if already marked
    existing = {}
    if already_marked:
        for rec in AttendanceRecord.objects.filter(
            tenant=tenant, classroom=classroom, date=mark_date
        ):
            existing[rec.student_id] = rec

    return render(request, 'attendance/mark_attendance.html', {
        'classroom': classroom,
        'enrollments': enrollments,
        'mark_date': mark_date,
        'already_marked': already_marked,
        'existing': existing,
        'status_choices': AttendanceRecord.StatusChoices.choices,
        'today': date.today(),
    })


@login_required
def attendance_report(request, classroom_pk):
    """Monthly attendance overview for a class."""
    tenant = request.tenant
    classroom = get_object_or_404(ClassRoom, pk=classroom_pk, tenant=tenant)

    # Date range: last 30 days by default
    end_date   = date.today()
    start_date = end_date - timedelta(days=29)

    enrollments = Enrollment.objects.filter(
        classroom=classroom, is_active=True
    ).select_related('student').order_by('student__last_name')

    # Build attendance grid
    date_range = [start_date + timedelta(days=i) for i in range(30)]
    records = AttendanceRecord.objects.filter(
        tenant=tenant,
        classroom=classroom,
        date__range=(start_date, end_date),
    ).values('student_id', 'date', 'status')

    record_map = {}
    for r in records:
        record_map[(r['student_id'], r['date'])] = r['status']

    grid = []
    for enr in enrollments:
        row = {
            'student': enr.student,
            'days': [(d, record_map.get((enr.student.pk, d), '')) for d in date_range],
            'present': sum(1 for d in date_range if record_map.get((enr.student.pk, d)) == 'P'),
            'absent':  sum(1 for d in date_range if record_map.get((enr.student.pk, d)) == 'A'),
        }
        row['pct'] = round(row['present'] / 30 * 100, 1) if row['present'] else 0
        grid.append(row)

    return render(request, 'attendance/report.html', {
        'classroom': classroom,
        'date_range': date_range,
        'grid': grid,
        'start_date': start_date,
        'end_date': end_date,
    })
