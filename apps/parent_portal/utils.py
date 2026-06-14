"""
Parent portal utility functions.
"""
from django.utils import timezone
from django.apps import apps


def get_parent_students(user):
    """
    Return all Student objects linked to this parent/guardian user.
    Handles the Guardian → Student relationship.
    """
    try:
        Guardian = apps.get_model('students', 'Guardian')
        guardians = Guardian.objects.filter(user=user).select_related('student')
        students = [g.student for g in guardians if hasattr(g, 'student') and g.student]
        if not students:
            # Fallback: try direct student FK on guardian
            students = list(Guardian.objects.filter(user=user).values_list('student', flat=True))
        return students
    except Exception:
        return []


def get_student_queryset(user):
    """Return queryset of Students for a parent user."""
    try:
        Guardian = apps.get_model('students', 'Guardian')
        Student = apps.get_model('students', 'Student')
        student_ids = Guardian.objects.filter(user=user).values_list('student_id', flat=True)
        return Student.objects.filter(id__in=student_ids).select_related('current_class')
    except Exception:
        Student = apps.get_model('students', 'Student')
        return Student.objects.none()


def get_unread_notification_count(user):
    """Return count of unread parent notifications for badge display."""
    try:
        from .models import ParentNotification
        return ParentNotification.objects.filter(parent_user=user, is_read=False).count()
    except Exception:
        return 0


def get_child_quick_stats(student, tenant):
    """
    Return a dict of quick stats for a student for the dashboard.
    Benchmarked: PowerSchool summary card, ClassDojo child overview.
    """
    stats = {
        'attendance_pct': None,
        'open_incidents': 0,
        'outstanding_fees': 0,
        'pending_assignments': 0,
        'unread_merits': 0,
        'risk_level': 'low',
    }

    # Attendance — rolling 4-week average
    try:
        AttendanceRecord = apps.get_model('attendance', 'AttendanceRecord')
        four_weeks_ago = timezone.now().date() - timezone.timedelta(weeks=4)
        records = AttendanceRecord.objects.filter(
            student=student,
            date__gte=four_weeks_ago,
        )
        total = records.count()
        if total > 0:
            present = records.filter(status__in=['present', 'late']).count()
            stats['attendance_pct'] = round((present / total) * 100)
    except Exception:
        pass

    # Discipline incidents this term
    try:
        DisciplineIncident = apps.get_model('discipline', 'DisciplineIncident')
        stats['open_incidents'] = DisciplineIncident.objects.filter(
            student=student,
        ).exclude(status__in=['resolved', 'closed']).count()
    except Exception:
        pass

    # Outstanding fees
    try:
        FeeInvoice = apps.get_model('finance', 'FeeInvoice')
        from django.db.models import Sum
        unpaid = FeeInvoice.objects.filter(
            student=student,
            status__in=['unpaid', 'partial', 'overdue'],
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        stats['outstanding_fees'] = unpaid
    except Exception:
        pass

    # Pending assignments
    try:
        Assignment = apps.get_model('assignments', 'Assignment')
        today = timezone.now().date()
        stats['pending_assignments'] = Assignment.objects.filter(
            class_room=student.current_class,
            due_date__gte=today,
        ).count()
    except Exception:
        pass

    # Risk level from AtRiskRegister
    try:
        AtRiskRegister = apps.get_model('counselling', 'AtRiskRegister')
        risk = AtRiskRegister.objects.filter(student=student).order_by('-computed_at').first()
        if risk:
            stats['risk_level'] = risk.risk_level
            stats['risk_score'] = risk.risk_score
    except Exception:
        pass

    return stats


def get_child_attendance_calendar(student, month=None, year=None):
    """
    Return attendance records for a student for a given month.
    Used to render the attendance calendar.
    Benchmarked: Infinite Campus attendance calendar, PowerSchool.
    """
    try:
        AttendanceRecord = apps.get_model('attendance', 'AttendanceRecord')
        today = timezone.now().date()
        if not month:
            month = today.month
        if not year:
            year = today.year

        records = AttendanceRecord.objects.filter(
            student=student,
            date__month=month,
            date__year=year,
        ).order_by('date')

        calendar_data = {}
        for r in records:
            calendar_data[r.date.day] = {
                'status': r.status,
                'note': getattr(r, 'notes', '') or getattr(r, 'note', ''),
            }
        return calendar_data, month, year
    except Exception:
        return {}, month or timezone.now().month, year or timezone.now().year


def get_child_academic_summary(student, term=None):
    """
    Return subject-level marks for the latest/specified term.
    Benchmarked: PowerSchool gradebook, Infinite Campus grade summary.
    """
    try:
        ExamResult = apps.get_model('exams', 'ExamResult')
        qs = ExamResult.objects.filter(student=student)
        if term:
            qs = qs.filter(term=term)
        else:
            # Latest available
            latest = qs.order_by('-id').values('term').first()
            if latest:
                qs = qs.filter(term_id=latest['term'])

        results = list(qs.select_related('subject'))
        return results
    except Exception:
        return []


def get_activity_feed(student, limit=10):
    """
    Return recent activity posts for this student's class.
    Benchmarked: ClassDojo class story, Seesaw learning feed.
    """
    try:
        from django.db.models import Q
        from .models import ActivityPost
        posts = ActivityPost.objects.filter(
            tenant=student.tenant,
        ).filter(
            Q(classroom=student.current_class) |
            Q(student=student) |
            Q(audience='school')
        ).order_by('-is_pinned', '-created_at')[:limit]
        return list(posts)
    except Exception:
        return []


def _get_parent_users_for_student(student):
    """
    Return all User objects that are linked as guardians of a student.
    Used by signals to send notifications to the right parent accounts.
    """
    try:
        Guardian = apps.get_model('students', 'Guardian')
        from django.contrib.auth import get_user_model
        User = get_user_model()
        guardian_user_ids = Guardian.objects.filter(
            student=student
        ).exclude(user=None).values_list('user_id', flat=True)
        return list(User.objects.filter(id__in=guardian_user_ids))
    except Exception:
        return []


def create_parent_notification(parent_user, student, category, title, body,
                                action_url='', is_urgent=False, tenant=None):
    """Helper to create a ParentNotification record."""
    try:
        from .models import ParentNotification
        return ParentNotification.objects.create(
            tenant=tenant or getattr(student, 'tenant', None),
            parent_user=parent_user,
            student=student,
            category=category,
            title=title,
            body=body,
            action_url=action_url,
            is_urgent=is_urgent,
        )
    except Exception:
        pass
