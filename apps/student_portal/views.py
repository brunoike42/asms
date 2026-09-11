"""

ASMS — Student Portal Views

Phase 3



All views require:

  - @login_required              (Django built-in)

  - @student_required            (Phase 1 custom decorator in accounts/decorators.py)



Data consumed from Phase 1 & 2 apps:

  students        ? Student, Class, Subject

  attendance      ? AttendanceRecord

  finance         ? FeeInvoice, Payment

  academics       ? Term, AcademicYear, Timetable

  exams           ? ExamResult, ReportCard

  assignments     ? Assignment, Submission

  lms             ? Course, Resource

  library         ? Book, BorrowingRecord

  transport       ? StudentTransport

  canteen         ? MealAccount, MealTransaction

  discipline      ? DisciplineIncident, Merit, Demerit

  communication   ? Announcement, StudentMessage

  documents       ? StudentDocument



New models (Phase 3 portal/models.py):

  TermEnrollment, CourseUnitRegistration, ExamPermit,

  ExamAppeal, ProgramChangeRequest, LeaveOfAbsenceRequest,

  AcademicClearanceItem, StudentClearance, AcademicCalendarEvent,

  PortalNotification

"""

from django.shortcuts               import render, redirect, get_object_or_404

from django.contrib.auth.decorators import login_required

from django.contrib                 import messages

from django.http                    import JsonResponse, HttpResponse

from django.utils                   import timezone

from django.db.models               import Avg, Count, Sum, Q

from django.views.decorators.http   import require_POST

from django.core.paginator          import Paginator

from django.conf import settings

# Phase 1 & 2 app models

from apps.students.models      import Student

from apps.attendance.models    import AttendanceRecord

from apps.finance.models       import FeeInvoice, Payment

from apps.core.models          import Term, AcademicYear

from apps.academics.models     import Subject, ClassSubject, TimetableSlot

from apps.students.models      import Student, ClassRoom

from apps.exams.models         import ExamResult, TermReport as ReportCard

from apps.assignments.models   import Assignment, AssignmentSubmission as Submission

from apps.library.models       import Book, BorrowRecord as BorrowingRecord

from apps.discipline.models    import DisciplineIncident, MeritRecord as Merit

Demerit = None  # no separate demerit model — likely fnewed into DisciplineIncident

from apps.communication.models import Announcement

StudentMessage = None  # no direct-messaging model exists yet in Phase 1/2 — only SMSLog and Announcement

# Phase 4+ apps — not yet built, stubbed safely

try:

    from apps.transport.models import StudentTransport

except ImportError:

    StudentTransport = None



try:

    from apps.canteen.models import MealAccount, MealTransaction

except ImportError:

    MealAccount = None

    MealTransaction = None



try:

    from apps.documents.models import StudentDocument

except ImportError:

    StudentDocument = None

    

# Phase 3 portal models

from .models import (

    TermEnrollment, CourseUnitRegistration, ExamPermit,

    ExamAppeal, ProgramChangeRequest, LeaveOfAbsenceRequest,

    AcademicClearanceItem, StudentClearance, StudentClearanceItemStatus,

    AcademicCalendarEvent, PortalNotification,

)

from .forms import (

    TermEnrollmentForm, ExamAppealForm, ProgramChangeRequestForm,

    LeaveOfAbsenceRequestForm, ProfileUpdateForm, PasswordChangeForm,

    ExcuseAbsenceForm,

)





# -----------------------------------------------------------------------------

# Decorator shorthand — wraps login_required + role check

# -----------------------------------------------------------------------------

def student_required(view_func):

    """Ensures the logged-in user has a Student record."""

    from functools import wraps

    from django.contrib.auth import logout as auth_logout



    @wraps(view_func)

    def _wrapped(request, *args, **kwargs):

        if not request.user.is_authenticated:

            return redirect(settings.LOGIN_URL)

        try:

            request.student = request.user.student_profile

        except Student.DoesNotExist:

            auth_logout(request)          # ? kills the session first

            messages.error(

                request,

                "Student account not found. Contact your school administrator."

            )

            return redirect('accounts:login')   # now login shows the form, no loop

        return view_func(request, *args, **kwargs)

    return _wrapped





# -----------------------------------------------------------------------------

# Helper: get current term

# -----------------------------------------------------------------------------

def _current_term():

    today = timezone.now().date()

    return Term.objects.filter(start_date__lte=today, end_date__gte=today).first()





def _current_year():

    today = timezone.now().date()

    return AcademicYear.objects.filter(start_date__lte=today, end_date__gte=today).first()





# =============================================================================

# 1. DASHBOARD

# =============================================================================

@student_required

def dashboard(request):

    student = request.student

    term    = _current_term()



    # Attendance

    attendance_qs = AttendanceRecord.objects.filter(student=student, date__range=(term.start_date, term.end_date)) if term else []

    total_days    = len(attendance_qs)

    present_days  = sum(1 for r in attendance_qs if r.status == 'present')

    attendance_pct = round((present_days / total_days * 100) if total_days else 0, 1)



    # Pending assignments

    pending_assignments = Assignment.objects.filter(

        class_subject__classroom=student.current_class,

        due_date__gte=timezone.now().date(),

        due_date__lte=term.end_date,

    ).exclude(

        submissions__student=student,

            ).count() if term else 0



    # Fee balance

    invoices = FeeInvoice.objects.filter(student=student, term=term) if term else []

    total_invoiced = sum(inv.total_amount for inv in invoices)

    total_paid     = Payment.objects.filter(

        invoice__in=invoices

    ).aggregate(s=Sum('amount'))['s'] or 0

    fee_balance = total_invoiced - total_paid



    # Today's timetable

    today_timetable = []

    if term:

        from apps.academics.models import TimetableSlot

        today_timetable = TimetableSlot.objects.filter(

            class_subject__classroom=student.current_class,

            day=timezone.now().weekday(),   # 0=Mon

        ).select_related('class_subject__subject', 'class_subject__teacher').order_by('start_time')



    # Unread notifications

    unread_notif_count = PortalNotification.objects.filter(student=student, is_read=False).count()



    # Recent results (last 5)

    recent_results = ExamResult.objects.filter(

        student=student

    ).select_related('exam__subject', 'exam__term').order_by('-exam__term__end_date')[:5]



    # Upcoming events (next 7 days)

    upcoming_events = AcademicCalendarEvent.objects.filter(

        start_date__gte=timezone.now().date(),

        start_date__lte=timezone.now().date() + timezone.timedelta(days=7),

        is_published=True,

    ).order_by('start_date')[:5]



    # Enrollment status for current term

    enrollment = TermEnrollment.objects.filter(student=student, term=term).first() if term else None



    context = {

        'student':            student,

        'term':               term,

        'attendance_pct':     attendance_pct,

        'pending_assignments': pending_assignments,

        'fee_balance':        fee_balance,

        'today_timetable':    today_timetable,

        'unread_notif_count': unread_notif_count,

        'recent_results':     recent_results,

        'upcoming_events':    upcoming_events,

        'enrollment':         enrollment,

        'page_title':         'Dashboard',

    }

    return render(request, 'student_portal/dashboard.html', context)





# =============================================================================

# 2. MY CLASSES

# =============================================================================

@student_required

def my_classes(request):

    student = request.student

    term    = _current_term()



    from apps.academics.models import ClassSubject

    class_subjects = ClassSubject.objects.filter(

        classroom=student.current_class

    ).select_related('subject', 'teacher', 'term').order_by('subject__name')



    context = {

        'student':       student,

        'current_class': student.current_class,

        'class_subjects': class_subjects,

        'classmates':    Student.objects.filter(

            enrollments__classroom=student.current_class,

            enrollments__is_active=True

        ).exclude(id=student.id).distinct().order_by('user__last_name')[:50],

        'page_title':    'My Classes',

    }

    return render(request, 'student_portal/classes.html', context)





# =============================================================================

# 3. TIMETABLE

# =============================================================================

@student_required

def timetable(request):

    from apps.academics.models import TimetableSlot

    student = request.student

    entries = TimetableSlot.objects.filter(

        class_subject__classroom=student.current_class

    ).select_related('class_subject__subject', 'class_subject__teacher').order_by('day', 'start_time')



    # Group by day

    days = {i: [] for i in range(5)}   # Mon–Fri (0–4)

    for entry in entries:

        days[entry.day].append(entry)



    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']



    context = {

        'student':          student,

        'days':             days,

        'day_names_indexed': list(enumerate(day_names)),

        'today_idx':        timezone.now().weekday(),

        'page_title':       'My Timetable',

    }

    return render(request, 'student_portal/timetable.html', context)





# =============================================================================

# 4. ASSIGNMENTS

# =============================================================================

@student_required

def assignments(request):

    student     = request.student

    term        = _current_term()

    filter_tab  = request.GET.get('tab', 'pending')   # pending | submitted | graded



    base_qs = Assignment.objects.filter(

        class_subject__classroom=student.current_class

    ).order_by('-due_date')



    if filter_tab == 'pending':

       qs = base_qs.exclude(submissions__student=student)

       

    elif filter_tab == 'submitted':

       qs = base_qs.filter(

    submissions__student=student,

    submissions__marks__isnull=True

)

    else:   # graded

        qs = base_qs.filter(

            submissions__student=student, submissions__grade__isnull=False

        )



    paginator = Paginator(qs, 15)

    page_obj  = paginator.get_page(request.GET.get('page'))



    # Pre-fetch student's submissions for these assignments

    submission_map = {

        s.assignment_id: s

        for s in Submission.objects.filter(student=student, assignment__in=qs)

    }



    context = {

        'student':        student,

        'page_obj':       page_obj,

        'submission_map': submission_map,

        'filter_tab':     filter_tab,

        'today':          timezone.now().date(),

        'page_title':     'Assignments',

    }

    return render(request, 'student_portal/assignments.html', context)





@student_required

def assignment_detail(request, assignment_id):

    student    = request.student

    assignment = get_object_or_404(Assignment, id=assignment_id, class_subject__classroom=student.current_class)

    submission = Submission.objects.filter(student=student, assignment=assignment).first()



    if request.method == 'POST' and not submission:

        # Handle new submission

        text_response = request.POST.get('text_response', '')

        uploaded_file = request.FILES.get('file')

        sub = Submission.objects.create(

            student=student, assignment=assignment,

            content=text_response,

        )

        if uploaded_file:

            from utils.cloudinary import upload_file

            sub.file = upload_file(uploaded_file, fnewer='submissions')

            sub.save()

        messages.success(request, "Assignment submitted successfully.")

        return redirect('student_portal:assignments')



    context = {

        'student':    student,

        'assignment': assignment,

        'submission': submission,

        'today':      timezone.now().date(),

        'page_title': assignment.title,

    }

    return render(request, 'student_portal/assignment_detail.html', context)





# =============================================================================

# 5. QUIZZES & TESTS

# =============================================================================

@student_required

def quizzes(request):

    from apps.lms.models import Quiz, QuizAttempt

    student   = request.student

    term      = _current_term()

    all_quizzes = Quiz.objects.filter(

        class_subject__classroom=student.current_class, is_published=True

    ).order_by('-start_date')



    attempt_map = {

        a.quiz_id: a

        for a in QuizAttempt.objects.filter(student=student, quiz__in=all_quizzes)

    }



    context = {

        'student':     student,

        'quizzes':     all_quizzes,

        'attempt_map': attempt_map,

        'page_title':  'Quizzes & Tests',

    }

    return render(request, 'student_portal/quizzes.html', context)





# =============================================================================

# 6. MY RESULTS

# =============================================================================

@student_required

def results(request):

    student     = request.student

    term_filter = request.GET.get('term')



    results_qs = ExamResult.objects.filter(

        student=student

    ).select_related('exam__subject', 'exam__term').order_by('-exam__term__end_date', 'exam__subject__name')



    if term_filter:

        results_qs = results_qs.filter(exam__term_id=term_filter)



    # Group by term

    from collections import defaultdict

    results_by_term = defaultdict(list)

    for r in results_qs:

        results_by_term[r.term].append(r)



    terms = Term.objects.filter(

        exams__results__student=student

    ).distinct().order_by('-end_date')



    # Latest report card

    report_card = ReportCard.objects.filter(student=student).order_by('-term__end_date').first()



    context = {

        'student':        student,

        'results_by_term': dict(results_by_term),

        'terms':          terms,

        'term_filter':    term_filter,

        'report_card':    report_card,

        'page_title':     'My Results',

    }

    return render(request, 'student_portal/results.html', context)





# =============================================================================

# 7. TRANSCRIPT  ? NEW — Makerere benchmark

#    Cumulative academic history across all years (vs term-by-term results)

# =============================================================================

@student_required

def transcript(request):

    student = request.student



    all_results = ExamResult.objects.filter(

        student=student

    ).select_related('exam__subject', 'exam__term', 'exam__term__academic_year').order_by(

        'exam__term__academic_year__start_date', 'exam__term__start_date', 'exam__subject__name'

    )



    # Group by academic year ? term

    from collections import defaultdict

    by_year = defaultdict(lambda: defaultdict(list))

    for r in all_results:

        by_year[r.term.academic_year][r.term].append(r)



    context = {

        'student':   student,

        'by_year':   {yr: dict(terms) for yr, terms in by_year.items()},

        'page_title': 'Academic Transcript',

    }

    return render(request, 'student_portal/transcript.html', context)





# =============================================================================

# 8. ATTENDANCE

# =============================================================================

@student_required

def attendance(request):

    student     = request.student

    term        = _current_term()

    month_param = request.GET.get('month')  # YYYY-MM



    qs = AttendanceRecord.objects.filter(student=student)

    if term:

        qs = qs.filter(date__range=(term.start_date, term.end_date))

    if month_param:

        year, month = map(int, month_param.split('-'))

        qs = qs.filter(date__year=year, date__month=month)



    records = qs.order_by('date')



    total      = records.count()

    present    = records.filter(status='present').count()

    absent     = records.filter(status='absent').count()

    late       = records.filter(status='late').count()

    att_pct    = round((present / total * 100) if total else 0, 1)



    context = {

        'student':   student,

        'records':   records,

        'total':     total,

        'present':   present,

        'absent':    absent,

        'late':      late,

        'att_pct':   att_pct,

        'term':      term,

        'page_title': 'My Attendance',

    }

    return render(request, 'student_portal/attendance.html', context)





@student_required

def excuse_absence(request):

    """Student submits an absence excuse request."""

    if request.method == 'POST':

        form = ExcuseAbsenceForm(request.POST, request.FILES)

        if form.is_valid():

            # In a real impl: create AbsenceExcuse record, notify class teacher

            messages.success(request, "Absence excuse submitted. Your class teacher will review it.")

            return redirect('student_portal:attendance')

    else:

        form = ExcuseAbsenceForm()

    return render(request, 'student_portal/excuse_absence.html', {'form': form, 'page_title': 'Submit Excuse'})





# =============================================================================

# 9. FEE ACCOUNT

# =============================================================================

@student_required

def fee_account(request):

    student    = request.student

    invoices   = FeeInvoice.objects.filter(student=student).select_related('term').order_by('-created_at')

    payments   = Payment.objects.filter(invoice__student=student).order_by('-created_at')



    total_billed = invoices.aggregate(s=Sum('total_amount'))['s'] or 0

    total_paid   = payments.aggregate(s=Sum('amount'))['s'] or 0

    balance      = total_billed - total_paid



    context = {

        'student':     student,

        'invoices':    invoices,

        'payments':    payments,

        'total_billed': total_billed,

        'total_paid':  total_paid,

        'balance':     balance,

        'page_title':  'Fee Account',

    }

    return render(request, 'student_portal/fee_account.html', context)





# =============================================================================

# 10. LIBRARY

# =============================================================================

@student_required

def library(request):

    student   = request.student

    tab       = request.GET.get('tab', 'borrowed')



    borrowed  = BorrowingRecord.objects.filter(

        student=student, return_date__isnull=True

    ).select_related('book').order_by('due_date')



    history   = BorrowingRecord.objects.filter(

        student=student, return_date__isnull=False

    ).select_related('book').order_by('-return_date')[:20]



    query     = request.GET.get('q', '')

    catalogue = Book.objects.filter(is_active=True)

    if query:

        catalogue = catalogue.filter(

            Q(title__icontains=query) | Q(author__icontains=query) | Q(isbn__icontains=query)

        )



    context = {

        'student':  student,

        'tab':      tab,

        'borrowed': borrowed,

        'history':  history,

        'catalogue': Paginator(catalogue.order_by('title'), 20).get_page(request.GET.get('page')),

        'query':    query,

        'page_title': 'Library',

    }

    return render(request, 'student_portal/library.html', context)





# =============================================================================

# 11. MEAL ACCOUNT

# =============================================================================

@student_required

def meal_account(request):

    student = request.student

    if MealAccount is None:
        return render(request, 'student_portal/meal_account.html', {
            'student': student, 'meal_account': None,
            'transactions': [], 'weekly_menu': [],
            'page_title': 'Meal Account',
        })
    try:

        meal_acct = MealAccount.objects.get(student=student)

    except MealAccount.DoesNotExist:

        meal_acct = None



    transactions = MealTransaction.objects.filter(

        account__student=student

    ).order_by('-created_at')[:30] if meal_acct else []



    # Weekly menu — sourced from canteen.models.WeeklyMenu if the school has

    # configured one for the current week; otherwise empty (template shows

    # "not yet published").

    weekly_menu = []

    try:

        from canteen.models import WeeklyMenu

        today_idx = timezone.now().weekday()

        menu_qs = WeeklyMenu.objects.filter(

            week_start__lte=timezone.now().date(),

            week_start__gte=timezone.now().date() - timezone.timedelta(days=6),

        ).order_by('day_of_week')

        for entry in menu_qs:

            weekly_menu.append({

                'name':       entry.get_day_of_week_display(),

                'breakfast':  entry.breakfast,

                'lunch':      entry.lunch,

                'snack':      entry.snack,

                'is_today':   entry.day_of_week == today_idx,

            })

    except ImportError:

        pass



    context = {

        'student':      student,

        'meal_account': meal_acct,

        'transactions': transactions,

        'weekly_menu':  weekly_menu,

        'page_title':   'Meal Account',

    }

    return render(request, 'student_portal/meal_account.html', context)





# =============================================================================

# 12. MESSAGES

# =============================================================================

@student_required

def portal_messages(request):

    student = request.student
    if StudentMessage is None:
        if request.method == 'POST':
            messages.error(request, "Messaging is not available yet.")
            return redirect('student_portal:messages')
        paginator = Paginator([], 20)
        page_obj = paginator.get_page(request.GET.get('page'))
        context = {
            'student': student,
            'page_obj': page_obj,
            'page_title': 'Messages',
        }
        return render(request, 'student_portal/messages.html', context)



    if request.method == 'POST':

        subject = request.POST.get('subject', '').strip()

        body    = request.POST.get('body', '').strip()

        if subject and body:

            class_teacher = getattr(student.current_class, 'class_teacher', None)

            if class_teacher and getattr(class_teacher, 'user', None):

                StudentMessage.objects.create(

                    tenant=request.tenant,

                    sender=request.user,

                    recipient_staff=class_teacher,

                    subject=subject,

                    body=body,

                    sent_at=timezone.now(),

                )

                messages.success(request, "Message sent to your class teacher.")

            else:

                messages.warning(request, "No class teacher is assigned to your class yet.")

        else:

            messages.error(request, "Please provide both a subject and a message.")

        return redirect('student_portal:messages')



    inbox   = StudentMessage.objects.filter(

        recipient_student=student

    ).select_related('sender').order_by('-sent_at')



    paginator = Paginator(inbox, 20)

    page_obj  = paginator.get_page(request.GET.get('page'))



    context = {

        'student':  student,

        'page_obj': page_obj,

        'page_title': 'Messages',

    }

    return render(request, 'student_portal/messages.html', context)





@student_required

def message_detail(request, message_id):

    student = request.student
    if StudentMessage is None:
        messages.error(request, "Messaging is not available yet.")
        return redirect('student_portal:messages')

    msg     = get_object_or_404(StudentMessage, id=message_id, recipient_student=student)

    if not msg.is_read:

        msg.is_read   = True

        msg.read_at   = timezone.now()

        msg.save(update_fields=['is_read', 'read_at'])

    return render(request, 'student_portal/message_detail.html', {'message': msg, 'page_title': msg.subject})





# =============================================================================

# 13. NOTICEBOARD

# =============================================================================

@student_required

def noticeboard(request):

    student = request.student

    announcements = Announcement.objects.filter(

        is_published=True,

        publish_date__lte=timezone.now(),

    ).order_by('-publish_date')



    paginator = Paginator(announcements, 10)

    page_obj  = paginator.get_page(request.GET.get('page'))



    context = {

        'student':  student,

        'page_obj': page_obj,

        'page_title': 'Noticeboard',

    }

    return render(request, 'student_portal/noticeboard.html', context)





# =============================================================================

# 14. MY DOCUMENTS

# =============================================================================

@student_required

def my_documents(request):
    student = request.student

    try:
        from apps.documents.models import StudentDocument
        docs = StudentDocument.objects.filter(student=student).order_by('-created_at')
    except ImportError:
        docs = []




    context = {

        'student':    student,

        'documents':  docs,

        'page_title': 'My Documents',

    }

    return render(request, 'student_portal/documents.html', context)





# =============================================================================

# 15. TRANSPORT

# =============================================================================

@student_required

def transport(request):

    student = request.student

    if StudentTransport is None:
        return render(request, 'student_portal/transport.html', {
            'student': student, 'transport_info': None,
            'page_title': 'Transport',
        })
    try:

        transport_info = StudentTransport.objects.select_related(

            'route', 'bus', 'stop'

        ).get(student=student)

    except StudentTransport.DoesNotExist:

        transport_info = None



    context = {

        'student':        student,

        'transport_info': transport_info,

        'page_title':     'Transport',

    }

    return render(request, 'student_portal/transport.html', context)





# =============================================================================

# 16. MY MERITS

# =============================================================================

@student_required
@student_required
def merits(request):
    student = request.student
    term    = _current_term()
    merit_records = Merit.objects.filter(student=student).order_by('-award_date')
    if term:
        merit_records = merit_records.filter(term=term)
    merit_total = merit_records.aggregate(s=Sum('merit_points'))['s'] or 0

    if Demerit is None:
        demerit_records = []
        demerit_total = 0
    else:
        demerit_records = Demerit.objects.filter(student=student).order_by('-award_date')
        if term:
            demerit_records = demerit_records.filter(term=term)
        demerit_total = demerit_records.aggregate(s=Sum('points'))['s'] or 0

    incidents = DisciplineIncident.objects.filter(student=student).order_by('-incident_date')[:10]
    net_balance = merit_total - demerit_total
    context = {
        'student':      student,
        'merit_records': merit_records,
        'demerit_records': demerit_records,
        'incidents':    incidents,
        'merit_total':  merit_total,
        'demerit_total': demerit_total,
        'net_balance':  net_balance,
        'page_title':   'My Merits',
    }
    return render(request, 'student_portal/merits.html', context)





# =============================================================================

# 17. ACADEMIC CALENDAR  ? NEW — Makerere benchmark

# =============================================================================

@student_required

def academic_calendar(request):

    student = request.student

    year    = _current_year()



    events = AcademicCalendarEvent.objects.filter(

        is_published=True

    ).filter(

        Q(audience='all') |

        Q(audience=request.tenant.school_type) if hasattr(request, 'tenant') else Q()

    ).order_by('start_date')



    if year:

        events = events.filter(academic_year=year)



    # Serialize for FullCalendar JS

    cal_events = [

        {

            'title': e.title,

            'start': str(e.start_date),

            'end':   str(e.end_date) if e.end_date else str(e.start_date),

            'color': _event_color(e.event_type),

            'description': e.description,

        }

        for e in events

    ]



    context = {

        'student':    student,

        'events':     events,

        'cal_events': cal_events,  # JSON for calendar JS

        'year':       year,

        'page_title': 'Academic Calendar',

    }

    return render(request, 'student_portal/academic_calendar.html', context)





def _event_color(event_type):

    """Map event type to a display colour for the calendar."""

    return {

        'exam_period':    '#DC2626',  # red

        'term_start':     '#16A34A',  # green

        'term_end':       '#16A34A',

        'fee_deadline':   '#D97706',  # amber

        'registration':   '#2563EB',  # blue

        'holiday':        '#7C3AED',  # purple

        'submission':     '#EA580C',  # orange

        'graduation':     '#0891B2',  # cyan

    }.get(event_type, '#6B7280')





# =============================================================================

# 18. TERM ENROLLMENT  ? NEW — Makerere benchmark (AIMS Step IV)

# =============================================================================

@student_required

def term_enrollment(request):

    student = request.student

    term    = _current_term()



    if not term:

        messages.info(request, "No active term found. Enrollment is not available at this time.")

        return redirect('student_portal:dashboard')



    enrollment, _ = TermEnrollment.objects.get_or_create(

        student=student,

        term=term,

        defaults={

            'tenant':     request.tenant,

            'study_year': 1,

            'status':     TermEnrollment.Status.CONTINUING,

        }

    )



    if request.method == 'POST':

        form = TermEnrollmentForm(request.POST, instance=enrollment)

        if form.is_valid():

            enr = form.save(commit=False)

            enr.tenant = request.tenant

            enr.save()

            if 'confirm' in request.POST:

                enr.confirm()

                messages.success(request, f"Enrollment for {term} confirmed successfully.")

            else:

                messages.success(request, "Enrollment details saved.")

            return redirect('student_portal:term_enrollment')

    else:

        form = TermEnrollmentForm(instance=enrollment)



    # Registration completeness checklist

    checklist = _enrollment_checklist(student, term)



    context = {

        'student':    student,

        'term':       term,

        'enrollment': enrollment,

        'form':       form,

        'checklist':  checklist,

        'page_title': 'Term Enrollment',

    }

    return render(request, 'student_portal/enrollment.html', context)





def _enrollment_checklist(student, term):

    """Returns a list of (label, is_done) tuples for the enrollment checklist."""

    from apps.finance.models import FeeInvoice

    invoice = FeeInvoice.objects.filter(student=student, term=term).first()

    fee_pct = 0

    if invoice and invoice.total_amount > 0:

        paid = Payment.objects.filter(

            invoice=invoice

        ).aggregate(s=Sum('amount'))['s'] or 0

        fee_pct = (paid / invoice.total_amount) * 100



    return [

        ('Fee payment = 60%',     fee_pct >= 60),

        ('Biodata verified',       bool(student.profile_verified)),

        ('Course units selected',  CourseUnitRegistration.objects.filter(

                                       enrollment__student=student,

                                       enrollment__term=term

                                   ).exists()),

    ]





# =============================================================================

# 19. COURSE UNIT REGISTRATION  ? NEW — Makerere benchmark (AIMS Step VI)

# =============================================================================

@student_required

def course_registration(request):

    student    = request.student

    term       = _current_term()

    enrollment = TermEnrollment.objects.filter(student=student, term=term).first() if term else None



    if not enrollment:

        messages.warning(request, "Please complete term enrollment before registering course units.")

        return redirect('student_portal:term_enrollment')



    # Available subjects for this class

    from apps.academics.models import ClassSubject

    available_subjects = ClassSubject.objects.filter(

        classroom=student.current_class

    ).select_related('subject').order_by('subject__name')



    # Already registered

    registered_ids = set(

        CourseUnitRegistration.objects.filter(

            enrollment=enrollment, is_active=True

        ).values_list('subject_id', flat=True)

    )



    if request.method == 'POST':

        selected_ids = request.POST.getlist('subject_ids')

        paper_types  = request.POST.getlist('paper_types')



        # Deactivate removed subjects

        CourseUnitRegistration.objects.filter(

            enrollment=enrollment

        ).exclude(subject_id__in=selected_ids).update(is_active=False)



        # Register new ones

        for subj_id, ptype in zip(selected_ids, paper_types):

            CourseUnitRegistration.objects.update_or_create(

                enrollment=enrollment,

                subject_id=subj_id,

                defaults={

                    'paper_type': ptype,

                    'is_active':  True,

                }

            )

        messages.success(request, "Course units registered successfully.")

        return redirect('student_portal:course_registration')



    context = {

        'student':           student,

        'term':              term,

        'enrollment':        enrollment,

        'available_subjects': available_subjects,

        'registered_ids':    registered_ids,

        'paper_type_choices': CourseUnitRegistration.PaperType.choices,

        'page_title':         'Course Unit Registration',

    }

    return render(request, 'student_portal/course_registration.html', context)





# =============================================================================

# 20. EXAM PERMIT  ? NEW — Makerere benchmark

# =============================================================================

@student_required

def exam_permit(request):

    student    = request.student

    term       = _current_term()

    enrollment = TermEnrollment.objects.filter(student=student, term=term).first() if term else None



    permit = None

    if enrollment:

        permit = ExamPermit.objects.filter(enrollment=enrollment).first()



    context = {

        'student':    student,

        'term':       term,

        'enrollment': enrollment,

        'permit':     permit,

        'page_title': 'Exam Permit',

    }

    return render(request, 'student_portal/exam_permit.html', context)





# =============================================================================

# 21. EXAM APPEALS  ? NEW — Makerere benchmark

# =============================================================================

@student_required

def exam_appeals(request):

    student  = request.student

    appeals  = ExamAppeal.objects.filter(student=student).order_by('-submitted_at')



    context = {

        'student':    student,

        'appeals':    appeals,

        'page_title': 'Examination Appeals',

    }

    return render(request, 'student_portal/appeals_list.html', context)





@student_required

def exam_appeal_new(request):

    student = request.student

    if request.method == 'POST':

        form = ExamAppealForm(student, request.POST)

        if form.is_valid():

            appeal = form.save(commit=False)

            appeal.tenant  = request.tenant

            appeal.student = student

            appeal.save()

            messages.success(request, f"Appeal {appeal.reference_number} submitted successfully. "

                                       "You will be notified when it is reviewed.")

            return redirect('student_portal:exam_appeals')

    else:

        form = ExamAppealForm(student)



    context = {

        'student':    student,

        'form':       form,

        'page_title': 'Lodge Exam Appeal',

    }

    return render(request, 'student_portal/appeal_form.html', context)





# =============================================================================

# 22. PROGRAMME / STREAM CHANGE REQUEST  ? NEW — Makerere benchmark

# =============================================================================

@student_required

def program_change(request):

    student   = request.student

    existing  = ProgramChangeRequest.objects.filter(

        student=student, status=ProgramChangeRequest.Status.PENDING

    ).first()



    if request.method == 'POST' and not existing:

        form = ProgramChangeRequestForm(student, request.POST, request.FILES)

        if form.is_valid():

            change = form.save(commit=False)

            change.tenant        = request.tenant

            change.student       = student

            change.current_class = student.current_class

            change.save()

            messages.success(request, "Programme change request submitted. "

                                       "You will be notified of the outcome.")

            return redirect('student_portal:program_change')

    else:

        form = ProgramChangeRequestForm(student)



    history = ProgramChangeRequest.objects.filter(student=student).order_by('-submitted_at')



    context = {

        'student':    student,

        'form':       form,

        'existing':   existing,

        'history':    history,

        'page_title': 'Programme / Stream Change',

    }

    return render(request, 'student_portal/program_change.html', context)





# =============================================================================

# 23. LEAVE OF ABSENCE / DEFERMENT  ? NEW — Makerere benchmark

# =============================================================================

@student_required

def leave_of_absence(request):

    student  = request.student

    existing = LeaveOfAbsenceRequest.objects.filter(

        student=student, status=LeaveOfAbsenceRequest.Status.PENDING

    ).first()



    if request.method == 'POST' and not existing:

        form = LeaveOfAbsenceRequestForm(request.POST, request.FILES)

        if form.is_valid():

            leave = form.save(commit=False)

            leave.tenant  = request.tenant

            leave.student = student

            leave.save()

            messages.success(request, "Leave of absence request submitted successfully.")

            return redirect('student_portal:leave_of_absence')

    else:

        form = LeaveOfAbsenceRequestForm()



    history = LeaveOfAbsenceRequest.objects.filter(student=student).order_by('-submitted_at')



    context = {

        'student':    student,

        'form':       form,

        'existing':   existing,

        'history':    history,

        'page_title': 'Leave of Absence',

    }

    return render(request, 'student_portal/leave_absence.html', context)





# =============================================================================

# 24. ACADEMIC CLEARANCE  ? NEW — Makerere benchmark

# =============================================================================

@student_required

def academic_clearance(request):

    student = request.student

    year    = _current_year()



    clearance = StudentClearance.objects.filter(

        student=student, academic_year=year

    ).first() if year else None



    if not clearance and year and request.method == 'POST' and 'request_clearance' in request.POST:

        clearance = StudentClearance.objects.create(

            tenant=request.tenant, student=student, academic_year=year

        )

        # Auto-create item statuses for all active clearance items

        items = AcademicClearanceItem.objects.filter(is_active=True)

        StudentClearanceItemStatus.objects.bulk_create([

            StudentClearanceItemStatus(clearance=clearance, item=item)

            for item in items

        ])

        messages.success(request, "Clearance application submitted.")

        return redirect('student_portal:academic_clearance')



    item_statuses = []

    if clearance:

        item_statuses = StudentClearanceItemStatus.objects.filter(

            clearance=clearance

        ).select_related('item', 'cleared_by')



    context = {

        'student':      student,

        'clearance':    clearance,

        'item_statuses': item_statuses,

        'year':         year,

        'page_title':   'Academic Clearance',

    }

    return render(request, 'student_portal/clearance.html', context)





# =============================================================================

# 25. CAREER GUIDANCE  (Phase 7 stub — shown with "Coming Soon" message)

# =============================================================================

@student_required

def career_guidance(request):

    student = request.student

    context = {

        'student':    student,

        'page_title': 'Career Guidance',

        'phase':      7,

    }

    return render(request, 'student_portal/career_guidance.html', context)





# =============================================================================

# 26. AI STUDY ASSISTANT  (Phase 7 stub)

# =============================================================================

@student_required

def ai_study_assistant(request):

    student = request.student

    context = {

        'student':    student,

        'page_title': 'AI Study Assistant',

        'phase':      7,

    }

    return render(request, 'student_portal/ai_assistant.html', context)





# =============================================================================

# 27. E-CERTIFICATES

# =============================================================================

@student_required

def certificates(request):

    student  = request.student

    try:
        from apps.documents.models import StudentDocument
        certs = StudentDocument.objects.filter(
            student=student, doc_type='certificate'
        ).order_by('-created_at')
    except ImportError:
        certs = []



    context = {

        'student':      student,

        'certificates': certs,

        'page_title':   'E-Certificates',

    }

    return render(request, 'student_portal/certificates.html', context)





# =============================================================================

# 28. PROFILE & SETTINGS

# =============================================================================

@student_required

def profile(request):

    student = request.student



    if request.method == 'POST':

        form = ProfileUpdateForm(request.POST)

        if form.is_valid():

            # Update user contact info

            user = request.user

            if form.cleaned_data.get('phone'):

                user.profile.phone = form.cleaned_data['phone']

            if form.cleaned_data.get('email'):

                user.email = form.cleaned_data['email']

            user.save()

            user.profile.save()

            messages.success(request, "Profile updated successfully.")

            return redirect('student_portal:profile')

    else:

        form = ProfileUpdateForm(initial={

            'phone': getattr(request.user, 'profile', None) and request.user.profile.phone,

            'email': request.user.email,

        })



    context = {

        'student':    student,

        'form':       form,

        'page_title': 'Profile & Settings',

    }

    return render(request, 'student_portal/profile.html', context)





# =============================================================================

# AJAX — Mark notification read

# =============================================================================

@student_required

@require_POST

def mark_notification_read(request, notif_id):

    notif = get_object_or_404(PortalNotification, id=notif_id, student=request.user.student_profile)

    notif.mark_read()

    return JsonResponse({'status': 'ok'})





@student_required
def notifications_feed(request):
    student = request.user.student_profile

    notifs = PortalNotification.objects.filter(
        student=student
    ).order_by('-created_at')

    unread = notifs.filter(is_read=False).count()
    notifs = notifs[:20]

    return JsonResponse({
        'unread': unread,
        'items': [
            {
                'id': n.id,
                'title': n.title,
                'body': n.body,
                'category': n.category,
                'is_read': n.is_read,
                'url': n.action_url,
                'time': n.created_at.isoformat(),
            }
            for n in notifs
        ]
    })
















