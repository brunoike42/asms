from django.urls import path
from . import views

app_name = 'parent'

urlpatterns = [
    # Main dashboard
    path('',                                    views.dashboard,          name='dashboard'),

    # Notifications
    path('notifications/',                      views.notifications,      name='notifications'),
    path('notifications/count/',                views.notification_count, name='notification_count'),

    # Profile
    path('profile/',                            views.profile,            name='profile'),

    # Child-specific pages
    path('child/<int:student_pk>/academic/',    views.child_academic,     name='child_academic'),
    path('child/<int:student_pk>/attendance/',  views.child_attendance,   name='child_attendance'),
    path('child/<int:student_pk>/fees/',        views.child_fees,         name='child_fees'),
    path('child/<int:student_pk>/behaviour/',   views.child_behaviour,    name='child_behaviour'),
    path('child/<int:student_pk>/assignments/', views.child_assignments,  name='child_assignments'),
    path('child/<int:student_pk>/documents/',   views.child_documents,    name='child_documents'),
    path('child/<int:student_pk>/meetings/',    views.child_meetings,     name='child_meetings'),
    path('child/<int:student_pk>/book-meeting/', views.book_meeting,      name='book_meeting'),
    # ── New sections (upgrade) ──────────────────
    path('child/<int:student_pk>/timetable/', views.child_timetable, name='child_timetable'),
    path('child/<int:student_pk>/library/',   views.child_library,   name='child_library'),
    path('messages/',      views.messages_inbox, name='messages'),
    path('messages/send/', views.send_message,   name='send_message'),
    path('child/<int:student_pk>/canteen/',   views.child_canteen,   name='child_canteen'),
    path('child/<int:student_pk>/health/',    views.child_health,    name='child_health'),
    path('child/<int:student_pk>/transport/', views.child_transport, name='child_transport'),
]
