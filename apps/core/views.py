"""
apps/core/views.py
Role-based dashboard routing.
Each view passes only the context its template needs.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from apps.students.models import Student, ClassRoom
from apps.core.models import AcademicYear, Term
from apps.accounts.models import User
from apps.students.models import ClassRoom, Enrollment


# Roles that own the main admin/principal dashboard
_ADMIN_ROLES = {
    User.RoleChoices.PLATFORM_ADMIN,
    User.RoleChoices.NETWORK_ADMIN,
    User.RoleChoices.SCHOOL_ADMIN,
    User.RoleChoices.PRINCIPAL,
}


def _base_ctx(request):
    """
    Shared context injected into every dashboard view.
    Avoids repeating the same two queries in every view.
    """
    tenant = request.tenant
    return {
        'current_year': AcademicYear.objects.filter(
            tenant=tenant, is_current=True
        ).first(),
        'current_term': Term.objects.filter(
            tenant=tenant, is_current=True
        ).first(),
    }


# ── Admin / Principal Dashboard ────────────────────────────────────────────────

@login_required
def dashboard(request):
    """
    School Admin dashboard — EMIS-inspired with gender breakdown,
    class enrollment chart, staff stats, fees, at-risk, and activity feed.
    """
    from django.db import models as _m
    import json as _json

    user    = request.user
    tenant  = getattr(request, 'tenant', None)

    def tqs(qs):
        """Filter queryset by tenant if tenant middleware is active."""
        if tenant:
            try: return qs.filter(tenant=tenant)
            except Exception: pass
        return qs

    # ── Students ─────────────────────────────────────────────────────────
    total_students = male_students = female_students = 0
    total_classes  = at_risk_count = 0
    enrollment_by_class = []
    recent_students     = []

    try:
        from apps.students.models import Student, ClassRoom
        s_qs = tqs(Student.objects.filter(status='active'))
        total_students  = s_qs.count()
        male_students   = s_qs.filter(gender='M').count()
        female_students = s_qs.filter(gender='F').count()
        recent_students = list(s_qs.order_by('-created_at')[:6])

        class_qs = tqs(ClassRoom.objects.all()).order_by('name')
        total_classes = class_qs.count()
        for cls in class_qs:
            cq = s_qs.filter(current_class=cls)
            enrollment_by_class.append({
                'name':   str(cls),
                'male':   cq.filter(gender='M').count(),
                'female': cq.filter(gender='F').count(),
                'total':  cq.count(),
            })

        # At-risk: 3+ absences
        try:
            at_risk_count = s_qs.annotate(
                abs_count=_m.Count(
                    'attendancerecord',
                    filter=_m.Q(attendancerecord__status__in=['absent','A','ABSENT'])
                )
            ).filter(abs_count__gte=3).count()
        except Exception:
            at_risk_count = 0

    except Exception:
        pass

    # ── Staff ─────────────────────────────────────────────────────────────
    total_staff = staff_male = staff_female = 0
    teaching_staff = non_teaching_staff = 0

    try:
        from apps.staff_hr.models import StaffProfile
        all_staff = tqs(StaffProfile.objects.filter(is_active=True))
        total_staff = all_staff.count()

        # Gender split — try user.gender then fall back to profile gender
        try:
            staff_male   = all_staff.filter(user__gender='M').count()
            staff_female = all_staff.filter(user__gender='F').count()
        except Exception:
            try:
                staff_male   = all_staff.filter(gender='M').count()
                staff_female = all_staff.filter(gender='F').count()
            except Exception:
                pass

        # Teaching vs non-teaching
        try:
            teaching_staff     = all_staff.filter(
                employment_type__icontains='teach').count() or total_staff
            non_teaching_staff = all_staff.exclude(
                employment_type__icontains='teach').count()
        except Exception:
            teaching_staff = total_staff

    except Exception:
        pass

    # ── Finance ───────────────────────────────────────────────────────────
    total_invoiced = total_collected = total_outstanding = 0

    try:
        from apps.finance.models import Invoice, Payment
        inv_qs = tqs(Invoice.objects.all())
        pay_qs = tqs(Payment.objects.all())
        total_invoiced   = inv_qs.aggregate(t=_m.Sum('total_amount'))['t'] or 0
        total_collected  = pay_qs.aggregate(t=_m.Sum('amount'))['t'] or 0
        total_outstanding = max(total_invoiced - total_collected, 0)
    except Exception:
        pass

    # ── Activity feed ─────────────────────────────────────────────────────
    activity_items = []

    try:
        from apps.students.models import Student
        for s in tqs(Student.objects.all()).order_by('-created_at')[:3]:
            activity_items.append({
                'message': f'New student enrolled: {s.get_full_name()}',
                'time':    s.created_at,
                'color':   'success',
                'icon':    'person-plus',
            })
    except Exception:
        pass

    try:
        from apps.finance.models import Payment
        for p in tqs(Payment.objects.all()).order_by('-created_at')[:3]:
            amt = getattr(p, 'amount', 0) or 0
            activity_items.append({
                'message': f'Fee payment received: UGX {amt:,.0f}',
                'time':    getattr(p, 'created_at', None) or getattr(p, 'payment_date', None),
                'color':   'info',
                'icon':    'cash-coin',
            })
    except Exception:
        pass

    try:
        from apps.staff_hr.models import LeaveRequest
        for lr in tqs(LeaveRequest.objects.filter(status='pending')).order_by('-created_at')[:2]:
            name = ''
            try:   name = lr.staff.user.get_full_name()
            except Exception: pass
            activity_items.append({
                'message': f'Leave request pending: {name}',
                'time':    lr.created_at,
                'color':   'warning',
                'icon':    'calendar-x',
            })
    except Exception:
        pass

    try:
        from apps.exams.models import ExamResult
        for er in tqs(ExamResult.objects.all()).order_by('-created_at')[:2]:
            activity_items.append({
                'message': 'Exam results entered',
                'time':    er.created_at,
                'color':   'primary',
                'icon':    'clipboard2-check',
            })
    except Exception:
        pass

    recent_activities = sorted(
        [a for a in activity_items if a.get('time')],
        key=lambda x: x['time'],
        reverse=True
    )[:6]

    # ── Academic period ───────────────────────────────────────────────────
    term = academic_year = None
    try:
        from apps.core.models import Term, AcademicYear
        term          = tqs(Term.objects.filter(is_current=True)).first()
        academic_year = tqs(AcademicYear.objects.filter(is_current=True)).first()
    except Exception:
        pass

    context = {
        'title':              'Dashboard',
        # Students
        'total_students':     total_students,
        'male_students':      male_students,
        'female_students':    female_students,
        'recent_students':    recent_students,
        'total_classes':      total_classes,
        'at_risk_count':      at_risk_count,
        # Staff
        'total_staff':        total_staff,
        'staff_male':         staff_male,
        'staff_female':       staff_female,
        'teaching_staff':     teaching_staff,
        'non_teaching_staff': non_teaching_staff,
        # Finance
        'total_collected':    int(total_collected),
        'total_outstanding':  int(total_outstanding),
        # Chart JSON
        'enrollment_json':    _json.dumps(enrollment_by_class),
        # Activity
        'recent_activities':  recent_activities,
        # Academic period
        'term':               term,
        'academic_year':      academic_year,
    }
    return render(request, 'dashboard/dashboard.html', context)


@login_required
def teacher_dashboard(request):
    tenant = request.tenant
    if not tenant:
        return render(request, 'base/no_tenant.html')

    ctx = _base_ctx(request)

    # Classes where this user is the assigned class teacher
    # Assumes ClassRoom.class_teacher = ForeignKey(User) per spec Appendix C
    my_classes = ClassRoom.objects.filter(
        tenant=tenant, class_teacher=request.user
    )

    # Students enrolled in those classes
    # Assumes Student.class_room = ForeignKey(ClassRoom) per spec Appendix C
    my_students_count = Enrollment.objects.filter(
        tenant=tenant, status='active', classroom__in=my_classes, is_active=True
    ).count()

    ctx.update({
        'my_classes':        my_classes,
        'my_classes_count':  my_classes.count(),
        'my_students_count': my_students_count,
        # at_risk_count and pending_assignments added here in Phase 5
        # when StudentRiskProfile and Assignments models are available
    })
    return render(request, 'dashboard/teacher.html', ctx)


# ── Finance / Accountant Dashboard ────────────────────────────────────────────
# Spec ref: Section 11, Section 14 (Finance), Appendix D.2, Section 7.4

@login_required
def finance_dashboard(request):
    tenant = request.tenant
    if not tenant:
        return render(request, 'base/no_tenant.html')

    ctx = _base_ctx(request)

    # Finance model context (FeeInvoice, Payment) added here once
    # apps/finance/models.py is built in Phase 1 finance sprint.
    # Example additions:
    #   from apps.finance.models import FeeInvoice, Payment
    #   ctx['invoices_count']    = FeeInvoice.objects.filter(tenant=tenant, term=ctx['current_term']).count()
    #   ctx['recent_payments']   = Payment.objects.filter(tenant=tenant).order_by('-timestamp')[:10]
    #   ctx['outstanding_count'] = FeeInvoice.objects.filter(tenant=tenant, status='unpaid').count()
    #   ctx['overdue_count']     = FeeInvoice.objects.filter(tenant=tenant, status='overdue').count()

    return render(request, 'dashboard/finance.html', ctx)


# ── Welfare / Counsellor Dashboard ────────────────────────────────────────────
# Spec ref: Section 7.1, Section 7.5, Section 11, Appendix G.6

@login_required
def welfare_dashboard(request):
    tenant = request.tenant
    if not tenant:
        return render(request, 'base/no_tenant.html')

    ctx = _base_ctx(request)

    # Welfare model context added here in Phase 3 (Counselling module).
    # Example additions:
    #   from apps.counselling.models import WelfareCase, StudentRiskProfile
    #   ctx['open_cases_count']   = WelfareCase.objects.filter(tenant=tenant, status='open').count()
    #   ctx['high_risk_count']    = StudentRiskProfile.objects.filter(tenant=tenant, score__gte=71).count()
    #   ctx['medium_risk_count']  = StudentRiskProfile.objects.filter(tenant=tenant, score__range=(41,70)).count()
    #   ctx['unresolved_count']   = WelfareCase.objects.filter(tenant=tenant, days_open__gte=21).count()
    #   ctx['at_risk_students']   = StudentRiskProfile.objects.filter(tenant=tenant, score__gte=41)
    #                                   .select_related('student').order_by('-score')[:10]

    return render(request, 'dashboard/welfare.html', ctx)


# ── Library Dashboard ──────────────────────────────────────────────────────────
# Spec ref: Section 11, Section 14 (Library), Section 12 (Borrowing Record doc)

@login_required
def library_dashboard(request):
    tenant = request.tenant
    if not tenant:
        return render(request, 'base/no_tenant.html')

    ctx = _base_ctx(request)

    # Library model context added here in Phase 4 (Library module).
    # Example additions:
    #   from apps.library.models import Book, BorrowingRecord
    #   ctx['total_books']      = Book.objects.filter(tenant=tenant).count()
    #   ctx['borrowed_count']   = BorrowingRecord.objects.filter(tenant=tenant, returned=False).count()
    #   ctx['overdue_count']    = BorrowingRecord.objects.filter(tenant=tenant, is_overdue=True).count()
    #   ctx['borrowed_records'] = BorrowingRecord.objects.filter(tenant=tenant, returned=False)
    #                                 .select_related('book', 'student').order_by('due_date')[:10]

    return render(request, 'dashboard/library.html', ctx) 

# ── Phase 2 Role Dashboards ────────────────────────────

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta

# ── TEACHER DASHBOARD ────────────────────────────────────────────────────
@login_required
def teacher_dashboard(request):
    from apps.academics.models import ClassSubject
    from apps.assignments.models import Assignment, AssignmentSubmission
    from apps.exams.models import Exam
    from apps.lms.models import LessonPlan
    try:
        from apps.attendance.models import AttendanceRecord
        from apps.students.models import Student
    except ImportError:
        AttendanceRecord = None
        Student = None

    today = timezone.now().date()
    user  = request.user

    my_subjects = ClassSubject.objects.filter(
        teacher=user
    ).select_related('classroom', 'subject')

    my_class_ids = list(my_subjects.values_list('classroom_id', flat=True))

    today_present = today_absent = 0
    if AttendanceRecord:
        today_att = AttendanceRecord.objects.filter(
            classroom_id__in=my_class_ids, date=today
        )
        today_present = today_att.filter(status='present').count()
        today_absent  = today_att.filter(status='absent').count()

    pending_grading = AssignmentSubmission.objects.filter(
        assignment__class_subject__teacher=user,
        status='submitted'
    ).count()

    my_assignments = Assignment.objects.filter(
        class_subject__teacher=user, status='published'
    ).order_by('-due_date')[:5]

    my_exams = Exam.objects.filter(
        created_by=user
    ).order_by('-exam_date')[:5]

    unfinished_plans = LessonPlan.objects.filter(
        class_subject__teacher=user, is_completed=False
    ).count()

    return render(request, 'dashboard/teacher.html', {
        'my_subjects':      my_subjects,
        'subject_count':    my_subjects.count(),
        'today_present':    today_present,
        'today_absent':     today_absent,
        'pending_grading':  pending_grading,
        'my_assignments':   my_assignments,
        'my_exams':         my_exams,
        'unfinished_plans': unfinished_plans,
        'today':            today,
    })


# ── ACCOUNTANT / FINANCE DASHBOARD ───────────────────────────────────────
@login_required
def finance_dashboard(request):
    from django.db.models import Sum
    try:
        from apps.finance.models import FeeInvoice, Payment
    except ImportError:
        return render(request, 'dashboard/finance.html', {})

    today = timezone.now().date()
    month_start = today.replace(day=1)

    total_invoiced    = FeeInvoice.objects.aggregate(t=Sum('total_amount'))['t'] or 0
    total_collected   = FeeInvoice.objects.aggregate(t=Sum('amount_paid'))['t'] or 0
    outstanding       = total_invoiced - total_collected
    collected_today   = Payment.objects.filter(
        payment_date=today
    ).aggregate(t=Sum('amount'))['t'] or 0
    collected_month   = Payment.objects.filter(
        payment_date__gte=month_start
    ).aggregate(t=Sum('amount'))['t'] or 0
    overdue_invoices  = FeeInvoice.objects.filter(
        status__in=['pending', 'overdue']
    ).select_related('student').order_by('-total_amount')[:10]
    recent_payments   = Payment.objects.select_related(
        'invoice__student'
    ).order_by('-payment_date')[:10]
    partial_invoices  = FeeInvoice.objects.filter(status='partial').count()

    return render(request, 'dashboard/finance.html', {
        'total_invoiced':   total_invoiced,
        'total_collected':  total_collected,
        'outstanding':      outstanding,
        'collected_today':  collected_today,
        'collected_month':  collected_month,
        'overdue_invoices': overdue_invoices,
        'recent_payments':  recent_payments,
        'partial_count':    partial_invoices,
    })


# ── COUNSELLOR / WELFARE DASHBOARD ───────────────────────────────────────
@login_required
def welfare_dashboard(request):
    try:
        from apps.students.models import Student
        from apps.attendance.models import AttendanceRecord
        from apps.finance.models import FeeInvoice
    except ImportError:
        return render(request, 'dashboard/welfare.html', {})

    today      = timezone.now().date()
    four_weeks = today - timedelta(weeks=4)

    # Students absent 3+ consecutive days in last week
    recent_absences = AttendanceRecord.objects.filter(
        status='absent', date__gte=today - timedelta(days=7)
    ).values('student_id').annotate(
        absent_days=__import__('django.db.models', fromlist=['Count']).Count('id')
    ).filter(absent_days__gte=3).count()

    # Fee arrears > 30 days
    from django.db.models import Q
    arrears_30 = FeeInvoice.objects.filter(
        status__in=['pending', 'overdue'],
        due_date__lte=today - timedelta(days=30)
    ).count()

    # Low attendance students (rough: absent > 20% in last 4 weeks)
    low_attendance = AttendanceRecord.objects.filter(
        date__gte=four_weeks, status='absent'
    ).values('student_id').annotate(
        cnt=__import__('django.db.models', fromlist=['Count']).Count('id')
    ).filter(cnt__gte=6)

    at_risk_students = Student.objects.filter(
        pk__in=[x['student_id'] for x in low_attendance],
        status='active'
    ).select_related('current_class')[:20]

    return render(request, 'dashboard/welfare.html', {
        'recent_absences':   recent_absences,
        'arrears_30':        arrears_30,
        'at_risk_students':  at_risk_students,
        'at_risk_count':     len(at_risk_students),
    })


# ── LIBRARIAN DASHBOARD ──────────────────────────────────────────────────
@login_required
def library_dashboard(request):
    from apps.library.models import Book, BorrowRecord, BookCategory

    today = timezone.now().date()

    total_books     = Book.objects.count()
    available_books = Book.objects.filter(available_copies__gt=0).count()
    borrowed_out    = BorrowRecord.objects.filter(status='borrowed').count()
    overdue_books   = BorrowRecord.objects.filter(status='overdue').count()
    overdue_records = BorrowRecord.objects.filter(
        status='overdue'
    ).select_related('book', 'student').order_by('due_date')[:15]
    issued_today    = BorrowRecord.objects.filter(
        borrow_date=today
    ).count()
    total_fines     = BorrowRecord.objects.filter(
        fine_amount__gt=0, fine_paid=False
    ).aggregate(
        t=__import__('django.db.models', fromlist=['Sum']).Sum('fine_amount')
    )['t'] or 0
    low_stock       = Book.objects.filter(available_copies=0).count()
    categories      = BookCategory.objects.all()

    return render(request, 'dashboard/library.html', {
        'total_books':     total_books,
        'available_books': available_books,
        'borrowed_out':    borrowed_out,
        'overdue_books':   overdue_books,
        'overdue_records': overdue_records,
        'issued_today':    issued_today,
        'total_fines':     total_fines,
        'low_stock':       low_stock,
        'categories':      categories,
    })


# ── PRINCIPAL DASHBOARD ──────────────────────────────────────────────────
@login_required
def principal_dashboard(request):
    from django.db.models import Avg
    from apps.exams.models import TermReport, Exam
    from apps.staff_hr.models import StaffProfile, LeaveRequest
    from apps.academics.models import ClassSubject
    try:
        from apps.students.models import Student
        from apps.attendance.models import AttendanceRecord
        from apps.finance.models import FeeInvoice
        from apps.admissions.models import AdmissionApplication
    except ImportError:
        Student = AttendanceRecord = FeeInvoice = AdmissionApplication = None

    today = timezone.now().date()

    student_count   = Student.objects.filter(status='active').count() if Student else 0
    staff_count     = StaffProfile.objects.filter(is_active=True).count()
    today_present   = today_absent = 0
    if AttendanceRecord:
        att = AttendanceRecord.objects.filter(date=today)
        today_present = att.filter(status='present').count()
        today_absent  = att.filter(status='absent').count()

    pending_leaves  = LeaveRequest.objects.filter(status='pending').count()
    pending_apps    = AdmissionApplication.objects.filter(status='pending').count() if AdmissionApplication else 0

    outstanding = 0
    if FeeInvoice:
        from django.db.models import Sum, F
        result = FeeInvoice.objects.aggregate(
            out=Sum('total_amount') - Sum('amount_paid')
        )
        outstanding = result['out'] or 0

    recent_reports = TermReport.objects.select_related(
        'student', 'classroom'
    ).order_by('-computed_at')[:10]

    unpublished_exams = Exam.objects.filter(is_published=False).count()

    return render(request, 'dashboard/principal.html', {
        'student_count':    student_count,
        'staff_count':      staff_count,
        'today_present':    today_present,
        'today_absent':     today_absent,
        'pending_leaves':   pending_leaves,
        'pending_apps':     pending_apps,
        'outstanding':      outstanding,
        'recent_reports':   recent_reports,
        'unpublished_exams':unpublished_exams,
    })
