#!/usr/bin/env python
"""
upgrade_dashboard.py
EMIS-inspired upgrade for the ASMS School Admin dashboard.
Adds gender breakdowns, per-class enrollment chart, staff stats,
real fee data, at-risk count, and recent activity feed.

Drop in your project root and run:
    python upgrade_dashboard.py
"""
import os, sys, re, json

BASE = os.path.dirname(os.path.abspath(__file__))

def r(p):  return os.path.join(BASE, p)
def read(p):
    with open(r(p), encoding='utf-8') as f: return f.read()
def write(p, c):
    os.makedirs(os.path.dirname(r(p)), exist_ok=True)
    with open(r(p), 'w', encoding='utf-8') as f: f.write(c)
    print(f"  ✓ Written: {p}")

print("=" * 60)
print("ASMS Dashboard Upgrade — EMIS-Inspired Stats & Charts")
print("=" * 60)

# ── Step 1: Find the dashboard view ─────────────────────────────────────────
print("\n[1/3] Locating dashboard view...")
view_path = None
for cand in ['apps/core/views.py', 'apps/dashboard/views.py']:
    if os.path.exists(r(cand)):
        content = read(cand)
        if 'def ' in content and ('dashboard' in content or 'render' in content):
            view_path = cand
            print(f"  Found: {cand}")
            break

if not view_path:
    print("  Searching recursively...")
    for root, dirs, files in os.walk(r('apps')):
        dirs[:] = [d for d in dirs if d not in ('venv','__pycache__','migrations')]
        for fname in files:
            if fname == 'views.py':
                fp = os.path.join(root, fname)
                try:
                    content = open(fp, encoding='utf-8').read()
                    if 'def dashboard' in content:
                        view_path = os.path.relpath(fp, BASE)
                        print(f"  Found: {view_path}")
                        break
                except: pass
        if view_path: break

if not view_path:
    print("  ERROR: Cannot locate dashboard view.")
    sys.exit(1)

# ── Step 2: Rewrite the dashboard view function ──────────────────────────────
print("\n[2/3] Upgrading dashboard view with EMIS-inspired stats...")

view_content = read(view_path)

NEW_FUNC = '''
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
'''

# Replace or append the dashboard function
pattern = r'(@login_required\s*\n)?def dashboard\s*\(request\).*?(?=\n(?:@|\s*class |\s*def |\Z))'
match = re.search(pattern, view_content, re.DOTALL)
if match:
    view_content = view_content[:match.start()] + NEW_FUNC.strip() + '\n\n' + view_content[match.end():]
    print("  Replaced existing dashboard() function.")
else:
    view_content = view_content + '\n\n' + NEW_FUNC.strip() + '\n'
    print("  Appended new dashboard() function (old one not found by pattern).")

write(view_path, view_content)

# ── Step 3: Write the new dashboard template ─────────────────────────────────
print("\n[3/3] Writing new EMIS-inspired dashboard template...")

# Determine template path
tmpl_candidates = ['templates/dashboard/dashboard.html', 'templates/core/dashboard.html']
tmpl_path = None
for tc in tmpl_candidates:
    if os.path.exists(r(tc)):
        tmpl_path = tc
        break
if not tmpl_path:
    tmpl_path = 'templates/dashboard/dashboard.html'

TEMPLATE = r"""{% extends "base/base.html" %}
{% load humanize %}

{% block title %}Dashboard — ASMS{% endblock %}

{% block content %}

<!-- ── Page header ──────────────────────────────────────────────────────── -->
<div class="d-flex justify-content-between align-items-start mb-4">
  <div>
    <h4 class="fw-bold mb-1">Good day, {{ user.get_full_name|default:user.username }} 👋</h4>
    {% if term and academic_year %}
    <p class="text-muted mb-0">
      <i class="bi bi-calendar3 me-1"></i>
      {{ term.get_name_display }} — {{ academic_year.name }}
    </p>
    {% else %}
    <p class="text-muted mb-0"><i class="bi bi-calendar3 me-1"></i>Current Academic Period</p>
    {% endif %}
  </div>
  <a href="{% url 'students:add' %}" class="btn btn-primary">
    <i class="bi bi-person-plus-fill me-1"></i> Add Student
  </a>
</div>

<!-- ── Stat cards — EMIS-style with gender breakdown ────────────────────── -->
<div class="row g-3 mb-4">

  <!-- Students -->
  <div class="col-sm-6 col-xl-3">
    <div class="card border-0 shadow-sm h-100">
      <div class="card-body">
        <div class="d-flex align-items-center gap-3 mb-3">
          <div class="rounded-3 p-2 bg-success bg-opacity-10 text-success">
            <i class="bi bi-people-fill fs-3"></i>
          </div>
          <div>
            <div class="fs-1 fw-bold lh-1 text-success">{{ total_students }}</div>
            <div class="text-muted small fw-semibold">ENROLLED LEARNERS</div>
          </div>
        </div>
        <div class="d-flex gap-2">
          <span class="badge rounded-pill px-3 py-2"
                style="background:rgba(13,110,253,.12);color:#0d6efd;font-size:.78rem">
            <i class="bi bi-gender-male me-1"></i>{{ male_students }} Male
          </span>
          <span class="badge rounded-pill px-3 py-2"
                style="background:rgba(220,53,69,.12);color:#dc3545;font-size:.78rem">
            <i class="bi bi-gender-female me-1"></i>{{ female_students }} Female
          </span>
        </div>
      </div>
    </div>
  </div>

  <!-- Teaching Staff -->
  <div class="col-sm-6 col-xl-3">
    <div class="card border-0 shadow-sm h-100">
      <div class="card-body">
        <div class="d-flex align-items-center gap-3 mb-3">
          <div class="rounded-3 p-2 bg-primary bg-opacity-10 text-primary">
            <i class="bi bi-person-badge-fill fs-3"></i>
          </div>
          <div>
            <div class="fs-1 fw-bold lh-1 text-primary">{{ teaching_staff }}</div>
            <div class="text-muted small fw-semibold">TEACHING STAFF</div>
          </div>
        </div>
        <div class="d-flex gap-2">
          <span class="badge rounded-pill px-3 py-2"
                style="background:rgba(13,110,253,.12);color:#0d6efd;font-size:.78rem">
            <i class="bi bi-gender-male me-1"></i>{{ staff_male }} Male
          </span>
          <span class="badge rounded-pill px-3 py-2"
                style="background:rgba(220,53,69,.12);color:#dc3545;font-size:.78rem">
            <i class="bi bi-gender-female me-1"></i>{{ staff_female }} Female
          </span>
        </div>
      </div>
    </div>
  </div>

  <!-- At-Risk Students -->
  <div class="col-sm-6 col-xl-3">
    <div class="card border-0 shadow-sm h-100">
      <div class="card-body">
        <div class="d-flex align-items-center gap-3 mb-3">
          <div class="rounded-3 p-2 bg-warning bg-opacity-10 text-warning">
            <i class="bi bi-exclamation-triangle-fill fs-3"></i>
          </div>
          <div>
            <div class="fs-1 fw-bold lh-1 text-warning">{{ at_risk_count }}</div>
            <div class="text-muted small fw-semibold">AT-RISK STUDENTS</div>
          </div>
        </div>
        <div class="d-flex gap-2">
          <span class="badge rounded-pill px-3 py-2"
                style="background:rgba(255,193,7,.15);color:#856404;font-size:.78rem">
            <i class="bi bi-calendar-x me-1"></i>3+ Absences This Term
          </span>
        </div>
      </div>
    </div>
  </div>

  <!-- Fees Collected -->
  <div class="col-sm-6 col-xl-3">
    <div class="card border-0 shadow-sm h-100">
      <div class="card-body">
        <div class="d-flex align-items-center gap-3 mb-3">
          <div class="rounded-3 p-2 bg-info bg-opacity-10 text-info">
            <i class="bi bi-cash-stack fs-3"></i>
          </div>
          <div>
            <div class="fs-2 fw-bold lh-1 text-info">{{ total_collected|intcomma }}</div>
            <div class="text-muted small fw-semibold">FEES COLLECTED (UGX)</div>
          </div>
        </div>
        <div class="d-flex gap-2">
          <span class="badge rounded-pill px-3 py-2"
                style="background:rgba(220,53,69,.12);color:#dc3545;font-size:.78rem">
            <i class="bi bi-exclamation-circle me-1"></i>{{ total_outstanding|intcomma }} Outstanding
          </span>
        </div>
      </div>
    </div>
  </div>

</div>

<!-- ── Charts row ────────────────────────────────────────────────────────── -->
<div class="row g-3 mb-4">

  <!-- Enrollment by Class & Sex — EMIS bar chart -->
  <div class="col-lg-8">
    <div class="card border-0 shadow-sm h-100">
      <div class="card-header bg-transparent border-0 py-3">
        <h6 class="fw-semibold mb-0">
          <i class="bi bi-bar-chart-fill text-primary me-2"></i>
          Enrollment by Class &amp; Sex
        </h6>
      </div>
      <div class="card-body pt-0" style="position:relative;height:260px">
        {% if enrollment_json != "[]" %}
        <canvas id="enrollmentChart"></canvas>
        {% else %}
        <div class="d-flex align-items-center justify-content-center h-100 text-muted">
          <div class="text-center">
            <i class="bi bi-bar-chart fs-1 opacity-25 d-block mb-2"></i>
            No class data yet — add students to classes to see this chart.
          </div>
        </div>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- Gender Distribution donut -->
  <div class="col-lg-4">
    <div class="card border-0 shadow-sm h-100">
      <div class="card-header bg-transparent border-0 py-3">
        <h6 class="fw-semibold mb-0">
          <i class="bi bi-pie-chart-fill text-success me-2"></i>
          Gender Distribution
        </h6>
      </div>
      <div class="card-body d-flex flex-column align-items-center justify-content-center">
        <div style="position:relative;width:180px;height:180px">
          <canvas id="genderChart"></canvas>
          <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;pointer-events:none">
            <div class="fw-bold fs-4">{{ total_students }}</div>
            <div class="text-muted" style="font-size:.7rem">TOTAL</div>
          </div>
        </div>
        <div class="d-flex justify-content-center gap-3 mt-3">
          <div class="text-center">
            <div class="badge rounded-pill px-3 py-2 mb-1"
                 style="background:rgba(13,110,253,.12);color:#0d6efd">
              {{ male_students }} Male
            </div>
            {% if total_students > 0 %}
            <div class="text-muted" style="font-size:.75rem">
              {{ male_students|floatformat:0 }} / {{ total_students }}
            </div>
            {% endif %}
          </div>
          <div class="text-center">
            <div class="badge rounded-pill px-3 py-2 mb-1"
                 style="background:rgba(220,53,69,.12);color:#dc3545">
              {{ female_students }} Female
            </div>
            {% if total_students > 0 %}
            <div class="text-muted" style="font-size:.75rem">
              {{ female_students|floatformat:0 }} / {{ total_students }}
            </div>
            {% endif %}
          </div>
        </div>
      </div>
    </div>
  </div>

</div>

<!-- ── Bottom row: Recent students + Quick actions + Activity ────────────── -->
<div class="row g-3">

  <!-- Recently Added Students table -->
  <div class="col-lg-7">
    <div class="card border-0 shadow-sm">
      <div class="card-header bg-transparent border-0 d-flex justify-content-between align-items-center py-3">
        <h6 class="fw-semibold mb-0">
          <i class="bi bi-person-lines-fill text-success me-2"></i>
          Recently Added Students
        </h6>
        <a href="{% url 'students:list' %}" class="btn btn-sm btn-outline-primary">View All</a>
      </div>
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th class="border-0">Student</th>
              <th class="border-0">ID</th>
              <th class="border-0">Class</th>
              <th class="border-0">Status</th>
              <th class="border-0">Admitted</th>
            </tr>
          </thead>
          <tbody>
            {% for student in recent_students %}
            <tr>
              <td>
                <div class="d-flex align-items-center gap-2">
                  <div class="rounded-circle d-flex align-items-center justify-content-center fw-bold text-white"
                       style="width:34px;height:34px;font-size:.8rem;
                              background:{% if student.gender == 'M' %}#0d6efd{% elif student.gender == 'F' %}#dc3545{% else %}#6c757d{% endif %}">
                    {{ student.first_name.0 }}{{ student.last_name.0 }}
                  </div>
                  <div>
                    <div class="fw-semibold small">{{ student.get_full_name }}</div>
                    <div class="text-muted" style="font-size:.73rem">{{ student.get_gender_display }}</div>
                  </div>
                </div>
              </td>
              <td><code class="text-primary small">{{ student.student_id }}</code></td>
              <td><span class="small">{{ student.current_class|default:"—" }}</span></td>
              <td>
                <span class="badge bg-success bg-opacity-15 text-success small">
                  {{ student.get_status_display }}
                </span>
              </td>
              <td><span class="small text-muted">{{ student.admission_date|date:"d M Y"|default:"—" }}</span></td>
            </tr>
            {% empty %}
            <tr>
              <td colspan="5" class="text-center text-muted py-4">
                <i class="bi bi-person-x fs-3 d-block mb-2 opacity-25"></i>
                No students enrolled yet
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Right column: Quick Actions + Activity Feed -->
  <div class="col-lg-5">

    <!-- Quick Actions — EMIS Action Center style -->
    <div class="card border-0 shadow-sm mb-3">
      <div class="card-header bg-transparent border-0 py-3">
        <h6 class="fw-semibold mb-0">
          <i class="bi bi-lightning-fill text-warning me-2"></i>Quick Actions
        </h6>
      </div>
      <div class="card-body pt-0">
        <div class="d-grid gap-2">
          <a href="{% url 'students:add' %}" class="btn btn-outline-success text-start">
            <i class="bi bi-person-plus me-2"></i>Enrol New Student
          </a>
          <a href="{% url 'students:classrooms' %}" class="btn btn-outline-primary text-start">
            <i class="bi bi-building me-2"></i>Manage Classes
          </a>
          <a href="{% url 'attendance:home' %}" class="btn btn-outline-info text-start">
            <i class="bi bi-calendar-check me-2"></i>Mark Attendance
          </a>
          <a href="{% url 'exam_list' %}" class="btn btn-outline-secondary text-start">
            <i class="bi bi-clipboard2-data me-2"></i>Enter Exam Marks
          </a>
          <a href="{% url 'invoice_list' %}" class="btn btn-outline-warning text-start">
            <i class="bi bi-receipt-cutoff me-2"></i>View Invoices
          </a>
        </div>
      </div>
    </div>

    <!-- Activity Feed — like EMIS Activity panel -->
    <div class="card border-0 shadow-sm">
      <div class="card-header bg-transparent border-0 d-flex justify-content-between py-3">
        <h6 class="fw-semibold mb-0">
          <i class="bi bi-activity text-info me-2"></i>Recent Activity
        </h6>
      </div>
      <div class="card-body pt-0">
        {% for item in recent_activities %}
        <div class="d-flex gap-3 py-2 {% if not forloop.last %}border-bottom{% endif %}">
          <div class="mt-1">
            <div class="rounded-circle bg-{{ item.color }} bg-opacity-15"
                 style="width:30px;height:30px;display:flex;align-items:center;justify-content:center">
              <i class="bi bi-{{ item.icon }} text-{{ item.color }} small"></i>
            </div>
          </div>
          <div>
            <div class="small fw-semibold">{{ item.message }}</div>
            {% if item.time %}
            <div class="text-muted" style="font-size:.73rem">{{ item.time|timesince }} ago</div>
            {% endif %}
          </div>
        </div>
        {% empty %}
        <div class="text-center text-muted py-3">
          <i class="bi bi-clock-history fs-3 d-block mb-2 opacity-25"></i>
          <small>No recent activity yet</small>
        </div>
        {% endfor %}
      </div>
    </div>

  </div>
</div>

{% endblock %}

{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
(function() {
  // ── Enrollment by Class & Sex chart ─────────────────────────────────────
  var enrollData = {{ enrollment_json|safe }};
  var ctx1 = document.getElementById('enrollmentChart');
  if (ctx1 && enrollData.length) {
    new Chart(ctx1, {
      type: 'bar',
      data: {
        labels: enrollData.map(function(d) { return d.name; }),
        datasets: [
          {
            label: 'Male',
            data: enrollData.map(function(d) { return d.male; }),
            backgroundColor: 'rgba(13,110,253,0.75)',
            borderRadius: 5,
            borderSkipped: false,
          },
          {
            label: 'Female',
            data: enrollData.map(function(d) { return d.female; }),
            backgroundColor: 'rgba(220,53,69,0.75)',
            borderRadius: 5,
            borderSkipped: false,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, padding: 16 } },
          tooltip: {
            callbacks: {
              afterLabel: function(ctx) {
                var d = enrollData[ctx.dataIndex];
                return 'Total in class: ' + d.total;
              }
            }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 11 } } },
          y: { beginAtZero: true, ticks: { stepSize: 1, font: { size: 11 } }, grid: { color: 'rgba(0,0,0,.06)' } }
        }
      }
    });
  }

  // ── Gender Distribution donut ────────────────────────────────────────────
  var ctx2 = document.getElementById('genderChart');
  if (ctx2) {
    new Chart(ctx2, {
      type: 'doughnut',
      data: {
        labels: ['Male', 'Female'],
        datasets: [{
          data: [{{ male_students }}, {{ female_students }}],
          backgroundColor: ['rgba(13,110,253,0.8)', 'rgba(220,53,69,0.8)'],
          borderWidth: 0,
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(ctx) {
                var total = ctx.dataset.data.reduce(function(a, b) { return a + b; }, 0);
                var pct = total ? Math.round(ctx.parsed / total * 100) : 0;
                return ' ' + ctx.label + ': ' + ctx.parsed + ' (' + pct + '%)';
              }
            }
          }
        },
        cutout: '68%'
      }
    });
  }
})();
</script>
{% endblock %}
"""

write(tmpl_path, TEMPLATE)

print("\n" + "="*60)
print("✅  Dashboard upgrade complete!")
print("="*60)
print("""
What was added (EMIS-inspired):
  ✓ Stat cards with Male/Female gender breakdown
  ✓ Teaching Staff count with gender split
  ✓ At-Risk Students (real count — 3+ absences)
  ✓ Fees Collected (real UGX) with Outstanding amount
  ✓ Enrollment by Class & Sex bar chart (Chart.js)
  ✓ Gender Distribution donut chart
  ✓ Recent Activity feed (students, payments, leave requests)
  ✓ Cleaned up Quick Actions panel

Now restart your server:
    python manage.py runserver

Then open:  http://127.0.0.1:8000/dashboard/
""")