"""
Builds role-specific dashboards for ASMS Phase 2.
Creates views, templates, and updates URLs.
Run from project root: python build_role_dashboards.py
"""
import os, re

ROOT  = os.getcwd()
APPS  = os.path.join(ROOT, 'apps')
TMPL  = os.path.join(ROOT, 'templates', 'dashboard')
os.makedirs(TMPL, exist_ok=True)

# ── 1. VIEWS ──────────────────────────────────────────────────────────────
VIEWS_CODE = '''
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
    total_collected   = FeeInvoice.objects.aggregate(t=Sum('paid_amount'))['t'] or 0
    outstanding       = total_invoiced - total_collected
    collected_today   = Payment.objects.filter(
        payment_date__date=today
    ).aggregate(t=Sum('amount'))['t'] or 0
    collected_month   = Payment.objects.filter(
        payment_date__date__gte=month_start
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
            out=Sum('total_amount') - Sum('paid_amount')
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
'''

# ── 2. TEMPLATES ──────────────────────────────────────────────────────────
BASE_EXTENDS = '{% extends "base/base.html" %}'

TEMPLATES = {}

TEMPLATES['teacher.html'] = BASE_EXTENDS + '''
{% block title %}Teacher Dashboard{% endblock %}
{% block content %}
<div class="row g-3 mb-4">
  <div class="col-6 col-md-3">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-primary">{{ subject_count }}</div>
      <div class="text-muted small">My Subjects</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-success">{{ today_present }}</div>
      <div class="text-muted small">Present Today</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-danger">{{ today_absent }}</div>
      <div class="text-muted small">Absent Today</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-warning">{{ pending_grading }}</div>
      <div class="text-muted small">Awaiting Grading</div>
    </div>
  </div>
</div>
<div class="row g-3">
  <div class="col-md-6">
    <div class="card h-100">
      <div class="card-header fw-semibold"><i class="bi bi-journal-text me-2 text-primary"></i>My Class Subjects</div>
      <div class="card-body p-0">
        <table class="table table-hover mb-0">
          <thead class="table-light"><tr><th>Class</th><th>Subject</th></tr></thead>
          <tbody>
          {% for cs in my_subjects %}
          <tr>
            <td>{{ cs.classroom }}</td>
            <td class="fw-semibold">{{ cs.subject }}</td>
          </tr>
          {% empty %}
          <tr><td colspan="2" class="text-center text-muted py-3">No subjects assigned yet.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
  <div class="col-md-6">
    <div class="card mb-3">
      <div class="card-header fw-semibold"><i class="bi bi-file-earmark-text me-2 text-success"></i>Assignments to Grade</div>
      <div class="card-body p-0">
        <table class="table table-sm mb-0">
          <thead class="table-light"><tr><th>Assignment</th><th>Class</th><th>Due</th></tr></thead>
          <tbody>
          {% for a in my_assignments %}
          <tr>
            <td><a href="{% url 'assignment_detail' a.pk %}">{{ a.title|truncatechars:25 }}</a></td>
            <td>{{ a.class_subject.classroom }}</td>
            <td class="text-muted small">{{ a.due_date|date:"d M" }}</td>
          </tr>
          {% empty %}
          <tr><td colspan="3" class="text-center text-muted py-2">No active assignments.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <div class="card-header fw-semibold"><i class="bi bi-clipboard2-data me-2 text-info"></i>Recent Exams</div>
      <div class="card-body p-0">
        <table class="table table-sm mb-0">
          <thead class="table-light"><tr><th>Exam</th><th>Status</th></tr></thead>
          <tbody>
          {% for e in my_exams %}
          <tr>
            <td>{{ e.name|truncatechars:30 }}</td>
            <td>{% if e.is_published %}<span class="badge bg-success">Published</span>{% else %}<span class="badge bg-warning text-dark">Draft</span>{% endif %}</td>
          </tr>
          {% empty %}
          <tr><td colspan="2" class="text-center text-muted py-2">No exams yet.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
<div class="row g-3 mt-1">
  <div class="col-12">
    <div class="d-flex gap-2 flex-wrap">
      <a href="{% url 'attendance_mark' %}" class="btn btn-primary"><i class="bi bi-calendar-check me-1"></i>Mark Attendance</a>
      <a href="{% url 'assignment_create' %}" class="btn btn-outline-success"><i class="bi bi-plus me-1"></i>New Assignment</a>
      <a href="{% url 'exam_create' %}" class="btn btn-outline-info"><i class="bi bi-plus me-1"></i>New Exam</a>
      <a href="{% url 'lesson_plan_create' %}" class="btn btn-outline-secondary"><i class="bi bi-journal-plus me-1"></i>Lesson Plan</a>
    </div>
  </div>
</div>
{% endblock %}'''

TEMPLATES['finance.html'] = BASE_EXTENDS + '''
{% block title %}Finance Dashboard{% endblock %}
{% block content %}
<div class="row g-3 mb-4">
  <div class="col-6 col-md-3">
    <div class="card p-3" style="border-left:4px solid #4f8ef7">
      <div class="text-muted small">Total Invoiced</div>
      <div class="fs-5 fw-bold text-primary">UGX {{ total_invoiced|floatformat:0 }}</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card p-3" style="border-left:4px solid #28a745">
      <div class="text-muted small">Total Collected</div>
      <div class="fs-5 fw-bold text-success">UGX {{ total_collected|floatformat:0 }}</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card p-3" style="border-left:4px solid #dc3545">
      <div class="text-muted small">Outstanding</div>
      <div class="fs-5 fw-bold text-danger">UGX {{ outstanding|floatformat:0 }}</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card p-3" style="border-left:4px solid #fd7e14">
      <div class="text-muted small">Collected Today</div>
      <div class="fs-5 fw-bold text-warning">UGX {{ collected_today|floatformat:0 }}</div>
    </div>
  </div>
</div>
<div class="row g-3">
  <div class="col-md-7">
    <div class="card">
      <div class="card-header fw-semibold"><i class="bi bi-exclamation-triangle me-2 text-danger"></i>Overdue Invoices</div>
      <div class="card-body p-0">
        <table class="table table-hover table-sm mb-0">
          <thead class="table-light"><tr><th>Student</th><th>Amount</th><th>Balance</th></tr></thead>
          <tbody>
          {% for inv in overdue_invoices %}
          <tr>
            <td><a href="{% url 'invoice_detail' inv.pk %}">{{ inv.student.full_name }}</a></td>
            <td>UGX {{ inv.total_amount|floatformat:0 }}</td>
            <td class="text-danger fw-semibold">UGX {{ inv.balance|floatformat:0 }}</td>
          </tr>
          {% empty %}
          <tr><td colspan="3" class="text-center text-muted py-3">No overdue invoices.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
  <div class="col-md-5">
    <div class="card mb-3">
      <div class="card-header fw-semibold"><i class="bi bi-clock-history me-2 text-success"></i>Recent Payments</div>
      <div class="card-body p-0">
        <table class="table table-sm mb-0">
          <thead class="table-light"><tr><th>Student</th><th>Amount</th></tr></thead>
          <tbody>
          {% for p in recent_payments %}
          <tr>
            <td class="small">{{ p.invoice.student.full_name }}</td>
            <td class="text-success fw-semibold small">{{ p.amount|floatformat:0 }}</td>
          </tr>
          {% empty %}
          <tr><td colspan="2" class="text-center text-muted py-2">No recent payments.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
    <div class="d-flex gap-2">
      <a href="{% url 'invoice_create' %}" class="btn btn-primary flex-grow-1"><i class="bi bi-plus me-1"></i>New Invoice</a>
      <a href="{% url 'finance_summary' %}" class="btn btn-outline-secondary flex-grow-1"><i class="bi bi-bar-chart me-1"></i>Summary</a>
    </div>
  </div>
</div>
{% endblock %}'''

TEMPLATES['welfare.html'] = BASE_EXTENDS + '''
{% block title %}Welfare Dashboard{% endblock %}
{% block content %}
<div class="row g-3 mb-4">
  <div class="col-md-4">
    <div class="card text-center p-4" style="border-left:4px solid #dc3545">
      <div class="display-5 fw-bold text-danger">{{ at_risk_count }}</div>
      <div class="text-muted">Students at Risk</div>
      <div class="text-muted small">(3+ absences in last 7 days)</div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card text-center p-4" style="border-left:4px solid #fd7e14">
      <div class="display-5 fw-bold text-warning">{{ recent_absences }}</div>
      <div class="text-muted">Absence Alerts</div>
      <div class="text-muted small">This week</div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card text-center p-4" style="border-left:4px solid #6f42c1">
      <div class="display-5 fw-bold text-purple">{{ arrears_30 }}</div>
      <div class="text-muted">Fee Arrears 30+ Days</div>
      <div class="text-muted small">Financial hardship flags</div>
    </div>
  </div>
</div>
<div class="card">
  <div class="card-header fw-semibold"><i class="bi bi-exclamation-triangle-fill me-2 text-danger"></i>Students Needing Attention</div>
  <div class="card-body p-0">
    <table class="table table-hover mb-0">
      <thead class="table-light"><tr><th>Student</th><th>Class</th><th>Action</th></tr></thead>
      <tbody>
      {% for s in at_risk_students %}
      <tr>
        <td class="fw-semibold">{{ s.full_name }}</td>
        <td>{{ s.current_class|default:"—" }}</td>
        <td><a href="{% url 'student_detail' s.pk %}" class="btn btn-sm btn-outline-danger">Review</a></td>
      </tr>
      {% empty %}
      <tr><td colspan="3" class="text-center text-muted py-4"><i class="bi bi-check-circle text-success fs-3 d-block mb-2"></i>No at-risk students this week.</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}'''

TEMPLATES['library.html'] = BASE_EXTENDS + '''
{% block title %}Library Dashboard{% endblock %}
{% block content %}
<div class="row g-3 mb-4">
  <div class="col-6 col-md-3">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-primary">{{ total_books }}</div>
      <div class="text-muted small">Total Books</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-success">{{ available_books }}</div>
      <div class="text-muted small">Available</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-warning">{{ borrowed_out }}</div>
      <div class="text-muted small">Borrowed Out</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-danger">{{ overdue_books }}</div>
      <div class="text-muted small">Overdue</div>
    </div>
  </div>
</div>
<div class="row g-3 mb-3">
  <div class="col-md-4"><div class="card p-3 text-center"><div class="fw-bold text-info">{{ issued_today }}</div><div class="text-muted small">Issued Today</div></div></div>
  <div class="col-md-4"><div class="card p-3 text-center"><div class="fw-bold text-danger">UGX {{ total_fines|floatformat:0 }}</div><div class="text-muted small">Unpaid Fines</div></div></div>
  <div class="col-md-4"><div class="card p-3 text-center"><div class="fw-bold text-warning">{{ low_stock }}</div><div class="text-muted small">Out of Stock</div></div></div>
</div>
<div class="card mb-3">
  <div class="card-header fw-semibold"><i class="bi bi-exclamation-circle me-2 text-danger"></i>Overdue Books</div>
  <div class="card-body p-0">
    <table class="table table-hover table-sm mb-0">
      <thead class="table-light"><tr><th>Book</th><th>Student</th><th>Due Date</th><th>Fine</th><th>Action</th></tr></thead>
      <tbody>
      {% for r in overdue_records %}
      <tr>
        <td class="fw-semibold small">{{ r.book.title|truncatechars:20 }}</td>
        <td class="small">{{ r.student.full_name }}</td>
        <td class="text-danger small">{{ r.due_date|date:"d M Y" }}</td>
        <td class="text-danger small">{% if r.fine_amount %}UGX {{ r.fine_amount|floatformat:0 }}{% else %}—{% endif %}</td>
        <td><a href="{% url 'return_book' r.pk %}" class="btn btn-sm btn-outline-success">Return</a></td>
      </tr>
      {% empty %}
      <tr><td colspan="5" class="text-center text-muted py-3">No overdue books.</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
<div class="d-flex gap-2">
  <a href="{% url 'borrow_book' %}" class="btn btn-primary"><i class="bi bi-arrow-right-circle me-1"></i>Issue Book</a>
  <a href="{% url 'book_create' %}" class="btn btn-outline-primary"><i class="bi bi-plus me-1"></i>Add Book</a>
  <a href="{% url 'borrow_list' %}" class="btn btn-outline-secondary"><i class="bi bi-list me-1"></i>All Loans</a>
</div>
{% endblock %}'''

TEMPLATES['principal.html'] = BASE_EXTENDS + '''
{% block title %}Principal Dashboard{% endblock %}
{% block content %}
<div class="row g-3 mb-4">
  <div class="col-6 col-md-2">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-primary">{{ student_count }}</div>
      <div class="text-muted small">Students</div>
    </div>
  </div>
  <div class="col-6 col-md-2">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-info">{{ staff_count }}</div>
      <div class="text-muted small">Staff</div>
    </div>
  </div>
  <div class="col-6 col-md-2">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-success">{{ today_present }}</div>
      <div class="text-muted small">Present</div>
    </div>
  </div>
  <div class="col-6 col-md-2">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-danger">{{ today_absent }}</div>
      <div class="text-muted small">Absent</div>
    </div>
  </div>
  <div class="col-6 col-md-2">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-warning">{{ pending_leaves }}</div>
      <div class="text-muted small">Leave Pending</div>
    </div>
  </div>
  <div class="col-6 col-md-2">
    <div class="card text-center p-3">
      <div class="display-6 fw-bold text-secondary">{{ pending_apps }}</div>
      <div class="text-muted small">Applications</div>
    </div>
  </div>
</div>
<div class="row g-3 mb-3">
  <div class="col-md-4">
    <div class="card p-3" style="border-left:4px solid #dc3545">
      <div class="text-muted small">Outstanding Fees</div>
      <div class="fs-5 fw-bold text-danger">UGX {{ outstanding|floatformat:0 }}</div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card p-3" style="border-left:4px solid #fd7e14">
      <div class="text-muted small">Unpublished Exams</div>
      <div class="fs-5 fw-bold text-warning">{{ unpublished_exams }}</div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card p-3 d-flex flex-row gap-2">
      <a href="{% url 'leave_list' %}" class="btn btn-sm btn-outline-primary flex-grow-1">Review Leaves</a>
      <a href="{% url 'report_list' 1 %}" class="btn btn-sm btn-outline-info flex-grow-1">Reports</a>
    </div>
  </div>
</div>
<div class="card">
  <div class="card-header fw-semibold"><i class="bi bi-file-earmark-person me-2 text-primary"></i>Recent Term Reports</div>
  <div class="card-body p-0">
    <table class="table table-hover table-sm mb-0">
      <thead class="table-light"><tr><th>Student</th><th>Class</th><th>Average</th><th>Position</th><th>Status</th></tr></thead>
      <tbody>
      {% for r in recent_reports %}
      <tr>
        <td><a href="{% url 'student_report' r.pk %}">{{ r.student.full_name }}</a></td>
        <td>{{ r.classroom }}</td>
        <td>{{ r.average_score }}%</td>
        <td>{{ r.position }}/{{ r.out_of }}</td>
        <td>{% if r.is_published %}<span class="badge bg-success">Published</span>{% else %}<span class="badge bg-secondary">Draft</span>{% endif %}</td>
      </tr>
      {% empty %}
      <tr><td colspan="5" class="text-center text-muted py-3">No reports computed yet.</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}'''

# ── 3. Write templates ─────────────────────────────────────────────────────
print('\n═══ Building Role Dashboards ═══\n')
for fname, content in TEMPLATES.items():
    path = os.path.join(TMPL, fname)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  ✓ templates/dashboard/{fname}')

# ── 4. Find dashboard views file and append new views ─────────────────────
dashboard_views = None
for candidate in [
    os.path.join(APPS, 'dashboard', 'views.py'),
    os.path.join(APPS, 'core', 'views.py'),
]:
    if os.path.exists(candidate):
        dashboard_views = candidate
        break

if dashboard_views:
    with open(dashboard_views, encoding='utf-8') as f:
        existing = f.read()
    views_to_add = []
    for view_name in ['teacher_dashboard', 'finance_dashboard', 'welfare_dashboard',
                      'library_dashboard', 'principal_dashboard']:
        if f'def {view_name}' not in existing:
            views_to_add.append(view_name)
    if views_to_add:
        with open(dashboard_views, 'a', encoding='utf-8') as f:
            f.write('\n\n# ── Phase 2 Role Dashboards ────────────────────────────\n')
            f.write(VIEWS_CODE)
        print(f'\n  ✓ Added role dashboard views to {dashboard_views}')
    else:
        print(f'\n  ✓ Views already exist in {dashboard_views}')
else:
    print('\n  ⚠ Could not find dashboard views file.')
    print('    Paste VIEWS_CODE manually into your dashboard views file.')

# ── 5. Update dashboard urls.py ───────────────────────────────────────────
dashboard_urls = None
for candidate in [
    os.path.join(APPS, 'dashboard', 'urls.py'),
    os.path.join(APPS, 'core', 'urls.py'),
]:
    if os.path.exists(candidate):
        dashboard_urls = candidate
        break

NEW_URL_PATTERNS = """
    path('teacher/',   views.teacher_dashboard,  name='teacher_dashboard'),
    path('finance/',   views.finance_dashboard,  name='finance_dashboard'),
    path('welfare/',   views.welfare_dashboard,  name='welfare_dashboard'),
    path('library/',   views.library_dashboard,  name='library_dashboard'),
    path('principal/', views.principal_dashboard,name='principal_dashboard'),
"""

if dashboard_urls:
    with open(dashboard_urls, encoding='utf-8') as f:
        url_content = f.read()
    if 'teacher_dashboard' not in url_content:
        # Insert before closing bracket of urlpatterns
        url_content = re.sub(
            r'(urlpatterns\s*=\s*\[)',
            r'\1' + NEW_URL_PATTERNS,
            url_content
        )
        with open(dashboard_urls, 'w', encoding='utf-8') as f:
            f.write(url_content)
        print(f'  ✓ Added role URL patterns to {dashboard_urls}')
    else:
        print(f'  ✓ URL patterns already exist in {dashboard_urls}')
else:
    print(f'\n  ⚠ Could not find dashboard urls.py')
    print(f'    Add these to your dashboard URLs manually:')
    print(NEW_URL_PATTERNS)

# ── 6. Update get_dashboard_url ────────────────────────────────────────────
accounts_models = os.path.join(APPS, 'accounts', 'models.py')
with open(accounts_models, encoding='utf-8') as f:
    am = f.read()

am = am.replace("'/dashboard/dashboard/'", "'/dashboard/'")
am = am.replace("'/dashboard/teacher/'",   "'/dashboard/teacher/'")
am = am.replace("'/dashboard/finance/'",   "'/dashboard/finance/'")
am = am.replace("'/dashboard/welfare/'",   "'/dashboard/welfare/'")
am = am.replace("'/dashboard/library/'",   "'/dashboard/library/'")
am = am.replace("'/portal/parent/'",       "'/dashboard/'")
am = am.replace("'/portal/student/'",      "'/dashboard/'")

# Now set the correct role URLs
am = am.replace("'/dashboard/teacher/'",   "'/dashboard/teacher/'")
am = am.replace("'/dashboard/finance/'",   "'/dashboard/finance/'")
am = am.replace("'/dashboard/welfare/'",   "'/dashboard/welfare/'")
am = am.replace("'/dashboard/library/'",   "'/dashboard/library/'")

with open(accounts_models, 'w', encoding='utf-8') as f:
    f.write(am)
print('  ✓ get_dashboard_url() updated in accounts/models.py')

print('''
═══════════════════════════════════════════════════════════
  Role dashboards built:

  Role          URL                   Template
  ──────────────────────────────────────────────────
  Teacher     → /dashboard/teacher/   teacher.html
  Accountant  → /dashboard/finance/   finance.html
  Counsellor  → /dashboard/welfare/   welfare.html
  Librarian   → /dashboard/library/   library.html
  Principal   → /dashboard/principal/ principal.html
  Admin/Other → /dashboard/           (existing)

  NOW:
  1. Go to http://127.0.0.1:8000/accounts/logout/
  2. Log in as a teacher → lands on /dashboard/teacher/
  3. Log in as librarian → lands on /dashboard/library/
═══════════════════════════════════════════════════════════
''')
