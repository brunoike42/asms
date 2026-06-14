"""
ASMS — Student Portal URL Configuration
Phase 3

Mount in main urls.py as:
    path('portal/', include('student_portal.urls', namespace='student_portal')),
"""
from django.urls import path
from . import views

app_name = 'student_portal'

urlpatterns = [

    # ─── Dashboard ────────────────────────────────────────────────────────────
    path('',                           views.dashboard,              name='dashboard'),

    # ─── Academic: Core (Phase 1 & 2 data) ────────────────────────────────────
    path('classes/',                   views.my_classes,             name='classes'),
    path('timetable/',                 views.timetable,              name='timetable'),
    path('assignments/',               views.assignments,            name='assignments'),
    path('assignments/<int:assignment_id>/', views.assignment_detail, name='assignment_detail'),
    path('quizzes/',                   views.quizzes,                name='quizzes'),
    path('results/',                   views.results,                name='results'),
    path('attendance/',                views.attendance,             name='attendance'),
    path('attendance/excuse/',         views.excuse_absence,         name='excuse_absence'),

    # ─── Academic: NEW (Makerere benchmark) ────────────────────────────────────
    path('transcript/',                views.transcript,             name='transcript'),
    path('calendar/',                  views.academic_calendar,      name='academic_calendar'),
    path('exam-permit/',               views.exam_permit,            name='exam_permit'),
    path('appeals/',                   views.exam_appeals,           name='exam_appeals'),
    path('appeals/new/',               views.exam_appeal_new,        name='exam_appeal_new'),
    path('clearance/',                 views.academic_clearance,     name='academic_clearance'),
    path('enrollment/',                views.term_enrollment,        name='term_enrollment'),
    path('enrollment/courses/',        views.course_registration,    name='course_registration'),
    path('program-change/',            views.program_change,         name='program_change'),
    path('leave-of-absence/',          views.leave_of_absence,       name='leave_of_absence'),

    # ─── Finance & Services ───────────────────────────────────────────────────
    path('fees/',                      views.fee_account,            name='fee_account'),
    path('library/',                   views.library,                name='library'),
    path('meals/',                     views.meal_account,           name='meal_account'),
    path('transport/',                 views.transport,              name='transport'),

    # ─── Student Life ─────────────────────────────────────────────────────────
    path('messages/',                  views.portal_messages,        name='messages'),
    path('messages/<int:message_id>/', views.message_detail,         name='message_detail'),
    path('noticeboard/',               views.noticeboard,            name='noticeboard'),
    path('documents/',                 views.my_documents,           name='documents'),
    path('merits/',                    views.merits,                 name='merits'),

    # ─── Intelligence (Phase 7 stubs) ─────────────────────────────────────────
    path('career/',                    views.career_guidance,        name='career_guidance'),
    path('ai-assistant/',              views.ai_study_assistant,     name='ai_assistant'),

    # ─── Personal ─────────────────────────────────────────────────────────────
    path('certificates/',              views.certificates,           name='certificates'),
    path('profile/',                   views.profile,                name='profile'),

    # ─── AJAX ─────────────────────────────────────────────────────────────────
    path('ajax/notifications/',        views.notifications_feed,       name='notifications_feed'),
    path('ajax/notifications/<int:notif_id>/read/',
                                       views.mark_notification_read,   name='mark_notification_read'),
]
