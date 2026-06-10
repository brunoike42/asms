from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/',         admin.site.urls),
    path('accounts/',      include('apps.accounts.urls',      namespace='accounts')),
    path('students/',      include('apps.students.urls',      namespace='students')),
    path('admissions/',    include('apps.admissions.urls',    namespace='admissions')),
    path('attendance/',    include('apps.attendance.urls',    namespace='attendance')),
    path('finance/',       include('apps.finance.urls',       namespace='finance')),
    path('communication/', include('apps.communication.urls', namespace='communication')),
   path('dashboard/',     include('apps.core.urls',          namespace='core')),
    path('academics/', include('apps.academics.urls')),
    path('exams/', include('apps.exams.urls')),
    path('staff_hr/', include('apps.staff_hr.urls')),
    path('lms/', include('apps.lms.urls')),
    path('assignments/', include('apps.assignments.urls')),
    path('library/', include('apps.library.urls')),

    path('',               lambda r: redirect('core:dashboard'), name='home'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
