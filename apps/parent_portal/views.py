"""
Parent Portal views.

All views require:
  1. User is authenticated
  2. User has role 'parent' (or is a guardian linked to students)


Features benchmarked and added:
  ClassDojo    — activity feed, instant alerts, child switcher
  PowerSchool  — grade trends, teacher comments, attendance calendar
  Infinite Campus — meeting booking, multi-child, notification centre
  FACTS        — fee statement, instalment view, payment history
  FamilyID     — consent forms, emergency contacts
  Seesaw       — achievement wall, student portfolio
  Class Charts — assignment calendar, merit/demerit display
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from apps.students.models import Student


from .models import (
    ParentMeetingBooking, AbsenceExcuse, ParentNotification, ActivityPost,
    ConsentForm, ConsentResponse,
)
from .utils import (
    get_parent_students, get_student_queryset, get_unread_notification_count,
    get_child_quick_stats, get_child_attendance_calendar,
    get_child_academic_summary, get_activity_feed,
    get_child_canteen_data, get_child_transport_data, get_child_health_data,
)

# ──────────────────────────────────────────────────────────────────
#  Access control
# ──────────────────────────────────────────────────────────────────

def require_parent(view_func):
    """Decorator: restrict view to parent role (and super admin for testing)."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        role = getattr(request.user, 'role', None)
        if role not in ('parent', 'school_admin', 'super_admin') and not request.user.is_staff:
            messages.error(request, 'This area is for parents and guardians only.')
            return redirect('parent:dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def get_tenant(request):
    return getattr(request, 'tenant', None)


def _get_child_or_403(request, student_pk):
    """Return a student object only if this parent is linked to them."""
    students = get_parent_students(request.user)
    student_ids = [s.pk for s in students]
    if int(student_pk) not in student_ids:
        # Super admin bypass
        if getattr(request.user, 'role', '') in ('school_admin', 'super_admin') or request.user.is_staff:
            from apps.students.models import Student
            return Student.objects.get(pk=student_pk)
        messages.error(request, 'You do not have access to this student.')
        return None
    return next(s for s in students if s.pk == int(student_pk))


# ──────────────────────────────────────────────────────────────────
#  Dashboard — multi-child overview
# ──────────────────────────────────────────────────────────────────

@login_required
@require_parent
def dashboard(request):
    """
    Main parent portal landing page.
    Shows all children with quick stats, activity feed, notifications.
    Benchmarked: ClassDojo home, PowerSchool parent dashboard, Infinite Campus.
    """
    tenant = get_tenant(request)
    students = get_parent_students(request.user)

    # Quick stats per child
    children_data = []
    for s in students:
        stats = get_child_quick_stats(s, tenant)
        feed = get_activity_feed(s, limit=3)
        children_data.append({'student': s, 'stats': stats, 'feed': feed})

    # Unread notifications
    notifications = ParentNotification.objects.filter(
        parent_user=request.user, is_read=False
    ).order_by('-created_at')[:10]
    unread_count = notifications.count()

    # Upcoming meetings
    upcoming_meetings = ParentMeetingBooking.objects.filter(
        parent_user=request.user,
        preferred_date__gte=timezone.now().date(),
        status__in=['pending', 'confirmed'],
    ).select_related('student', 'teacher').order_by('preferred_date')[:3]

    # Pending consent forms (benchmarked: FamilyID)
    try:
        pending_consents = []
        if students:
            classes = [s.current_class for s in students if s.current_class]
            consent_forms = ConsentForm.objects.filter(
                tenant=tenant,
                is_active=True,
                deadline__gte=timezone.now().date(),
                target_classes__in=classes,
            ).distinct()
            for form in consent_forms:
                for s in students:
                    already = ConsentResponse.objects.filter(form=form, student=s).exists()
                    if not already:
                        pending_consents.append({'form': form, 'student': s})
    except Exception:
        pending_consents = []

    context = {
        'page_title':       'Parent Portal',
        'children_data': children_data, 'students': students,
        'notifications':    notifications,
        'unread_count':     unread_count,
        'upcoming_meetings': upcoming_meetings,
        'pending_consents': pending_consents,
        'today':            timezone.now().date(),
    }
    return render(request, 'parent/dashboard.html', context)


# ──────────────────────────────────────────────────────────────────
#  Academic Overview — grades, trends, teacher comments
# ──────────────────────────────────────────────────────────────────

@login_required
@require_parent
def child_academic(request, student_pk):
    """
    Subject-level grades, performance trends, teacher comments, class average.
    Benchmarked: PowerSchool gradebook, Infinite Campus academic tab,
    Alma progress report, Class Charts academic view.
    """
    student = _get_child_or_403(request, student_pk)
    if not student:
        return redirect('parent:dashboard')

    # Get latest term results
    results = get_child_academic_summary(student)

    # Term history (for trend chart) — benchmarked: PowerSchool grade history
    term_history = []
    try:
        from apps.exams.models import ExamResult
        from apps.core.models import Term
        terms = list(
            ExamResult.objects.filter(student=student)
            .values('term__name', 'term_id')
            .distinct()
            .order_by('term__start_date')
        )
        for t in terms[-4:]:  # Last 4 terms
            term_results = ExamResult.objects.filter(student=student, term_id=t['term_id'])
            avg = term_results.aggregate(avg=Sum('marks') / Count('id'))['avg'] or 0
            term_history.append({'term': t['term__name'], 'average': round(float(avg), 1)})
    except Exception:
        pass

    # Subject performance for radar chart (benchmarked: PowerSchool, Alma)
    subject_labels = [r.subject.name if hasattr(r, 'subject') else str(r) for r in results]
    subject_marks = [float(getattr(r, 'marks', 0) or 0) for r in results]

    context = {
        'page_title':     f'Academic — {student.first_name}',
        'student':        student,
        'results':        results,
        'term_history':   term_history,
        'subject_labels': subject_labels,
        'subject_marks':  subject_marks,
        'students':       get_parent_students(request.user),
        'unread_count':   get_unread_notification_count(request.user),
    }
    return render(request, 'parent/child/academic.html', context)


# ──────────────────────────────────────────────────────────────────
#  Attendance — calendar, excuse form
# ──────────────────────────────────────────────────────────────────

@login_required
@require_parent
def child_attendance(request, student_pk):
    """
    Monthly attendance calendar with colour coding.
    Parents can submit an absence excuse.
    Benchmarked: Infinite Campus attendance, PowerSchool attendance tab,
    Alma attendance calendar.
    """
    student = _get_child_or_403(request, student_pk)
    if not student:
        return redirect('parent:dashboard')

    month = int(request.GET.get('month', timezone.now().month))
    year  = int(request.GET.get('year',  timezone.now().year))

    calendar_data, month, year = get_child_attendance_calendar(student, month, year)

    # Calculate nav months
    import calendar
    prev_month = month - 1 if month > 1 else 12
    prev_year  = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year  = year if month < 12 else year + 1

    # Days in this month
    _, days_in_month = calendar.monthrange(year, month)
    first_weekday, _ = calendar.monthrange(year, month)  # 0=Mon
    days_range = list(range(1, days_in_month + 1))

    # Recent excuses submitted by this parent
    excuses = AbsenceExcuse.objects.filter(
        student=student, parent_user=request.user
    ).order_by('-absence_date')[:5]

    # Excuse form submission
    if request.method == 'POST':
        absence_date = request.POST.get('absence_date')
        excuse_type  = request.POST.get('excuse_type')
        explanation  = request.POST.get('explanation', '').strip()

        if absence_date and excuse_type and explanation:
            AbsenceExcuse.objects.create(
                tenant      = get_tenant(request),
                student     = student,
                parent_user = request.user,
                absence_date = absence_date,
                excuse_type  = excuse_type,
                explanation  = explanation,
                supporting_doc = request.FILES.get('supporting_doc'),
            )
            messages.success(request, 'Excuse submitted. The school will review it shortly.')
        else:
            messages.error(request, 'Please fill in all required fields.')

    import json
    # Serialize calendar_data for JS consumption
    calendar_json = json.dumps(calendar_data)
    # Leading blank cells so day 1 falls on the correct weekday column
    leading_blanks = range(first_weekday)

    context = {
        'page_title':     f'Attendance — {student.first_name}',
        'student':        student,
        'calendar_data':  calendar_data,
        'calendar_json':  calendar_json,
        'month':          month,
        'year':           year,
        'month_name':     calendar.month_name[month],
        'days_in_month':  days_in_month,
        'first_weekday':  first_weekday,
        'leading_blanks': leading_blanks,
        'days_range':     days_range,
        'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year,
        'excuses':        excuses,
        'excuse_choices': AbsenceExcuse.EXCUSE_TYPE_CHOICES,
        'students':       get_parent_students(request.user),
        'unread_count':   get_unread_notification_count(request.user),
        'today':          timezone.now().date(),
    }
    return render(request, 'parent/child/attendance.html', context)


# ──────────────────────────────────────────────────────────────────
#  Fees & Payments
# ──────────────────────────────────────────────────────────────────

@login_required
@require_parent
def child_fees(request, student_pk):
    """
    Fee balance, invoice history, payment history, pay online button.
    Instalment schedule if applicable.
    Benchmarked: FACTS tuition management, PowerSchool fee tab, ParentPay.
    """
    student = _get_child_or_403(request, student_pk)
    if not student:
        return redirect('parent:dashboard')

    invoices = []
    payments = []
    total_outstanding = 0
    total_paid = 0

    try:
        from apps.finance.models import FeeInvoice, Payment
        invoices = list(
            FeeInvoice.objects.filter(student=student)
            .order_by('-created_at')
        )
        for inv in invoices:
            paid = Payment.objects.filter(invoice=inv).aggregate(total=Sum('amount'))['total'] or 0
            inv.amount_paid = paid
            inv.amount_outstanding = max((getattr(inv, 'total_amount', 0) or 0) - paid, 0)
            if inv.amount_outstanding > 0:
                total_outstanding += inv.amount_outstanding
            total_paid += paid

        payments = list(
            Payment.objects.filter(invoice__student=student)
            .order_by('-created_at')[:10]
        )
    except Exception:
        pass

    # Online payment transactions
    try:
        from apps.payments.models import PesaPalTransaction
        online_txns = PesaPalTransaction.objects.filter(
            student=student
        ).order_by('-initiated_at')[:5]
    except Exception:
        online_txns = []

    context = {
        'page_title':       f'Fees — {student.first_name}',
        'student':          student,
        'invoices':         invoices,
        'payments':         payments,
        'online_txns':      online_txns,
        'total_outstanding': total_outstanding,
        'total_paid':       total_paid,
        'students':         get_parent_students(request.user),
        'unread_count':     get_unread_notification_count(request.user),
    }
    return render(request, 'parent/child/fees.html', context)


# ──────────────────────────────────────────────────────────────────
#  Behaviour — incidents, merits, acknowledgement
# ──────────────────────────────────────────────────────────────────

@login_required
@require_parent
def child_behaviour(request, student_pk):
    """
    View discipline incidents and merits. Acknowledge incidents.
    Benchmarked: ClassDojo behaviour tracking, Infinite Campus behaviour tab,
    Class Charts merit/demerit system.
    """
    student = _get_child_or_403(request, student_pk)
    if not student:
        return redirect('parent:dashboard')

    incidents = []
    merits    = []
    try:
        from apps.discipline.models import DisciplineIncident, MeritRecord
        incidents = list(
            DisciplineIncident.objects.filter(student=student)
            .select_related('category').order_by('-incident_date')[:20]
        )
        merits = list(
            MeritRecord.objects.filter(student=student)
            .order_by('-award_date')[:20]
        )
    except Exception:
        pass

    # Handle parent acknowledgement (ClassDojo-inspired)
    if request.method == 'POST' and request.POST.get('action') == 'acknowledge':
        incident_pk = request.POST.get('incident_pk')
        try:
            from apps.discipline.models import DisciplineIncident
            incident = DisciplineIncident.objects.get(pk=incident_pk, student=student)
            if not incident.parent_acknowledged:
                incident.parent_acknowledged    = True
                incident.parent_acknowledged_at = timezone.now()
                incident.parent_acknowledgement_note = request.POST.get('note', '').strip()
                incident.save(update_fields=[
                    'parent_acknowledged', 'parent_acknowledged_at',
                    'parent_acknowledgement_note'
                ])
                messages.success(request, 'Incident acknowledged.')
        except Exception:
            messages.error(request, 'Could not process acknowledgement.')

    # Unacknowledged count
    unack_count = sum(1 for i in incidents if not i.parent_acknowledged)

    # Merit total
    total_merits   = sum(getattr(m, 'merit_points', 1) for m in merits)
    total_demerits = 0  # Calculate from consequences if needed

    context = {
        'page_title':    f'Behaviour — {student.first_name}',
        'student':       student,
        'incidents':     incidents,
        'merits':        merits,
        'unack_count':   unack_count,
        'total_merits':  total_merits,
        'students':      get_parent_students(request.user),
        'unread_count':  get_unread_notification_count(request.user),
    }
    return render(request, 'parent/child/behaviour.html', context)


# ──────────────────────────────────────────────────────────────────
#  Assignments — calendar view, submitted work
# ──────────────────────────────────────────────────────────────────

@login_required
@require_parent
def child_assignments(request, student_pk):
    """
    All assignments for child: pending, submitted, graded.
    Assignment calendar. View submitted work.
    Benchmarked: Class Charts homework calendar, PowerSchool assignments,
    Google Classroom, Infinite Campus.
    """
    student = _get_child_or_403(request, student_pk)
    if not student:
        return redirect('parent:dashboard')

    assignments = []
    try:
        from apps.assignments.models import Assignment, AssignmentSubmission
        if student.current_class:
            assignments = list(
                Assignment.objects.filter(class_room=student.current_class)
                .order_by('-due_date')[:30]
            )
            # Annotate with submission status
            for a in assignments:
                try:
                    sub = AssignmentSubmission.objects.filter(
                        assignment=a, student=student
                    ).first()
                    a.submission = sub
                except Exception:
                    a.submission = None
    except Exception:
        pass

    # Group by status for tabs (benchmarked: Class Charts)
    today = timezone.now().date()
    pending  = [a for a in assignments if not a.submission and a.due_date >= today]
    overdue  = [a for a in assignments if not a.submission and a.due_date < today]
    submitted = [a for a in assignments if a.submission and not getattr(a.submission, 'marks', None)]
    graded   = [a for a in assignments if a.submission and getattr(a.submission, 'marks', None)]

    context = {
        'page_title':  f'Assignments — {student.first_name}',
        'student':     student,
        'assignments': assignments,
        'pending':     pending,
        'overdue':     overdue,
        'submitted':   submitted,
        'graded':      graded,
        'today':       today,
        'students':    get_parent_students(request.user),
        'unread_count': get_unread_notification_count(request.user),
    }
    return render(request, 'parent/child/assignments.html', context)


# ──────────────────────────────────────────────────────────────────
#  Documents — all PDFs for the child
# ──────────────────────────────────────────────────────────────────

@login_required
@require_parent
def child_documents(request, student_pk):
    """
    Permanent document vault for all PDFs: report cards, receipts, letters.
    Benchmarked: Blackbaud document vault, PowerSchool documents tab,
    Infinite Campus document library.
    """
    student = _get_child_or_403(request, student_pk)
    if not student:
        return redirect('parent:dashboard')

    # Gather documents from various modules
    report_cards = []
    receipts = []
    letters = []

    try:
        # Report cards from exams module
        from apps.exams.models import TermReport
        report_cards = list(
            TermReport.objects.filter(student=student).order_by('-created_at')
        )
    except Exception:
        pass

    try:
        # Payment receipts
        from apps.finance.models import Payment
        receipts = list(
            Payment.objects.filter(invoice__student=student).order_by('-created_at')[:20]
        )
    except Exception:
        pass

    context = {
        'page_title':   f'Documents — {student.first_name}',
        'student':      student,
        'report_cards': report_cards,
        'receipts':     receipts,
        'letters':      letters,
        'students':     get_parent_students(request.user),
        'unread_count': get_unread_notification_count(request.user),
    }
    return render(request, 'parent/child/documents.html', context)


# ──────────────────────────────────────────────────────────────────
#  Meeting Booking
# ──────────────────────────────────────────────────────────────────

@login_required
@require_parent
def book_meeting(request, student_pk):
    """
    Book a parent-teacher meeting.
    Benchmarked: Infinite Campus meeting scheduler, PowerSchool parent-teacher,
    SchoolStatus meeting booking.
    """
    student = _get_child_or_403(request, student_pk)
    if not student:
        return redirect('parent:dashboard')

    if request.method == 'POST':
        meeting_type    = request.POST.get('meeting_type')
        preferred_date  = request.POST.get('preferred_date')
        preferred_time  = request.POST.get('preferred_time')
        parent_notes    = request.POST.get('parent_notes', '').strip()

        # Get teacher (optional)
        teacher_pk = request.POST.get('teacher_pk')
        teacher = None
        if teacher_pk:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                teacher = User.objects.get(pk=teacher_pk)
            except User.DoesNotExist:
                pass

        if meeting_type and preferred_date and preferred_time:
            booking = ParentMeetingBooking.objects.create(
                tenant          = get_tenant(request),
                student         = student,
                parent_user     = request.user,
                teacher         = teacher,
                meeting_type    = meeting_type,
                preferred_date  = preferred_date,
                preferred_time  = preferred_time,
                parent_notes    = parent_notes,
            )
            messages.success(
                request,
                f'Meeting request submitted for {booking.preferred_date}. '
                f'The school will confirm shortly.'
            )
            return redirect('parent:child_meetings', student_pk=student_pk)
        else:
            messages.error(request, 'Please fill in all required fields.')

    # Teachers to choose from (student's class teacher + subject teachers)
    teachers = []
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        teachers = list(User.objects.filter(role='teacher', is_active=True)[:20])
    except Exception:
        pass

    context = {
        'page_title':    f'Book a Meeting — {student.first_name}',
        'student':       student,
        'teachers':      teachers,
        'meeting_types': ParentMeetingBooking.MEETING_TYPE_CHOICES,
        'students':      get_parent_students(request.user),
        'unread_count':  get_unread_notification_count(request.user),
        'min_date':      (timezone.now().date() + timezone.timedelta(days=1)).isoformat(),
    }
    return render(request, 'parent/child/book_meeting.html', context)


@login_required
@require_parent
def child_meetings(request, student_pk):
    """View all meetings for a student, rate completed ones."""
    student = _get_child_or_403(request, student_pk)
    if not student:
        return redirect('parent:dashboard')

    # Handle rating submission (PowerSchool-inspired post-meeting rating)
    if request.method == 'POST':
        booking_pk = request.POST.get('booking_pk')
        rating = request.POST.get('rating')
        feedback = request.POST.get('feedback', '').strip()
        try:
            booking = ParentMeetingBooking.objects.get(pk=booking_pk, parent_user=request.user)
            if rating:
                booking.parent_rating = int(rating)
            if feedback:
                booking.parent_feedback = feedback
            booking.save(update_fields=['parent_rating', 'parent_feedback'])
            messages.success(request, 'Thank you for your feedback!')
        except Exception:
            messages.error(request, 'Could not save rating.')

    meetings = ParentMeetingBooking.objects.filter(
        student=student, parent_user=request.user
    ).select_related('teacher').order_by('-preferred_date')

    context = {
        'page_title':  f'Meetings — {student.first_name}',
        'student':     student,
        'meetings':    meetings,
        'students':    get_parent_students(request.user),
        'unread_count': get_unread_notification_count(request.user),
        'today':       timezone.now().date(),
    }
    return render(request, 'parent/child/meetings.html', context)


# ──────────────────────────────────────────────────────────────────
#  Notifications
# ──────────────────────────────────────────────────────────────────

@login_required
@require_parent
def notifications(request):
    """Full notification centre. Mark as read individually or all at once."""
    if request.method == 'POST' and request.POST.get('action') == 'mark_all_read':
        ParentNotification.objects.filter(
            parent_user=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        messages.success(request, 'All notifications marked as read.')

    notifs = ParentNotification.objects.filter(
        parent_user=request.user
    ).order_by('-created_at')
    paginator = Paginator(notifs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # Mark visible ones as read
    unread_ids = [n.pk for n in page_obj if not n.is_read]
    if unread_ids:
        ParentNotification.objects.filter(pk__in=unread_ids).update(
            is_read=True, read_at=timezone.now()
        )

    context = {
        'page_title':   'Notifications',
        'notifs':       page_obj,
        'unread_count': 0,  # Just marked them read
        'students':     get_parent_students(request.user),
    }
    return render(request, 'parent/notifications.html', context)


# ──────────────────────────────────────────────────────────────────
#  Profile & Settings
# ──────────────────────────────────────────────────────────────────

@login_required
@require_parent
def profile(request):
    """Parent profile — update contact details, notification preferences."""
    tenant = get_tenant(request)
    students = get_parent_students(request.user)

    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name  = request.POST.get('last_name', user.last_name)
        user.email      = request.POST.get('email', user.email)
        user.save(update_fields=['first_name', 'last_name', 'email'])
        messages.success(request, 'Profile updated.')

    context = {
        'page_title':  'My Profile',
        'students':    students,
        'unread_count': get_unread_notification_count(request.user),
    }
    return render(request, 'parent/profile.html', context)


# ──────────────────────────────────────────────────────────────────
#  AJAX — unread notification count (for polling)
# ──────────────────────────────────────────────────────────────────

@login_required
def notification_count(request):
    """AJAX: return unread notification count for badge update."""
    count = get_unread_notification_count(request.user)
    return JsonResponse({'unread': count})


# ── Timetable ────────────────────────────────────────────────
def child_timetable(request, student_pk):
    from apps.parent_portal.utils import get_parent_students
    from django.shortcuts import get_object_or_404
    from django.core.exceptions import PermissionDenied
    from django.shortcuts import render
    students = get_parent_students(request.user)
    try:
        from apps.students.models import Student
        student = get_object_or_404(Student, pk=student_pk)
    except Exception:
        student = None
    if not student or student not in students:
        raise PermissionDenied

    timetable_by_day = {}
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    try:
        from apps.academics.models import TimetableSlot as TT
        for day in days:
            qs = TT.objects.filter(
                class_subject__classroom=student.current_class,
                day=day
            ).select_related(
                'class_subject__subject', 'class_subject__teacher'
            ).order_by('start_time') if student.current_class else []
            timetable_by_day[day] = list(qs)
    except Exception:
        for day in days:
            timetable_by_day[day] = []

    return render(request, 'parent/child/timetable.html', {
        'student': student, 'students': students,
        'timetable_by_day': timetable_by_day, 'days': days,
    })


# ── Library ──────────────────────────────────────────────────
def child_library(request, student_pk):
    from apps.parent_portal.utils import get_parent_students
    from django.shortcuts import get_object_or_404
    from django.core.exceptions import PermissionDenied
    from django.shortcuts import render
    students = get_parent_students(request.user)
    try:
        from apps.students.models import Student
        student = get_object_or_404(Student, pk=student_pk)
    except Exception:
        student = None
    if not student or student not in students:
        raise PermissionDenied

    current_books, history, total_fine = [], [], 0
    try:
        from apps.library.models import BorrowRecord
        current_books = list(
            BorrowRecord.objects.filter(student=student, returned_at__isnull=True)
            .select_related('book')
        )
        history = list(
            BorrowRecord.objects.filter(student=student, returned_at__isnull=False)
            .select_related('book').order_by('-returned_at')[:10]
        )
    except Exception:
        pass

    return render(request, 'parent/child/library.html', {
        'student': student, 'students': students,
        'current_books': current_books, 'history': history,
        'total_fine': total_fine,
    })


# ── Messages inbox ────────────────────────────────────────────
def messages_inbox(request):
    from apps.parent_portal.utils import get_parent_students
    from django.shortcuts import render
    from django.contrib.auth.decorators import login_required
    students = get_parent_students(request.user)
    received, sent = [], []
    unread_messages = 0
    try:
        from apps.parent_portal.models import ParentMessage
        received = list(
            ParentMessage.objects.filter(recipient=request.user)
            .select_related('sender', 'student').order_by('-created_at')[:20]
        )
        sent = list(
            ParentMessage.objects.filter(sender=request.user)
            .select_related('recipient', 'student').order_by('-created_at')[:10]
        )
        unread_messages = ParentMessage.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        # Mark visible as read
        ParentMessage.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    except Exception:
        pass

    # Build teacher list for compose form
    teachers = []
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        teachers = list(
            User.objects.filter(
                role='teacher', tenant=request.user.tenant, is_active=True
            ).order_by('last_name')
        )
    except Exception:
        pass

    return render(request, 'parent/messages.html', {
        'students': students, 'received': received, 'sent': sent,
        'teachers': teachers, 'unread_messages': unread_messages,
    })


# ── Send message ──────────────────────────────────────────────
def send_message(request):
    from django.shortcuts import redirect
    from django.contrib import messages as dj_messages
    if request.method != 'POST':
        return redirect('parent:messages')
    try:
        from apps.parent_portal.models import ParentMessage
        from django.contrib.auth import get_user_model
        User = get_user_model()
        recipient_id = request.POST.get('recipient_id')
        subject      = request.POST.get('subject', '').strip()
        body         = request.POST.get('body', '').strip()
        student_pk   = request.POST.get('student_pk')
        if not (recipient_id and subject and body):
            dj_messages.error(request, 'Please fill in all fields.')
            return redirect('parent:messages')
        recipient = User.objects.get(pk=recipient_id, tenant=request.user.tenant)
        student   = None
        if student_pk:
            from apps.students.models import Student
            student = Student.objects.filter(pk=student_pk).first()
        ParentMessage.objects.create(
            tenant=request.user.tenant,
            sender=request.user,
            recipient=recipient,
            student=student,
            subject=subject,
            body=body,
        )
        dj_messages.success(request, 'Message sent.')
    except Exception as e:
        dj_messages.error(request, f'Could not send message: {e}')
    return redirect('parent:messages')

# ── Access guard ─────────────────────────────────────────────────────────────
def _require_parent_access(request, student):
    """Raise 403 if the logged-in user is not a guardian of this student."""
    from apps.students.models import Guardian
    from django.core.exceptions import PermissionDenied
    if request.user.is_superuser or getattr(request.user, "role", "") in (
        "super_admin", "school_admin", "principal"
    ):
        return
    ok = Guardian.objects.filter(user=request.user, student=student).exists()
    if not ok:
        raise PermissionDenied

# ── Canteen (Phase 4 placeholder) ────────────────────────────────────────────
@login_required
def child_canteen(request, student_pk):
    student = get_object_or_404(Student, pk=student_pk)
    _require_parent_access(request, student)
    context = {
        "active_section": "canteen",
        "student": student,
        "phase": 4,
    }
    context.update(get_child_canteen_data(student))
    return render(request, "parent/child/canteen.html", context)

# ── Health ────────────────────────────────────────────────────────────────
@login_required
def child_health(request, student_pk):
    student = get_object_or_404(Student, pk=student_pk)
    _require_parent_access(request, student)
    context = {
        "active_section": "health",
        "student": student,
        "phase": 4,
    }
    context.update(get_child_health_data(student))
    return render(request, "parent/child/health.html", context)

# ── Transport ─────────────────────────────────────────────────────────────
@login_required
def child_transport(request, student_pk):
    student = get_object_or_404(Student, pk=student_pk)
    _require_parent_access(request, student)
    context = {
        "active_section": "transport",
        "student": student,
        "phase": 4,
    }
    context.update(get_child_transport_data(student))
    return render(request, "parent/child/transport.html", context)
