#!/usr/bin/env python3
"""
Final patch — fixes all remaining class_group= / current_class= / day_of_week=
errors in apps/student_portal/views.py.

Run from: E:\\DJANGO\\ASMS\\asms\\
    python patch_views_final.py
"""
from pathlib import Path

TARGET = Path("apps/student_portal/views.py")
text   = TARGET.read_text(encoding="utf-8")
orig   = text
applied = 0

def apply(label, old, new):
    global text, applied
    n = text.count(old)
    if n == 0:
        print(f"  ❌ NOT FOUND  — {label}")
    else:
        text = text.replace(old, new)
        applied += n
        print(f"  ✅ {n}x fixed  — {label}")

# 1. classes(): ClassSubject filter ──────────────────────────────────────────
apply(
    "classes() → ClassSubject  classroom=",
    "    class_subjects = ClassSubject.objects.filter(\n"
    "        class_group=student.current_class()\n"
    "    ).select_related('subject', 'teacher').order_by('subject__name')",

    "    class_subjects = ClassSubject.objects.filter(\n"
    "        classroom=student.current_class()\n"
    "    ).select_related('subject', 'teacher').order_by('subject__name')",
)

# 2. classes(): classmates via enrollments ───────────────────────────────────
apply(
    "classes() → Student classmates  enrollments__classroom=",
    "        'classmates':    Student.objects.filter(\n"
    "            current_class=student.current_class()\n"
    "        ).exclude(id=student.id).order_by('user__last_name')[:50],",

    "        'classmates':    Student.objects.filter(\n"
    "            enrollments__classroom=student.current_class(),\n"
    "            enrollments__is_active=True\n"
    "        ).exclude(id=student.id).distinct().order_by('user__last_name')[:50],",
)

# 3. timetable(): TimetableEntry filter + select_related + order_by ──────────
apply(
    "timetable() → TimetableEntry  class_subject__classroom= + day + select_related",
    "    entries = TimetableEntry.objects.filter(\n"
    "        class_group=student.current_class()\n"
    "    ).select_related('subject', 'teacher').order_by('day_of_week', 'start_time')",

    "    entries = TimetableEntry.objects.filter(\n"
    "        class_subject__classroom=student.current_class()\n"
    "    ).select_related('class_subject__subject', 'class_subject__teacher').order_by('day', 'start_time')",
)

# 4. timetable(): day-grouping loop attribute ─────────────────────────────────
apply(
    "timetable() → entry.day  (was .day_of_week)",
    "        days[entry.day_of_week].append(entry)",
    "        days[entry.day].append(entry)",
)

# 5. assignments(): remove phantom term=, fix class_group= ───────────────────
apply(
    "assignments() → Assignment  class_subject__classroom=  (removed phantom term=)",
    "    base_qs = Assignment.objects.filter(\n"
    "        class_group=student.current_class(), term=term\n"
    "    ).order_by('-due_date')",

    "    base_qs = Assignment.objects.filter(\n"
    "        class_subject__classroom=student.current_class()\n"
    "    ).order_by('-due_date')",
)

# 6. assignment_detail(): get_object_or_404 ──────────────────────────────────
apply(
    "assignment_detail() → get_object_or_404  class_subject__classroom=",
    "    assignment = get_object_or_404(Assignment, id=assignment_id, "
    "class_group=student.current_class())",

    "    assignment = get_object_or_404(Assignment, id=assignment_id, "
    "class_subject__classroom=student.current_class())",
)

# 7. ~line 865: available_subjects ───────────────────────────────────────────
apply(
    "~line 865 → available_subjects  ClassSubject.classroom=",
    "    available_subjects = ClassSubject.objects.filter(\n"
    "        class_group=student.current_class()\n"
    "    ).select_related('subject').order_by('subject__name')",

    "    available_subjects = ClassSubject.objects.filter(\n"
    "        classroom=student.current_class()\n"
    "    ).select_related('subject').order_by('subject__name')",
)

# ── save + straggler scan ────────────────────────────────────────────────────
print(f"\n{'─'*58}")
if text != orig:
    TARGET.write_text(text, encoding="utf-8")
    print(f"✅  {applied} replacement(s) applied — views.py saved.\n")
    stragglers = [
        (i + 1, ln)
        for i, ln in enumerate(text.splitlines())
        if (
            "class_group="    in ln or
            "day_of_week"     in ln or
            ("current_class=" in ln and "'current_class'" not in ln and "#" not in ln)
        )
    ]
    if stragglers:
        print("⚠️  Possible remaining issues — check manually:")
        for lineno, ln in stragglers:
            print(f"  line {lineno:4d}:  {ln.strip()}")
    else:
        print("🎉  Zero class_group= / day_of_week / stray current_class= lines remain.")
else:
    print("⚠️  Nothing changed — no patterns matched.")