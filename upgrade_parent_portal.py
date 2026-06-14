#!/usr/bin/env python3
r"""
upgrade_parent_portal_phase2.py
=================================
Phase 2 Parent Portal Upgrade:
  ① base.html   – sidebar layout matching asms_parent_portal_complete.html
  ② library.html / timetable.html / documents.html / messages.html
  ③ ParentMessage model appended to models.py
  ④ 6 new views appended to views.py
  ⑤ 6 new URL patterns patched into urls.py

Run from:  E:\DJANGO\ASMS\asms
    python upgrade_parent_portal_phase2.py
    python manage.py makemigrations parent_portal
    python manage.py migrate
    python manage.py runserver
"""
import os

GUARD = '# --- PHASE 2 PARENT PORTAL ---'

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  ✅ {path}')

def safe_append(path, content):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
    except FileNotFoundError:
        src = ''
    if GUARD in src:
        print(f'  ⏭  {path} – already patched')
        return
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n\n' + content)
    print(f'  ✅ {path} (appended)')

def patch_urls(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
    except FileNotFoundError:
        print(f'  ⚠  {path} not found'); return
    if GUARD in src:
        print(f'  ⏭  {path} – already patched'); return
    insert = (
        f"\n    {GUARD}\n"
        "    path('child/<int:student_pk>/library/',   views.child_library,   name='child_library'),\n"
        "    path('child/<int:student_pk>/timetable/', views.child_timetable, name='child_timetable'),\n"
        "    path('child/<int:student_pk>/documents/', views.child_documents, name='child_documents'),\n"
        "    path('messages/',         views.parent_messages, name='parent_messages'),\n"
        "    path('messages/send/',    views.message_send,    name='message_send'),\n"
        "    path('messages/meeting/', views.meeting_request, name='meeting_request'),\n"
    )
    close = src.rfind(']')
    if close == -1:
        print(f'  ⚠  No ] found in {path}'); return
    with open(path, 'w', encoding='utf-8') as f:
        f.write(src[:close] + insert + src[close:])
    print(f'  ✅ {path} (patched)')


# ════════════════════════════════════════════════════════════════════════
# 1.  templates/parent/base.html  (FULL REWRITE – sidebar layout)
# ════════════════════════════════════════════════════════════════════════
BASE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <meta name="theme-color" content="#042C53">
  <title>{% block title %}Parent Portal | ASMS{% endblock %}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --pp-dark:    #042C53;
      --pp-sidebar: #0C447C;
      --pp-accent:  #185FA5;
      --pp-primary: #1B3A6B;
      --pp-secondary:#0A7B8C;
      --pp-warning: #E3A008;
      --pp-danger:  #E02424;
      --pp-bg:      #F0F2F5;
      --pp-card:    #ffffff;
      --pp-text:    #1A202C;
      --pp-muted:   #6B7280;
      --pp-border:  #E5E7EB;
      --pp-sbtext:  #B5D4F4;
      --pp-sblabel: #85B7EB;
      --hdr:        48px;
      --sb-w:       172px;
    }
    *, *::before, *::after { box-sizing: border-box; }
    html, body { margin: 0; min-height: 100%; }
    body {
      font-family: 'Inter', sans-serif;
      font-size: 13px;
      background: var(--pp-bg);
      color: var(--pp-text);
    }

    /* ─── HEADER ─── */
    .pp-hdr {
      position: fixed; top: 0; left: 0; right: 0;
      height: var(--hdr); background: var(--pp-dark);
      display: flex; align-items: center; gap: 10px;
      padding: 0 14px; z-index: 1100;
      box-shadow: 0 2px 10px rgba(0,0,0,.35);
    }
    .pp-hdr .hbg-btn {
      display: none; background: none; border: none;
      color: var(--pp-sbtext); font-size: 22px; padding: 0;
      cursor: pointer; line-height: 1; flex-shrink: 0;
    }
    .pp-hdr .school-name {
      font-size: 13px; font-weight: 600; color: var(--pp-sbtext);
      white-space: nowrap; text-decoration: none; flex-shrink: 0;
    }
    .pp-hdr .chip-row {
      display: flex; gap: 5px; flex: 1;
      overflow-x: auto; -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
    }
    .pp-hdr .chip-row::-webkit-scrollbar { display: none; }
    .child-chip {
      display: flex; align-items: center; gap: 5px;
      padding: 4px 10px; border-radius: 20px;
      border: 1.5px solid rgba(255,255,255,.2);
      background: transparent; color: var(--pp-sbtext);
      font-size: 11px; font-weight: 500; white-space: nowrap;
      text-decoration: none; transition: all .15s; flex-shrink: 0;
    }
    .child-chip:hover { border-color: rgba(255,255,255,.5); color: #fff; }
    .child-chip.on { border-color: #EF9F27; background: rgba(239,159,39,.12); color: #FAC775; }
    .child-chip .ch-av {
      width: 20px; height: 20px; border-radius: 50%;
      background: var(--pp-accent); display: flex; align-items: center;
      justify-content: center; font-size: 8px; font-weight: 700;
      color: #fff; flex-shrink: 0;
    }
    .pp-hdr .hdr-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
    .notif-btn {
      position: relative; color: var(--pp-sbtext);
      background: rgba(255,255,255,.1); border: none; border-radius: 50%;
      width: 32px; height: 32px; display: flex; align-items: center;
      justify-content: center; text-decoration: none; font-size: 15px;
      transition: background .15s;
    }
    .notif-btn:hover { background: rgba(255,255,255,.22); color: #fff; }
    .notif-badge {
      position: absolute; top: -3px; right: -3px;
      background: var(--pp-danger); color: #fff;
      font-size: 8px; font-weight: 700; border-radius: 50%;
      width: 15px; height: 15px;
      display: flex; align-items: center; justify-content: center;
    }
    .user-av {
      width: 30px; height: 30px; border-radius: 50%;
      background: var(--pp-accent); border: 2px solid rgba(255,255,255,.3);
      display: flex; align-items: center; justify-content: center;
      color: #fff; font-weight: 700; font-size: 11px;
      text-decoration: none; transition: border-color .15s;
    }
    .user-av:hover { border-color: rgba(255,255,255,.7); }

    /* ─── LAYOUT ─── */
    .pp-layout {
      display: flex;
      margin-top: var(--hdr);
      min-height: calc(100vh - var(--hdr));
    }

    /* ─── SIDEBAR ─── */
    .pp-sidebar {
      width: var(--sb-w); background: var(--pp-sidebar);
      position: fixed; top: var(--hdr); bottom: 0;
      overflow-y: auto; overflow-x: hidden; z-index: 1050;
      scrollbar-width: thin;
      scrollbar-color: rgba(255,255,255,.12) transparent;
      transition: transform .22s ease;
    }
    .pp-sidebar::-webkit-scrollbar { width: 4px; }
    .pp-sidebar::-webkit-scrollbar-thumb { background: rgba(255,255,255,.15); border-radius: 2px; }
    .sb-child-info {
      padding: 10px 13px 9px;
      border-bottom: 0.5px solid rgba(255,255,255,.12);
      margin-bottom: 3px;
    }
    .sb-child-name {
      font-size: 12px; font-weight: 600; color: #fff; margin: 0;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .sb-child-class { font-size: 10px; color: var(--pp-sblabel); margin: 0; }
    .ng {
      padding: 6px 13px 2px; font-size: 10px; font-weight: 600;
      color: var(--pp-sblabel); letter-spacing: .05em;
      text-transform: uppercase; margin-top: 5px;
    }
    .nv {
      display: flex; align-items: center; gap: 8px;
      padding: 7px 13px; font-size: 12px; font-weight: 400;
      color: var(--pp-sbtext); text-decoration: none;
      transition: background .12s; white-space: nowrap;
    }
    .nv i { font-size: 13px; flex-shrink: 0; }
    .nv:hover { background: rgba(255,255,255,.08); color: #fff; }
    .nv.on { background: var(--pp-accent); color: #fff; font-weight: 500; }

    /* ─── MAIN ─── */
    .pp-main {
      flex: 1; margin-left: var(--sb-w);
      padding: 16px; background: var(--pp-bg);
      min-height: calc(100vh - var(--hdr));
    }
    .pp-inner { max-width: 960px; }

    /* ─── CARDS ─── */
    .pp-card {
      background: var(--pp-card); border-radius: 10px;
      padding: 14px; margin-bottom: 12px;
      border: 0.5px solid var(--pp-border);
      box-shadow: 0 1px 3px rgba(0,0,0,.04);
    }
    .pp-card:last-child { margin-bottom: 0; }
    .pp-card h6 {
      font-size: 13px; font-weight: 600; margin: 0 0 11px; color: var(--pp-text);
    }
    .pp-card-link { display: flex; justify-content: space-between; align-items: center; }

    /* ─── METRIC CARDS ─── */
    .mc-grid { display: grid; gap: 9px; margin-bottom: 12px; }
    .mc-grid.c2 { grid-template-columns: repeat(2,1fr); }
    .mc-grid.c3 { grid-template-columns: repeat(3,1fr); }
    .mc-grid.c4 { grid-template-columns: repeat(4,1fr); }
    .mc {
      background: #F9FAFB; border: 0.5px solid var(--pp-border);
      border-radius: 8px; padding: 11px 13px;
    }
    .mc .ml { font-size: 11px; color: var(--pp-muted); margin: 0 0 2px; }
    .mc .mv { font-size: 20px; font-weight: 600; margin: 0; }
    .mc .ms { font-size: 10px; color: var(--pp-muted); margin: 2px 0 0; }
    .mv.danger, .ms.danger { color: var(--pp-danger); }
    .mv.warning, .ms.warning { color: var(--pp-warning); }
    .mv.success, .ms.success { color: var(--pp-secondary); }

    /* ─── BADGES ─── */
    .bd { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 500; }
    .bd.green  { background: #D1FAE5; color: #065F46; }
    .bd.red    { background: #FEE2E2; color: #991B1B; }
    .bd.amber  { background: #FEF3C7; color: #92400E; }
    .bd.blue   { background: #DBEAFE; color: #1E3A8A; }
    .bd.grey   { background: #F3F4F6; color: #374151; }
    .bd.navy   { background: #E8EEF6; color: #1B3A6B; }

    /* ─── TABLE ─── */
    .pp-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .pp-table th {
      text-align: left; padding: 6px 9px; font-size: 11px; font-weight: 500;
      color: var(--pp-muted); border-bottom: 0.5px solid var(--pp-border);
      background: #F9FAFB;
    }
    .pp-table td { padding: 7px 9px; border-bottom: 0.5px solid var(--pp-border); }
    .pp-table tr:last-child td { border-bottom: none; }
    .pp-table tr:hover td { background: #F9FAFB; }

    /* ─── PAY BUTTONS ─── */
    .pay-btn {
      display: flex; align-items: center; gap: 10px;
      padding: 9px 12px; border-radius: 8px;
      border: 0.5px solid var(--pp-border); background: var(--pp-card);
      cursor: pointer; font-size: 12px; font-family: 'Inter', sans-serif;
      color: var(--pp-text); width: 100%; margin-bottom: 8px;
      text-align: left; transition: background .12s;
    }
    .pay-btn:last-child { margin-bottom: 0; }
    .pay-btn:hover { background: #F9FAFB; }

    /* ─── PROGRESS ─── */
    .pp-prog { height: 7px; border-radius: 4px; background: var(--pp-border); overflow: hidden; margin-top: 5px; }
    .pp-prog-fill { height: 100%; border-radius: 4px; transition: width .4s; }

    /* ─── PAGE TITLE ─── */
    .pp-sec-title { font-size: 15px; font-weight: 700; color: var(--pp-text); margin: 0 0 12px; }
    .pp-sec-sub   { font-size: 11px; color: var(--pp-muted); margin: -8px 0 12px; }

    /* ─── ALERTS ─── */
    .pp-alert {
      border-radius: 8px; padding: 10px 13px; margin-bottom: 10px;
      display: flex; align-items: flex-start; gap: 9px; font-size: 12px;
    }
    .pp-alert.red   { background: #FEF2F2; border: 0.5px solid #FECACA; color: #991B1B; }
    .pp-alert.amber { background: #FFFBEB; border: 0.5px solid #FDE68A; color: #92400E; }
    .pp-alert.blue  { background: #EFF6FF; border: 0.5px solid #BFDBFE; color: #1E3A8A; }
    .pp-alert.green { background: #F0FDF4; border: 0.5px solid #BBF7D0; color: #166534; }

    /* ─── MESSAGES ─── */
    .msg-item {
      display: flex; gap: 9px; padding-bottom: 10px; margin-bottom: 10px;
      border-bottom: 0.5px solid var(--pp-border);
    }
    .msg-item:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
    .msg-av {
      width: 30px; height: 30px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 10px; font-weight: 600; flex-shrink: 0;
    }
    .unread-dot { width: 7px; height: 7px; background: var(--pp-accent); border-radius: 50%; flex-shrink: 0; margin-top: 5px; }

    /* ─── TIMETABLE ─── */
    .tt-cell { padding: 3px 5px; border-radius: 3px; font-size: 10px; font-weight: 500; text-align: center; }

    /* ─── FORM ─── */
    .pp-input, .pp-select, .pp-textarea {
      width: 100%; padding: 7px 10px;
      border: 0.5px solid var(--pp-border); border-radius: 7px;
      font-size: 13px; font-family: 'Inter', sans-serif;
      color: var(--pp-text); background: var(--pp-card);
      box-sizing: border-box;
    }
    .pp-textarea { resize: vertical; }
    .pp-label { font-size: 11px; color: var(--pp-muted); display: block; margin-bottom: 3px; }
    .pp-field { margin-bottom: 10px; }
    .btn-pp {
      padding: 8px 18px; background: var(--pp-accent); color: #fff;
      border: none; border-radius: 8px; font-size: 13px; font-weight: 500;
      cursor: pointer; font-family: 'Inter', sans-serif; transition: background .15s;
    }
    .btn-pp:hover { background: #144F8C; }
    .btn-pp-sm {
      padding: 4px 10px; border: 0.5px solid var(--pp-border);
      background: transparent; border-radius: 6px; font-size: 11px;
      cursor: pointer; font-family: 'Inter', sans-serif; color: var(--pp-text);
      display: inline-flex; align-items: center; gap: 4px; transition: background .12s;
    }
    .btn-pp-sm:hover { background: #F9FAFB; }

    /* ─── TOAST ─── */
    .pp-toast-wrap {
      position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
      z-index: 2000; width: 90%; max-width: 380px;
      transition: opacity .35s;
    }
    .pp-toast {
      background: #1F2937; color: #fff; padding: 11px 14px;
      border-radius: 9px; font-size: 12px; margin-bottom: 7px;
      display: flex; align-items: center; gap: 9px;
      box-shadow: 0 4px 12px rgba(0,0,0,.25);
    }

    /* ─── SIDEBAR OVERLAY (mobile) ─── */
    .sb-overlay {
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,.45); z-index: 1040;
    }
    .sb-overlay.on { display: block; }

    /* ─── BACKWARD-COMPAT (existing child templates) ─── */
    .pp-section-label { font-size: 11px; font-weight: 700; color: var(--pp-muted); letter-spacing: .06em; text-transform: uppercase; margin: 14px 0 6px; }
    .stat-row { display: grid; grid-template-columns: repeat(2,1fr); gap: 8px; margin-bottom: 12px; }
    .stat-pill { background: #F9FAFB; border-radius: 10px; padding: 12px; text-align: center; border: 1px solid var(--pp-border); }
    .stat-pill .val { font-size: 22px; font-weight: 800; line-height: 1; }
    .stat-pill .lbl { font-size: 11px; color: var(--pp-muted); margin-top: 2px; }
    .stat-pill.green .val { color: var(--pp-secondary); }
    .stat-pill.blue  .val { color: var(--pp-accent); }
    .stat-pill.red   .val { color: var(--pp-danger); }
    .stat-pill.amber .val { color: var(--pp-warning); }
    .feed-item { display: flex; gap: 10px; padding: 10px 0; border-bottom: 0.5px solid var(--pp-border); }
    .feed-item:last-child { border-bottom: none; }
    .feed-icon { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 16px; }
    .feed-content .feed-title { font-weight: 600; font-size: 13px; }
    .feed-content .feed-body  { color: var(--pp-muted); font-size: 12px; }
    .feed-content .feed-time  { font-size: 11px; color: var(--pp-muted); margin-top: 2px; }
    .pp-list-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 0.5px solid var(--pp-border); gap: 8px; }
    .pp-list-item:last-child { border-bottom: none; }
    .pp-list-item .item-main { flex: 1; min-width: 0; }
    .pp-list-item .item-title { font-weight: 600; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .pp-list-item .item-sub   { font-size: 12px; color: var(--pp-muted); }
    .pp-badge { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 600; }
    .pp-badge.green { background: #D1FAE5; color: #065F46; }
    .pp-badge.red   { background: #FEE2E2; color: #991B1B; }
    .pp-badge.amber { background: #FEF3C7; color: #92400E; }
    .pp-badge.blue  { background: #DBEAFE; color: #1E3A8A; }
    .pp-badge.grey  { background: #F3F4F6; color: #374151; }
    .pp-badge.navy  { background: #E8EEF6; color: #1B3A6B; }
    .pp-progress      { height: 8px; border-radius: 4px; background: var(--pp-border); overflow: hidden; }
    .pp-progress-bar  { height: 100%; border-radius: 4px; transition: width .4s; }
    .att-calendar { display: grid; grid-template-columns: repeat(7,1fr); gap: 3px; }
    .att-day-header { text-align: center; font-size: 10px; font-weight: 700; color: var(--pp-muted); padding: 4px 0; }
    .att-day { aspect-ratio: 1; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 500; }
    .att-day.present { background: #D1FAE5; color: #065F46; }
    .att-day.absent  { background: #FEE2E2; color: #991B1B; }
    .att-day.late    { background: #FEF3C7; color: #92400E; }
    .att-day.empty   { background: transparent; }
    .att-day.today   { border: 2px solid var(--pp-primary); }
    @media (min-width: 640px) { .stat-row { grid-template-columns: repeat(4,1fr); } }

    /* ─── MOBILE ─── */
    @media (max-width: 767px) {
      .pp-hdr .hbg-btn { display: flex; align-items: center; }
      .pp-sidebar { transform: translateX(-100%); }
      .pp-sidebar.open { transform: translateX(0); }
      .pp-main { margin-left: 0; padding: 12px; }
      .mc-grid.c4 { grid-template-columns: repeat(2,1fr); }
      .mc-grid.c3 { grid-template-columns: repeat(2,1fr); }
    }

    {% block extra_css %}{% endblock %}
  </style>
</head>
<body>

<!-- ═══ HEADER ═══ -->
<header class="pp-hdr">
  <button class="hbg-btn" id="hbgBtn" onclick="toggleSidebar()" aria-label="Open menu">
    <i class="bi bi-list"></i>
  </button>

  <a href="{% url 'parent:dashboard' %}" class="school-name">
    {% if request.tenant %}{{ request.tenant.name }}{% else %}ASMS{% endif %}
  </a>

  <div class="chip-row">
    {% for s in students %}
    <a href="{% url 'parent:child_academic' student_pk=s.pk %}"
       class="child-chip {% if student and student.pk == s.pk %}on{% endif %}">
      <div class="ch-av">{{ s.first_name|first }}{{ s.last_name|first }}</div>
      {{ s.first_name }}
    </a>
    {% endfor %}
  </div>

  <div class="hdr-right">
    <a href="{% url 'parent:notifications' %}" class="notif-btn" aria-label="Alerts">
      <i class="bi bi-bell-fill"></i>
      {% if unread_count %}<span class="notif-badge" id="notifBadge">{{ unread_count }}</span>
      {% else %}<span class="notif-badge d-none" id="notifBadge"></span>{% endif %}
    </a>
    <a href="{% url 'parent:profile' %}" class="user-av">
      {{ request.user.first_name|first|upper }}{{ request.user.last_name|first|upper }}
    </a>
  </div>
</header>

<!-- Mobile overlay -->
<div class="sb-overlay" id="sbOverlay" onclick="toggleSidebar()"></div>

<div class="pp-layout">

  <!-- ═══ SIDEBAR ═══ -->
  {% with u=request.resolver_match.url_name %}
  <nav class="pp-sidebar" id="sidebar" aria-label="Portal navigation">

    <div class="sb-child-info">
      {% if student %}
      <p class="sb-child-name">{{ student.first_name }} {{ student.last_name }}</p>
      <p class="sb-child-class">{{ student.current_class|default:'' }}</p>
      {% else %}
      <p class="sb-child-name" style="color:var(--pp-sblabel)">Select a child above</p>
      <p class="sb-child-class">↑ tap a name in the header</p>
      {% endif %}
    </div>

    <div class="ng">Overview</div>
    <a href="{% url 'parent:dashboard' %}"
       class="nv {% if active_section == 'dash' or u == 'dashboard' %}on{% endif %}">
      <i class="bi bi-house-fill"></i> Dashboard
    </a>
    <a href="{% url 'parent:notifications' %}"
       class="nv {% if active_section == 'ntc' or u == 'notifications' %}on{% endif %}">
      <i class="bi bi-megaphone-fill"></i> Notices & Alerts
    </a>

    {% if student %}
    <div class="ng">Child's Life</div>
    <a href="{% url 'parent:child_attendance' student_pk=student.pk %}"
       class="nv {% if active_section == 'att' or u == 'child_attendance' %}on{% endif %}">
      <i class="bi bi-calendar-check"></i> Attendance
    </a>
    <a href="{% url 'parent:child_academic' student_pk=student.pk %}"
       class="nv {% if active_section == 'acad' or u == 'child_academic' %}on{% endif %}">
      <i class="bi bi-bar-chart-fill"></i> Academic
    </a>
    <a href="{% url 'parent:child_timetable' student_pk=student.pk %}"
       class="nv {% if active_section == 'tt' or u == 'child_timetable' %}on{% endif %}">
      <i class="bi bi-clock"></i> Timetable
    </a>
    <a href="{% url 'parent:child_library' student_pk=student.pk %}"
       class="nv {% if active_section == 'lib' or u == 'child_library' %}on{% endif %}">
      <i class="bi bi-book"></i> Library
    </a>
    <a href="{% url 'parent:child_behaviour' student_pk=student.pk %}"
       class="nv {% if active_section == 'behv' or u == 'child_behaviour' %}on{% endif %}">
      <i class="bi bi-shield-fill"></i> Behaviour
    </a>

    <div class="ng">Finance & Docs</div>
    <a href="{% url 'parent:child_fees' student_pk=student.pk %}"
       class="nv {% if active_section == 'fees' or u == 'child_fees' %}on{% endif %}">
      <i class="bi bi-credit-card-fill"></i> Fees & Payments
    </a>
    <a href="{% url 'parent:child_documents' student_pk=student.pk %}"
       class="nv {% if active_section == 'docs' or u == 'child_documents' %}on{% endif %}">
      <i class="bi bi-file-earmark-pdf"></i> Documents
    </a>
    {% endif %}

    <div class="ng">Communication</div>
    <a href="{% url 'parent:parent_messages' %}"
       class="nv {% if active_section == 'msg' or u == 'parent_messages' %}on{% endif %}">
      <i class="bi bi-chat-dots-fill"></i> Messages
    </a>
    <a href="{% url 'parent:profile' %}"
       class="nv {% if active_section == 'prf' or u == 'profile' %}on{% endif %}">
      <i class="bi bi-person-fill"></i> Profile
    </a>
  </nav>
  {% endwith %}

  <!-- ═══ MAIN ═══ -->
  <main class="pp-main" role="main">
    <div class="pp-inner">

      {% if messages %}
      <div class="pp-toast-wrap" id="toastContainer">
        {% for msg in messages %}
        <div class="pp-toast">
          {% if 'error' in msg.tags %}<i class="bi bi-exclamation-circle-fill text-danger"></i>
          {% elif 'success' in msg.tags %}<i class="bi bi-check-circle-fill" style="color:#0A7B8C"></i>
          {% else %}<i class="bi bi-info-circle-fill" style="color:#185FA5"></i>{% endif %}
          {{ msg }}
        </div>
        {% endfor %}
      </div>
      {% endif %}

      {% block content %}{% endblock %}
    </div>
  </main>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
  function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('sbOverlay').classList.toggle('on');
  }
  setTimeout(() => {
    const c = document.getElementById('toastContainer');
    if (c) { c.style.opacity = '0'; setTimeout(() => c && (c.style.display = 'none'), 400); }
  }, 3500);
  {% if request.user.is_authenticated %}
  setInterval(() => {
    fetch('{% url "parent:notification_count" %}')
      .then(r => r.json())
      .then(d => {
        const b = document.getElementById('notifBadge');
        if (b) { b.textContent = d.unread || ''; b.classList.toggle('d-none', !d.unread); }
      }).catch(() => {});
  }, 60000);
  {% endif %}
</script>
{% block extra_js %}{% endblock %}
</body>
</html>
"""

# ════════════════════════════════════════════════════════════════════════
# 2.  templates/parent/library.html
# ════════════════════════════════════════════════════════════════════════
LIBRARY_HTML = """{% extends 'parent/base.html' %}
{% block title %}Library – {{ student.first_name }} | ASMS{% endblock %}

{% block content %}
<p class="pp-sec-title"><i class="bi bi-book me-2"></i>Library — {{ student.get_full_name }}</p>

<div class="mc-grid c3">
  <div class="mc">
    <p class="ml">Books borrowed</p>
    <p class="mv">{{ current_loans|length }}</p>
  </div>
  <div class="mc">
    <p class="ml">Books overdue</p>
    <p class="mv {% if overdue_count %}danger{% endif %}">{{ overdue_count }}</p>
    {% if overdue_count %}<p class="ms danger">⚠ action needed</p>{% endif %}
  </div>
  <div class="mc">
    <p class="ml">Outstanding fine</p>
    <p class="mv {% if total_fine %}danger{% endif %}">
      {% if total_fine %}UGX {{ total_fine|floatformat:0 }}{% else %}None{% endif %}
    </p>
  </div>
</div>

<div class="pp-card">
  <h6><i class="bi bi-journals me-2"></i>Currently borrowed</h6>
  {% if current_loans %}
  <table class="pp-table">
    <thead>
      <tr><th>Title</th><th>Borrowed</th><th>Due date</th><th style="text-align:right">Status</th></tr>
    </thead>
    <tbody>
      {% for loan in current_loans %}
      <tr>
        <td>
          <p style="font-weight:600;margin:0">{{ loan.book.title }}</p>
          <p style="font-size:11px;color:var(--pp-muted);margin:1px 0 0">{{ loan.book.barcode|default:'' }}</p>
        </td>
        <td>{{ loan.borrowed_at|date:"j M" }}</td>
        <td>
          {% if loan.is_overdue %}
          <span style="color:var(--pp-danger);font-weight:600">{{ loan.due_date|date:"j M" }}</span>
          <br><span style="font-size:10px;color:var(--pp-danger)">{{ loan.days_overdue }} days overdue</span>
          {% else %}
          <span style="color:#059669;font-weight:600">{{ loan.due_date|date:"j M" }}</span>
          <br><span style="font-size:10px;color:var(--pp-muted)">{{ loan.days_remaining }} days left</span>
          {% endif %}
        </td>
        <td style="text-align:right">
          {% if loan.is_overdue %}
            <span class="bd red">Overdue</span>
            {% if loan.fine_amount %}<p style="font-size:11px;color:var(--pp-danger);margin:3px 0 0;font-weight:600">UGX {{ loan.fine_amount|floatformat:0 }} fine</p>{% endif %}
          {% else %}
            <span class="bd green">On time</span>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p style="color:var(--pp-muted);margin:0"><i class="bi bi-check-circle me-1" style="color:#059669"></i>No books currently borrowed.</p>
  {% endif %}
</div>

<div class="pp-card">
  <h6><i class="bi bi-clock-history me-2"></i>Reading history</h6>
  {% if past_loans %}
  <table class="pp-table">
    <thead><tr><th>Title</th><th>Returned</th><th style="text-align:right">Fine paid</th></tr></thead>
    <tbody>
      {% for loan in past_loans %}
      <tr>
        <td>{{ loan.book.title }}</td>
        <td>{{ loan.returned_at|date:"j M Y" }}</td>
        <td style="text-align:right">
          {% if loan.fine_paid %}<span style="color:var(--pp-danger);font-weight:600;font-size:11px">UGX {{ loan.fine_paid|floatformat:0 }}</span>
          {% else %}<span class="bd green">None</span>{% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p style="color:var(--pp-muted);margin:0">No borrowing history yet.</p>
  {% endif %}
  {% if total_fine %}
  <div style="margin-top:10px;padding-top:10px;border-top:0.5px solid var(--pp-border)">
    <p style="font-size:12px;color:var(--pp-muted);margin:0">
      <i class="bi bi-info-circle me-1"></i>
      To pay the outstanding fine of <strong>UGX {{ total_fine|floatformat:0 }}</strong>, visit the library desk or contact the school bursar.
    </p>
  </div>
  {% endif %}
</div>
{% endblock %}
"""

# ════════════════════════════════════════════════════════════════════════
# 3.  templates/parent/timetable.html
# ════════════════════════════════════════════════════════════════════════
TIMETABLE_HTML = """{% extends 'parent/base.html' %}
{% block title %}Timetable – {{ student.first_name }} | ASMS{% endblock %}

{% block content %}
<p class="pp-sec-title"><i class="bi bi-clock me-2"></i>Weekly Timetable — {{ student.first_name }}{% if student.current_class %}, {{ student.current_class }}{% endif %}</p>

{% if timetable_notice %}
<div class="pp-alert amber">
  <i class="bi bi-exclamation-triangle-fill flex-shrink-0"></i>
  <span>{{ timetable_notice }}</span>
</div>
{% endif %}

{% if timetable_grid %}
<div class="pp-card" style="overflow-x:auto">
  <table class="pp-table" style="min-width:480px">
    <thead>
      <tr>
        <th style="width:85px">Period</th>
        {% for day in days %}<th>{{ day }}</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for row in timetable_grid %}
      <tr>
        <td style="font-size:10px;color:var(--pp-muted);white-space:nowrap">{{ row.period }}</td>
        {% for cell in row.cells %}
        <td>
          {% if cell.is_break %}
          <div style="text-align:center;color:var(--pp-muted);font-size:11px">{{ cell.label }}</div>
          {% elif cell.subject %}
          <div class="tt-cell" style="background:{{ cell.bg }};color:{{ cell.fg }}">{{ cell.subject }}</div>
          {% else %}
          <div style="color:var(--pp-border);text-align:center">—</div>
          {% endif %}
        </td>
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<div class="pp-card" style="text-align:center;padding:32px 16px">
  <i class="bi bi-calendar-x" style="font-size:36px;color:var(--pp-border);display:block;margin-bottom:10px"></i>
  <p style="color:var(--pp-muted);margin:0">
    Timetable not yet configured{% if student.current_class %} for {{ student.current_class }}{% endif %}.<br>
    Contact the school to request a copy.
  </p>
</div>
{% endif %}
{% endblock %}
"""

# ════════════════════════════════════════════════════════════════════════
# 4.  templates/parent/documents.html
# ════════════════════════════════════════════════════════════════════════
DOCUMENTS_HTML = """{% extends 'parent/base.html' %}
{% block title %}Documents – {{ student.first_name }} | ASMS{% endblock %}

{% block content %}
<p class="pp-sec-title"><i class="bi bi-file-earmark-pdf me-2"></i>Documents — {{ student.get_full_name }}</p>
<p class="pp-sec-sub">All documents are permanently archived and available at any time.</p>

<div class="pp-card">
  {% if documents %}
  <table class="pp-table">
    <thead>
      <tr>
        <th>Document</th>
        <th>Date issued</th>
        <th>Type</th>
        <th style="text-align:right">Download</th>
      </tr>
    </thead>
    <tbody>
      {% for doc in documents %}
      <tr>
        <td style="font-weight:600">{{ doc.title }}</td>
        <td>{{ doc.date_issued|date:"j M Y" }}</td>
        <td>
          {% if doc.doc_type == 'report_card' %}<span class="bd blue">Report Card</span>
          {% elif doc.doc_type == 'invoice' %}<span class="bd amber">Invoice</span>
          {% elif doc.doc_type == 'receipt'  %}<span class="bd green">Receipt</span>
          {% else %}<span class="bd grey">{{ doc.doc_type|capfirst }}</span>
          {% endif %}
        </td>
        <td style="text-align:right">
          {% if doc.file_url %}
          <a href="{{ doc.file_url }}" target="_blank" class="btn-pp-sm">
            <i class="bi bi-download"></i> PDF
          </a>
          {% else %}
          <span style="color:var(--pp-muted);font-size:11px">Pending</span>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div style="text-align:center;padding:28px 16px">
    <i class="bi bi-folder-x" style="font-size:36px;color:var(--pp-border);display:block;margin-bottom:10px"></i>
    <p style="color:var(--pp-muted);margin:0;font-size:12px">
      No documents have been uploaded yet.<br>
      Report cards and receipts will appear here when issued by the school.
    </p>
  </div>
  {% endif %}
</div>
{% endblock %}
"""

# ════════════════════════════════════════════════════════════════════════
# 5.  templates/parent/messages.html
# ════════════════════════════════════════════════════════════════════════
MESSAGES_HTML = """{% extends 'parent/base.html' %}
{% block title %}Messages | ASMS{% endblock %}

{% block content %}
<p class="pp-sec-title"><i class="bi bi-chat-dots-fill me-2"></i>Messages & Meetings</p>

<div class="row g-3">

  <!-- ── Inbox ── -->
  <div class="col-12 col-md-5">
    <div class="pp-card">
      <h6><i class="bi bi-inbox me-1"></i>Inbox</h6>
      {% if inbox %}
        {% for msg in inbox %}
        <div class="msg-item">
          <div class="msg-av" style="background:#DBEAFE;color:#1E3A8A">
            {{ msg.sender.first_name|first }}{{ msg.sender.last_name|first }}
          </div>
          <div style="flex:1;min-width:0">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:6px">
              <p style="font-size:12px;font-weight:600;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ msg.sender.get_full_name }}</p>
              <span style="font-size:10px;color:var(--pp-muted);flex-shrink:0">{{ msg.sent_at|date:"j M" }}</span>
            </div>
            {% if msg.subject %}<p style="font-size:11px;font-weight:600;color:var(--pp-text);margin:1px 0 0">{{ msg.subject }}</p>{% endif %}
            <p style="font-size:12px;color:var(--pp-muted);margin:2px 0 0">{{ msg.body|truncatechars:80 }}</p>
          </div>
          {% if not msg.read_at %}<span class="unread-dot"></span>{% endif %}
        </div>
        {% endfor %}
      {% else %}
      <p style="color:var(--pp-muted);margin:0;font-size:12px">No messages yet. Teachers will contact you here about your child's progress.</p>
      {% endif %}
    </div>
  </div>

  <!-- ── Right column ── -->
  <div class="col-12 col-md-7">

    <!-- Send message -->
    <div class="pp-card mb-3">
      <h6><i class="bi bi-send me-1"></i>Send message to teacher</h6>
      <form method="post" action="{% url 'parent:message_send' %}">
        {% csrf_token %}
        {% if student %}
        <input type="hidden" name="student_pk" value="{{ student.pk }}">
        {% else %}
        <div class="pp-field">
          <label class="pp-label">Child</label>
          <select name="student_pk" class="pp-select" required>
            {% for s in students %}<option value="{{ s.pk }}">{{ s.get_full_name }}</option>{% endfor %}
          </select>
        </div>
        {% endif %}
        <div class="pp-field">
          <label class="pp-label">Teacher / recipient</label>
          <select name="recipient_id" class="pp-select" required>
            <option value="">— Select —</option>
            {% for t in teachers %}<option value="{{ t.pk }}">{{ t.get_full_name }}{% if t.profile.subject_taught %} — {{ t.profile.subject_taught }}{% endif %}</option>{% endfor %}
          </select>
        </div>
        <div class="pp-field">
          <label class="pp-label">Subject</label>
          <input type="text" name="subject" class="pp-input" placeholder="e.g. Query about mid-term results" required>
        </div>
        <div class="pp-field">
          <label class="pp-label">Message</label>
          <textarea name="body" class="pp-input pp-textarea" rows="3" placeholder="Type your message here..." required></textarea>
        </div>
        <button type="submit" class="btn-pp" style="width:100%">
          <i class="bi bi-send me-1"></i> Send Message
        </button>
      </form>
    </div>

    <!-- Book meeting -->
    <div class="pp-card">
      <h6><i class="bi bi-calendar-event me-1"></i>Request a parent–teacher meeting</h6>
      <form method="post" action="{% url 'parent:meeting_request' %}">
        {% csrf_token %}
        {% if student %}<input type="hidden" name="student_pk" value="{{ student.pk }}">{% endif %}
        <div class="pp-field">
          <label class="pp-label">Teacher</label>
          <select name="teacher_id" class="pp-select" required>
            <option value="">— Select —</option>
            {% for t in teachers %}<option value="{{ t.pk }}">{{ t.get_full_name }}</option>{% endfor %}
          </select>
        </div>
        <div class="row g-2 mb-3">
          <div class="col-6">
            <label class="pp-label">Preferred date</label>
            <input type="date" name="pref_date" class="pp-input" required>
          </div>
          <div class="col-6">
            <label class="pp-label">Time slot</label>
            <select name="pref_time" class="pp-select" required>
              <option>8:00 AM</option><option>10:00 AM</option>
              <option>2:00 PM</option><option>3:00 PM</option><option>4:00 PM</option>
            </select>
          </div>
        </div>
        <button type="submit" class="btn-pp" style="width:100%">
          <i class="bi bi-calendar-check me-1"></i> Request Meeting
        </button>
      </form>
    </div>

  </div>
</div>
{% endblock %}
"""

# ════════════════════════════════════════════════════════════════════════
# 6.  apps/parent_portal/models.py  – append ParentMessage
# ════════════════════════════════════════════════════════════════════════
MODELS_BLOCK = f"""{GUARD}
import uuid as _uuid
from django.conf import settings as _settings
from django.db import models as _models


class ParentMessage(_models.Model):
    \"\"\"Direct messages between parents and school staff (Phase 2).\"\"\"
    id        = _models.UUIDField(primary_key=True, default=_uuid.uuid4, editable=False)
    sender    = _models.ForeignKey(
        _settings.AUTH_USER_MODEL, on_delete=_models.CASCADE,
        related_name='sent_parent_messages'
    )
    recipient = _models.ForeignKey(
        _settings.AUTH_USER_MODEL, on_delete=_models.CASCADE,
        related_name='received_parent_messages'
    )
    student   = _models.ForeignKey(
        'admissions.Student', on_delete=_models.CASCADE,
        null=True, blank=True, related_name='parent_messages'
    )
    subject   = _models.CharField(max_length=200, blank=True)
    body      = _models.TextField()
    sent_at   = _models.DateTimeField(auto_now_add=True)
    read_at   = _models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'parent_portal'
        ordering  = ['-sent_at']

    def __str__(self):
        return f'{{self.sender}} → {{self.recipient}}: {{self.subject[:40]}}'
"""

# ════════════════════════════════════════════════════════════════════════
# 7.  apps/parent_portal/views.py  – append 6 new views
# ════════════════════════════════════════════════════════════════════════
VIEWS_BLOCK = f"""{GUARD}
# library · timetable · documents · messages · meeting_request

from django.contrib import messages as _msgs
from django.utils import timezone as _tz


def _get_unread_count_safe(request):
    try:
        from apps.communications.models import Notification
        return Notification.objects.filter(
            recipient=request.user, read_at__isnull=True
        ).count()
    except Exception:
        return 0


def _get_staff_contacts():
    try:
        from apps.accounts.models import User
        return list(
            User.objects.filter(
                role__in=['teacher', 'class_teacher', 'principal', 'counsellor'],
                is_active=True
            ).order_by('first_name')
        )
    except Exception:
        return []


@login_required
def child_library(request, student_pk):
    students = _get_parent_students(request)
    student  = next((s for s in students if s.pk == student_pk), None)
    if student is None:
        return redirect('parent:dashboard')

    current_loans, past_loans = [], []
    overdue_count, total_fine = 0, 0
    try:
        from apps.library.models import BorrowRecord
        today = _tz.now().date()
        current_loans = list(
            BorrowRecord.objects.filter(
                student=student, returned_at__isnull=True
            ).select_related('book').order_by('due_date')
        )
        for loan in current_loans:
            due = getattr(loan, 'due_date', None)
            if due and due < today:
                loan.is_overdue    = True
                loan.days_overdue  = (today - due).days
                loan.fine_amount   = getattr(loan, 'fine_amount', loan.days_overdue * 200)
                overdue_count += 1
                total_fine    += loan.fine_amount
            else:
                loan.is_overdue    = False
                loan.days_remaining = (due - today).days if due else 0
        past_loans = list(
            BorrowRecord.objects.filter(
                student=student, returned_at__isnull=False
            ).select_related('book').order_by('-returned_at')[:10]
        )
    except Exception:
        pass

    return render(request, 'parent/library.html', {{
        'student': student, 'students': students,
        'current_loans': current_loans, 'past_loans': past_loans,
        'overdue_count': overdue_count, 'total_fine': total_fine,
        'active_section': 'lib',
        'unread_count': _get_unread_count_safe(request),
    }})


@login_required
def child_timetable(request, student_pk):
    students = _get_parent_students(request)
    student  = next((s for s in students if s.pk == student_pk), None)
    if student is None:
        return redirect('parent:dashboard')

    DAYS    = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    PALETTE = [
        ('#E6F1FB','#0C447C'), ('#EAF3DE','#27500A'), ('#FAEEDA','#633806'),
        ('#EEEDFE','#3C3489'), ('#E1F5EE','#085041'), ('#F1EFE8','#444441'),
        ('#FAECE7','#712B13'), ('#FEF3C7','#92400E'),
    ]
    timetable_grid, timetable_notice = [], None

    try:
        from apps.academics.models import TimetableEntry
        entries = list(
            TimetableEntry.objects.filter(
                class_room=student.current_class
            ).select_related('subject', 'teacher').order_by('day_of_week', 'start_time')
        )
        color_map, ci = {{}}, 0
        periods = sorted(set((e.start_time, e.end_time) for e in entries))
        for st, et in periods:
            label = f'{{st.strftime("%I:%M").lstrip("0")}}–{{et.strftime("%I:%M %p").lstrip("0")}}'
            row   = {{'period': label, 'cells': []}}
            for day_n in range(1, 6):
                hit = next((e for e in entries if e.day_of_week == day_n and e.start_time == st), None)
                if hit:
                    name = hit.subject.name if hasattr(hit.subject, 'name') else str(hit.subject)
                    if name not in color_map:
                        color_map[name] = PALETTE[ci % len(PALETTE)]; ci += 1
                    bg, fg = color_map[name]
                    row['cells'].append({{'subject': name, 'bg': bg, 'fg': fg, 'is_break': False}})
                else:
                    row['cells'].append({{'subject': None, 'is_break': False}})
            timetable_grid.append(row)
    except Exception:
        timetable_notice = 'Timetable not yet configured for this class.'

    return render(request, 'parent/timetable.html', {{
        'student': student, 'students': students,
        'timetable_grid': timetable_grid, 'days': DAYS,
        'timetable_notice': timetable_notice,
        'active_section': 'tt',
        'unread_count': _get_unread_count_safe(request),
    }})


@login_required
def child_documents(request, student_pk):
    students = _get_parent_students(request)
    student  = next((s for s in students if s.pk == student_pk), None)
    if student is None:
        return redirect('parent:dashboard')

    documents = []
    try:
        from apps.exams.models import ReportCard
        for rc in ReportCard.objects.filter(student=student).order_by('-created_at'):
            f = getattr(rc, 'pdf_file', None)
            documents.append({{
                'title':      f'Report Card — {{rc.term}}',
                'date_issued': rc.created_at.date() if hasattr(rc.created_at, 'date') else rc.created_at,
                'doc_type':   'report_card',
                'file_url':   f.url if f else None,
            }})
    except Exception:
        pass
    try:
        from apps.fees.models import Invoice
        for inv in Invoice.objects.filter(student=student).order_by('-created_at')[:15]:
            documents.append({{
                'title':      f'Fee Invoice #{{inv.invoice_number}}',
                'date_issued': inv.created_at.date() if hasattr(inv.created_at, 'date') else inv.created_at,
                'doc_type':   'invoice',
                'file_url':   None,
            }})
    except Exception:
        pass
    documents.sort(key=lambda d: d['date_issued'] or '', reverse=True)

    return render(request, 'parent/documents.html', {{
        'student': student, 'students': students,
        'documents': documents,
        'active_section': 'docs',
        'unread_count': _get_unread_count_safe(request),
    }})


@login_required
def parent_messages(request):
    students = _get_parent_students(request)
    student  = students[0] if students else None
    inbox    = []
    try:
        from apps.parent_portal.models import ParentMessage
        inbox = list(
            ParentMessage.objects.filter(recipient=request.user)
            .select_related('sender', 'student').order_by('-sent_at')[:25]
        )
        ParentMessage.objects.filter(
            recipient=request.user, read_at__isnull=True
        ).update(read_at=_tz.now())
    except Exception:
        pass

    return render(request, 'parent/messages.html', {{
        'student': student, 'students': students,
        'inbox': inbox, 'teachers': _get_staff_contacts(),
        'active_section': 'msg',
        'unread_count': _get_unread_count_safe(request),
    }})


@login_required
def message_send(request):
    if request.method != 'POST':
        return redirect('parent:parent_messages')
    try:
        from apps.parent_portal.models import ParentMessage
        from apps.accounts.models import User
        from apps.admissions.models import Student as _Student
        recipient = User.objects.get(pk=request.POST['recipient_id'])
        student   = _Student.objects.get(pk=request.POST['student_pk'])
        ParentMessage.objects.create(
            sender=request.user, recipient=recipient, student=student,
            subject=request.POST.get('subject', ''),
            body=request.POST.get('body', ''),
        )
        _msgs.success(request, 'Message sent successfully.')
    except Exception as e:
        _msgs.error(request, f'Could not send message: {{e}}')
    return redirect('parent:parent_messages')


@login_required
def meeting_request(request):
    if request.method != 'POST':
        return redirect('parent:parent_messages')
    try:
        from apps.parent_portal.models import ParentMessage
        from apps.accounts.models import User
        teacher    = User.objects.get(pk=request.POST['teacher_id'])
        pref_date  = request.POST.get('pref_date', '')
        pref_time  = request.POST.get('pref_time', '')
        student_pk = request.POST.get('student_pk')
        student    = None
        if student_pk:
            from apps.admissions.models import Student as _Student
            student = _Student.objects.filter(pk=student_pk).first()
        body = (
            f'Dear {{teacher.first_name}},\\n\\n'
            f'I would like to request a parent–teacher meeting on {{pref_date}} at {{pref_time}}. '
            f'Please confirm if this time is suitable.\\n\\n'
            f'Regards,\\n{{request.user.get_full_name()}}'
        )
        ParentMessage.objects.create(
            sender=request.user, recipient=teacher, student=student,
            subject=f'Meeting request — {{pref_date}} at {{pref_time}}',
            body=body,
        )
        _msgs.success(request, f'Meeting request sent to {{teacher.get_full_name()}}.')
    except Exception as e:
        _msgs.error(request, f'Could not send meeting request: {{e}}')
    return redirect('parent:parent_messages')
"""

# ════════════════════════════════════════════════════════════════════════
# EXECUTE
# ════════════════════════════════════════════════════════════════════════
print('\n🔷 Phase 2 Parent Portal Upgrade\n')

print('① Writing templates...')
write('templates/parent/base.html',      BASE_HTML)
write('templates/parent/library.html',   LIBRARY_HTML)
write('templates/parent/timetable.html', TIMETABLE_HTML)
write('templates/parent/documents.html', DOCUMENTS_HTML)
write('templates/parent/messages.html',  MESSAGES_HTML)

print('\n② Patching models.py...')
safe_append('apps/parent_portal/models.py', MODELS_BLOCK)

print('\n③ Appending views.py...')
safe_append('apps/parent_portal/views.py', VIEWS_BLOCK)

print('\n④ Patching urls.py...')
patch_urls('apps/parent_portal/urls.py')

print("""
✅  Done!  Next steps:
    python manage.py makemigrations parent_portal
    python manage.py migrate
    python manage.py runserver

    Then hard-refresh the parent portal (Ctrl+Shift+R).
""")