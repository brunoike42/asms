# fix_parent_base.py
path = 'templates/parent/base.html'
content = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <meta name="theme-color" content="#1B3A6B">
  <title>{% block title %}Parent Portal | ASMS{% endblock %}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --pp-primary:   #1B3A6B;
      --pp-accent:    #1a56db;
      --pp-secondary: #0A7B8C;
      --pp-warning:   #e3a008;
      --pp-danger:    #e02424;
      --pp-bg:        #F0F2F5;
      --pp-card:      #ffffff;
      --pp-text:      #1a202c;
      --pp-muted:     #718096;
      --pp-border:    #edf2f7;
      --nav-height:   64px;
    }
    * { box-sizing: border-box; }
    body {
      background: var(--pp-bg);
      color: var(--pp-text);
      font-family: \'Inter\', sans-serif;
      font-size: 14px;
      padding-top: 60px;
      padding-bottom: calc(var(--nav-height) + 8px);
      min-height: 100vh;
    }

    /* ── Top Header ── */
    .pp-header {
      position: fixed; top: 0; left: 0; right: 0;
      height: 60px;
      background: var(--pp-primary);
      display: flex; align-items: center;
      justify-content: space-between;
      padding: 0 16px; z-index: 1000;
      box-shadow: 0 2px 8px rgba(0,0,0,.2);
    }
    .pp-header .school-name {
      color: #fff; font-weight: 700; font-size: 15px; letter-spacing: -.01em;
    }
    .pp-header .header-right { display: flex; align-items: center; gap: 12px; }
    .pp-header .notif-btn {
      position: relative; color: #fff;
      background: rgba(255,255,255,.15);
      border: none; border-radius: 50%;
      width: 36px; height: 36px;
      display: flex; align-items: center; justify-content: center;
      text-decoration: none; font-size: 17px;
      transition: background .15s;
    }
    .pp-header .notif-btn:hover { background: rgba(255,255,255,.28); }
    .pp-header .notif-badge {
      position: absolute; top: -3px; right: -3px;
      background: var(--pp-danger); color: #fff;
      font-size: 9px; font-weight: 700;
      border-radius: 50%; width: 16px; height: 16px;
      display: flex; align-items: center; justify-content: center;
    }
    .pp-header .avatar {
      width: 34px; height: 34px;
      background: rgba(255,255,255,.2);
      border: 2px solid rgba(255,255,255,.35);
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      color: #fff; font-weight: 700; font-size: 13px;
      text-decoration: none; transition: background .15s;
    }
    .pp-header .avatar:hover { background: rgba(255,255,255,.35); }

    /* ── Child Selector ── */
    .child-selector {
      background: #fff; border-bottom: 1px solid var(--pp-border);
      padding: 8px 16px; display: flex; gap: 8px;
      overflow-x: auto; -webkit-overflow-scrolling: touch;
    }
    .child-selector::-webkit-scrollbar { display: none; }
    .child-chip {
      display: flex; align-items: center; gap: 6px;
      background: var(--pp-bg); border: 1.5px solid var(--pp-border);
      border-radius: 20px; padding: 5px 14px;
      white-space: nowrap; font-size: 13px; font-weight: 500;
      color: var(--pp-text); text-decoration: none;
      transition: all .15s; flex-shrink: 0;
    }
    .child-chip:hover {
      border-color: var(--pp-primary);
      color: var(--pp-primary);
      background: rgba(27,58,107,.06);
    }
    .child-chip.active {
      background: var(--pp-primary);
      border-color: var(--pp-primary); color: #fff;
    }
    .child-chip .child-avatar {
      width: 22px; height: 22px; border-radius: 50%;
      background: rgba(255,255,255,.3);
      display: flex; align-items: center; justify-content: center;
      font-size: 10px; font-weight: 700;
    }

    /* ── Page Container ── */
    .pp-page { padding: 12px 16px; max-width: 680px; margin: 0 auto; }

    /* ── Cards ── */
    .pp-card {
      background: var(--pp-card); border-radius: 12px;
      padding: 16px; margin-bottom: 12px;
      box-shadow: 0 1px 3px rgba(0,0,0,.06);
      border: 1px solid var(--pp-border);
      transition: transform .15s, box-shadow .15s;
    }
    a.pp-card, .pp-card-clickable {
      cursor: pointer; text-decoration: none; color: inherit; display: block;
    }
    a.pp-card:hover, .pp-card-clickable:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 16px rgba(0,0,0,.1);
      border-color: rgba(27,58,107,.2);
    }
    .pp-card-header {
      display: flex; justify-content: space-between;
      align-items: center; margin-bottom: 12px;
    }
    .pp-card-title { font-weight: 700; font-size: 14px; color: var(--pp-text); }
    .pp-card-link  { font-size: 12px; color: var(--pp-accent); text-decoration: none; }
    .pp-card-link:hover { text-decoration: underline; }

    /* ── Stat Pills ── */
    .stat-row { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .stat-pill {
      background: var(--pp-bg); border-radius: 10px;
      padding: 12px; text-align: center;
      border: 1px solid var(--pp-border);
      transition: transform .15s, box-shadow .15s;
    }
    .stat-pill:hover {
      transform: translateY(-1px);
      box-shadow: 0 3px 8px rgba(0,0,0,.08);
    }
    .stat-pill .val { font-size: 22px; font-weight: 800; line-height: 1; }
    .stat-pill .lbl { font-size: 11px; color: var(--pp-muted); margin-top: 2px; font-weight: 500; }
    .stat-pill.green .val { color: var(--pp-secondary); }
    .stat-pill.blue  .val { color: var(--pp-accent); }
    .stat-pill.red   .val { color: var(--pp-danger); }
    .stat-pill.amber .val { color: var(--pp-warning); }

    /* ── Bottom Navigation ── */
    .pp-bottom-nav {
      position: fixed; bottom: 0; left: 0; right: 0;
      height: var(--nav-height); background: #fff;
      border-top: 1px solid var(--pp-border);
      display: flex; z-index: 1000;
      box-shadow: 0 -2px 12px rgba(0,0,0,.08);
    }
    .pp-nav-item {
      flex: 1; display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      gap: 2px; color: var(--pp-muted); text-decoration: none;
      font-size: 10px; font-weight: 500;
      transition: color .15s, background .15s;
      padding: 6px 0; position: relative;
    }
    .pp-nav-item i { font-size: 20px; }
    .pp-nav-item:hover { color: var(--pp-primary); background: rgba(27,58,107,.04); }
    .pp-nav-item.active { color: var(--pp-primary); }
    .pp-nav-item.active::after {
      content: \'\';
      position: absolute; top: 0; left: 25%; right: 25%;
      height: 2px; background: var(--pp-primary); border-radius: 0 0 3px 3px;
    }

    /* ── Activity Feed ── */
    .feed-item {
      display: flex; gap: 10px; padding: 10px 0;
      border-bottom: 1px solid var(--pp-border);
    }
    .feed-item:last-child { border-bottom: none; }
    .feed-icon {
      width: 36px; height: 36px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0; font-size: 16px;
    }
    .feed-content .feed-title { font-weight: 600; font-size: 13px; }
    .feed-content .feed-body  { color: var(--pp-muted); font-size: 12px; }
    .feed-content .feed-time  { font-size: 11px; color: var(--pp-muted); margin-top: 2px; }

    /* ── Alerts ── */
    .pp-alert {
      border-radius: 10px; padding: 12px 14px;
      margin-bottom: 10px; display: flex;
      align-items: flex-start; gap: 10px; font-size: 13px;
    }
    .pp-alert.urgent  { background: #fef2f2; border: 1px solid #fee2e2; color: #991b1b; }
    .pp-alert.info    { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e3a8a; }
    .pp-alert.success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
    .pp-alert.warning { background: #fffbeb; border: 1px solid #fde68a; color: #92400e; }

    /* ── Section Label ── */
    .pp-section-label {
      font-size: 11px; font-weight: 700;
      color: var(--pp-muted); letter-spacing: .06em;
      text-transform: uppercase; margin: 16px 0 6px;
    }

    /* ── List Items ── */
    .pp-list-item {
      display: flex; justify-content: space-between;
      align-items: center; padding: 10px 0;
      border-bottom: 1px solid var(--pp-border); gap: 8px;
      transition: background .12s; border-radius: 6px;
    }
    .pp-list-item:last-child { border-bottom: none; }
    .pp-list-item:hover { background: #f7fafc; margin: 0 -8px; padding: 10px 8px; }
    .pp-list-item .item-main { flex: 1; min-width: 0; }
    .pp-list-item .item-title { font-weight: 600; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .pp-list-item .item-sub   { font-size: 12px; color: var(--pp-muted); }

    /* ── Badges ── */
    .pp-badge {
      display: inline-block; padding: 2px 8px;
      border-radius: 20px; font-size: 11px; font-weight: 600;
      transition: opacity .12s;
    }
    a.pp-badge:hover { opacity: .8; }
    .pp-badge.green  { background: #d1fae5; color: #065f46; }
    .pp-badge.red    { background: #fee2e2; color: #991b1b; }
    .pp-badge.amber  { background: #fef3c7; color: #92400e; }
    .pp-badge.blue   { background: #dbeafe; color: #1e3a8a; }
    .pp-badge.grey   { background: #f3f4f6; color: #374151; }
    .pp-badge.navy   { background: #e8eef6; color: #1B3A6B; }

    /* ── Progress Bar ── */
    .pp-progress { height: 8px; border-radius: 4px; background: var(--pp-border); overflow: hidden; }
    .pp-progress-bar { height: 100%; border-radius: 4px; transition: width .4s; }

    /* ── Calendar ── */
    .att-calendar { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; }
    .att-day-header { text-align: center; font-size: 10px; font-weight: 700; color: var(--pp-muted); padding: 4px 0; }
    .att-day {
      aspect-ratio: 1; border-radius: 6px;
      display: flex; align-items: center; justify-content: center;
      font-size: 12px; font-weight: 500; cursor: default;
    }
    .att-day.present { background: #d1fae5; color: #065f46; }
    .att-day.absent  { background: #fee2e2; color: #991b1b; }
    .att-day.late    { background: #fef3c7; color: #92400e; }
    .att-day.empty   { background: transparent; }
    .att-day.today   { border: 2px solid var(--pp-primary); }

    /* ── Responsive ── */
    @media (min-width: 640px) {
      .pp-page { padding: 20px 24px; }
      .stat-row { grid-template-columns: repeat(4, 1fr); }
    }

    /* ── Toast ── */
    .pp-toast-container {
      position: fixed; bottom: 80px; left: 50%;
      transform: translateX(-50%); z-index: 2000;
      width: 90%; max-width: 380px;
    }
    .pp-toast {
      background: #1f2937; color: #fff;
      padding: 12px 16px; border-radius: 10px;
      font-size: 13px; margin-bottom: 8px;
      display: flex; align-items: center; gap: 10px;
      box-shadow: 0 4px 12px rgba(0,0,0,.2);
    }

    /* ── Btn overrides ── */
    .btn-primary { background: var(--pp-primary); border-color: var(--pp-primary); }
    .btn-primary:hover { background: #152f58; border-color: #152f58; }
  </style>
</head>
<body>

<!-- Top Header -->
<header class="pp-header">
  <div class="d-flex align-items-center gap-2">
    <a href="{% url \'parent:dashboard\' %}" class="text-decoration-none">
      <span class="school-name">
        {% if request.tenant %}{{ request.tenant.name }}{% else %}ASMS{% endif %}
      </span>
    </a>
  </div>
  <div class="header-right">
    <a href="{% url \'parent:notifications\' %}" class="notif-btn">
      <i class="bi bi-bell-fill"></i>
      {% if unread_count %}
      <span class="notif-badge" id="notifBadge">{{ unread_count }}</span>
      {% else %}
      <span class="notif-badge d-none" id="notifBadge"></span>
      {% endif %}
    </a>
    <a href="{% url \'parent:profile\' %}" class="avatar">
      {{ request.user.first_name|first|upper }}{{ request.user.last_name|first|upper }}
    </a>
  </div>
</header>

{% if messages %}
<div class="pp-toast-container" id="toastContainer">
  {% for msg in messages %}
  <div class="pp-toast">
    {% if \'error\' in msg.tags %}<i class="bi bi-exclamation-circle-fill text-danger"></i>
    {% elif \'success\' in msg.tags %}<i class="bi bi-check-circle-fill" style="color:#0A7B8C"></i>
    {% else %}<i class="bi bi-info-circle-fill" style="color:#1a56db"></i>{% endif %}
    {{ msg }}
  </div>
  {% endfor %}
</div>
{% endif %}

<!-- Child Selector -->
{% if students %}
<div class="child-selector">
  {% for s in students %}
  <a href="{% url \'parent:child_academic\' student_pk=s.pk %}"
     class="child-chip {% if student and student.pk == s.pk %}active{% endif %}">
    <div class="child-avatar">{{ s.first_name|first }}{{ s.last_name|first }}</div>
    {{ s.first_name }}
  </a>
  {% endfor %}
</div>
{% endif %}

<!-- Main Content -->
<div class="pp-page">
  {% block content %}{% endblock %}
</div>

<!-- Bottom Navigation -->
<nav class="pp-bottom-nav">
  <a href="{% url \'parent:dashboard\' %}"
     class="pp-nav-item {% if request.resolver_match.url_name == \'dashboard\' %}active{% endif %}">
    <i class="bi bi-house{% if request.resolver_match.url_name == \'dashboard\' %}-fill{% endif %}"></i>
    Home
  </a>
  {% if student %}
  <a href="{% url \'parent:child_academic\' student_pk=student.pk %}"
     class="pp-nav-item {% if \'academic\' in request.resolver_match.url_name %}active{% endif %}">
    <i class="bi bi-bar-chart{% if \'academic\' in request.resolver_match.url_name %}-fill{% endif %}"></i>
    Academic
  </a>
  <a href="{% url \'parent:child_fees\' student_pk=student.pk %}"
     class="pp-nav-item {% if \'fees\' in request.resolver_match.url_name %}active{% endif %}">
    <i class="bi bi-credit-card{% if \'fees\' in request.resolver_match.url_name %}-fill{% endif %}"></i>
    Fees
  </a>
  <a href="{% url \'parent:child_behaviour\' student_pk=student.pk %}"
     class="pp-nav-item {% if \'behaviour\' in request.resolver_match.url_name %}active{% endif %}">
    <i class="bi bi-shield{% if \'behaviour\' in request.resolver_match.url_name %}-fill{% endif %}"></i>
    Behaviour
  </a>
  {% else %}
  <a href="{% url \'parent:notifications\' %}"
     class="pp-nav-item {% if \'notifications\' in request.resolver_match.url_name %}active{% endif %}">
    <i class="bi bi-bell{% if \'notifications\' in request.resolver_match.url_name %}-fill{% endif %}"></i>
    Alerts
  </a>
  <a href="#" class="pp-nav-item"><i class="bi bi-credit-card"></i> Fees</a>
  <a href="#" class="pp-nav-item"><i class="bi bi-shield"></i> Behaviour</a>
  {% endif %}
  <a href="{% url \'parent:profile\' %}"
     class="pp-nav-item {% if \'profile\' in request.resolver_match.url_name %}active{% endif %}">
    <i class="bi bi-person{% if \'profile\' in request.resolver_match.url_name %}-fill{% endif %}"></i>
    Profile
  </a>
</nav>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
setTimeout(() => {
  const c = document.getElementById(\'toastContainer\');
  if (c) c.style.display = \'none\';
}, 3500);
{% if request.user.is_authenticated %}
setInterval(() => {
  fetch("{% url \'parent:notification_count\' %}")
    .then(r => r.json())
    .then(data => {
      const badge = document.getElementById(\'notifBadge\');
      if (badge) {
        badge.textContent = data.unread || \'\';
        badge.classList.toggle(\'d-none\', !data.unread);
      }
    }).catch(() => {});
}, 60000);
{% endif %}
</script>
{% block extra_js %}{% endblock %}
</body>
</html>'''

open(path, 'w', encoding='utf-8').write(content)
print("✅ templates/parent/base.html updated with:")
print("   • Inter font (matches ASMS staff dashboard)")
print("   • #1B3A6B navy (matches ASMS primary color)")
print("   • Hover lift on all cards")
print("   • Hover highlight on bottom nav items")
print("   • Active indicator bar on bottom nav")
print("   • Hover on list items, badges, child chips")
print("   • btn-primary overridden to ASMS navy")