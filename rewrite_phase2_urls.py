"""
Rewrites all 6 Phase 2 apps' urls.py files with correct urlpatterns.
Run from project root: python rewrite_phase2_urls.py
"""
import os

ROOT = os.getcwd()
APPS = os.path.join(ROOT, 'apps')

URLS = {}

URLS['academics'] = '''from django.urls import path
from . import views

urlpatterns = [
    path('subjects/',              views.subject_list,        name='subject_list'),
    path('subjects/add/',          views.subject_create,      name='subject_create'),
    path('class-subjects/',        views.class_subject_list,  name='class_subject_list'),
    path('class-subjects/assign/', views.class_subject_assign,name='class_subject_assign'),
    path('timetable/',             views.timetable_view,      name='timetable_view'),
]
'''

URLS['exams'] = '''from django.urls import path
from . import views

urlpatterns = [
    path('',                                views.exam_list,       name='exam_list'),
    path('create/',                         views.exam_create,     name='exam_create'),
    path('<int:exam_id>/marks/',            views.enter_marks,     name='enter_marks'),
    path('<int:exam_id>/publish/',          views.publish_exam,    name='publish_exam'),
    path('<int:exam_id>/results/',          views.exam_results,    name='exam_results'),
    path('reports/<int:term_id>/',          views.report_list,     name='report_list'),
    path('reports/<int:term_id>/compute/',  views.compute_reports, name='compute_reports'),
    path('reports/<int:term_id>/publish/',  views.publish_reports, name='publish_reports'),
    path('reports/student/<int:report_id>/',views.student_report,  name='student_report'),
]
'''

URLS['staff_hr'] = '''from django.urls import path
from . import views

urlpatterns = [
    path('',                          views.staff_list,   name='staff_list'),
    path('add/',                      views.staff_create, name='staff_create'),
    path('<int:pk>/',                 views.staff_detail, name='staff_detail'),
    path('leave/',                    views.leave_list,   name='leave_list'),
    path('leave/apply/',              views.leave_apply,  name='leave_apply'),
    path('leave/<int:pk>/<str:action>/', views.leave_action, name='leave_action'),
    path('cpd/',                      views.cpd_list,     name='cpd_list'),
    path('cpd/add/',                  views.cpd_create,   name='cpd_create'),
]
'''

URLS['library'] = '''from django.urls import path
from . import views

urlpatterns = [
    path('',                       views.book_list,   name='book_list'),
    path('add/',                   views.book_create, name='book_create'),
    path('<int:pk>/',              views.book_detail, name='book_detail'),
    path('borrow/',                views.borrow_book, name='borrow_book'),
    path('return/<int:record_id>/',views.return_book, name='return_book'),
    path('loans/',                 views.borrow_list, name='borrow_list'),
]
'''

URLS['lms'] = '''from django.urls import path
from . import views

urlpatterns = [
    path('',                                    views.lms_dashboard,      name='lms_dashboard'),
    path('resources/',                          views.resource_list,      name='resource_list'),
    path('resources/<int:class_subject_id>/',   views.resource_list,      name='resource_list_cs'),
    path('resources/add/',                      views.resource_create,    name='resource_create'),
    path('lessons/',                            views.lesson_plan_list,   name='lesson_plan_list'),
    path('lessons/add/',                        views.lesson_plan_create, name='lesson_plan_create'),
    path('quizzes/',                            views.quiz_list,          name='quiz_list'),
    path('quizzes/create/',                     views.quiz_create,        name='quiz_create'),
    path('quizzes/<int:quiz_id>/questions/',    views.quiz_add_questions, name='quiz_add_questions'),
    path('quizzes/<int:quiz_id>/publish/',      views.quiz_publish,       name='quiz_publish'),
]
'''

URLS['assignments'] = '''from django.urls import path
from . import views

urlpatterns = [
    path('',                                    views.assignment_list,   name='assignment_list'),
    path('create/',                             views.assignment_create, name='assignment_create'),
    path('<int:pk>/',                           views.assignment_detail, name='assignment_detail'),
    path('<int:pk>/publish/',                   views.publish_assignment,name='publish_assignment'),
    path('submission/<int:submission_id>/grade/',views.grade_submission, name='grade_submission'),
]
'''

print('\n═══ Rewriting Phase 2 urls.py files ═══\n')

for app, content in URLS.items():
    app_dir = os.path.join(APPS, app)
    if not os.path.isdir(app_dir):
        print(f'  ✗ apps/{app}/ not found — skipping')
        continue

    # First show what's currently in the file
    urls_path = os.path.join(app_dir, 'urls.py')
    if os.path.exists(urls_path):
        with open(urls_path, encoding='utf-8') as f:
            current = f.read()
        has_urlpatterns = 'urlpatterns' in current
        print(f'  {"✓" if has_urlpatterns else "✗"} apps/{app}/urls.py — '
              f'{"has urlpatterns" if has_urlpatterns else "MISSING urlpatterns — fixing"}')

    with open(urls_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  ✓ Rewrote apps/{app}/urls.py')

# ── Also verify all views referenced in urls exist in views.py ────────────
import re
print('\n─── Verifying views exist ──────────────────────────────────────\n')
all_ok = True
for app in URLS:
    urls_path  = os.path.join(APPS, app, 'urls.py')
    views_path = os.path.join(APPS, app, 'views.py')
    if not os.path.exists(views_path):
        print(f'  ✗ apps/{app}/views.py missing!')
        all_ok = False
        continue
    with open(urls_path,  encoding='utf-8') as f: u = f.read()
    with open(views_path, encoding='utf-8') as f: v = f.read()
    refs    = set(re.findall(r'views\.(\w+)', u))
    defined = set(re.findall(r'^(?:async )?def (\w+)', v, re.MULTILINE))
    missing = refs - defined
    if missing:
        print(f'  ✗ apps/{app}/views.py missing: {", ".join(sorted(missing))}')
        all_ok = False
    else:
        print(f'  ✓ apps/{app} — all {len(refs)} views present')

print()
if all_ok:
    print('  All views verified ✓')
else:
    print('  Some views are missing — paste output here for next fix.')

print('''
═══════════════════════════════════════════════════════════
  Test these URLs in your browser:
    http://127.0.0.1:8000/academics/subjects/
    http://127.0.0.1:8000/exams/
    http://127.0.0.1:8000/staff_hr/
    http://127.0.0.1:8000/library/
    http://127.0.0.1:8000/lms/
    http://127.0.0.1:8000/assignments/
═══════════════════════════════════════════════════════════
''')