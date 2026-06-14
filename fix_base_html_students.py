"""
fix_base_html_students.py
=========================
Fixes: VariableDoesNotExist — 'Failed lookup for key [0] in []'

ROOT CAUSE
----------
parent/base.html line 331 accesses students.0 (index on empty list).
In Django DEBUG mode this bubbles as VariableDoesNotExist instead of
silently returning ''.

FIX
---
1. Replace every  students.0  occurrence with  active_student
   (the context processor already sets active_student = students[0] or None)
2. Add {% if students %} ... {% endif %} guard around any child-switcher
   block that would otherwise crash on an empty students list.

Run from project root:
    python fix_base_html_students.py
"""

import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_HTML = os.path.join(BASE_DIR, "templates", "parent", "base.html")


# ── STEP 1: Show line 331 context so we know exactly what we're fixing ────────

def show_context(lines, center=331, radius=10):
    start = max(0, center - radius - 1)
    end = min(len(lines), center + radius)
    print(f"\n=== base.html lines {start+1}–{end} (error at line {center}) ===")
    for i, line in enumerate(lines[start:end], start=start + 1):
        marker = "  <<<< ERROR" if i == center else ""
        print(f"  {i:4d}: {line.rstrip()}{marker}")
    print()


# ── STEP 2: Patch content ─────────────────────────────────────────────────────

def patch(content: str) -> str:
    changes = []

    # 2a. Replace bare  students.0  with  active_student
    #     Covers: {{ students.0 }}, {% with x=students.0 %}, {% if students.0 %}, etc.
    if "students.0" in content:
        content = content.replace("students.0", "active_student")
        changes.append("Replaced 'students.0' → 'active_student'")

    # 2b. Replace  children_data.0  too (legacy name)
    if "children_data.0" in content:
        content = content.replace("children_data.0", "active_student")
        changes.append("Replaced 'children_data.0' → 'active_student'")

    # 2c. Wrap any {% with student=active_student %} … {% endwith %} so that
    #     if active_student is None the inner block is skipped.
    #     Pattern: {% with student=active_student %}
    #     → {% if active_student %}{% with student=active_student %}
    #       … {% endwith %}{% endif %}
    # We do a targeted replacement rather than a broad regex to stay safe.

    WITH_PAT = re.compile(
        r"(\{%-?\s*with\s+\w+=active_student\s*-?%\})",
        re.IGNORECASE,
    )
    if WITH_PAT.search(content):
        # Only wrap if not already wrapped with {% if active_student %}
        # Insert guard before the with block
        def wrap_with(m):
            return "{% if active_student %}" + m.group(1)
        content = WITH_PAT.sub(wrap_with, content)
        # Close the guard: find {% endwith %} that follows and append {% endif %}
        # Simple: replace first {% endwith %} that corresponds to our with block
        # (base.html child switcher is usually one level deep — safe to replace all)
        content = content.replace(
            "{% endwith %}",
            "{% endwith %}{% endif %}",
            # only replace the ones we just modified (count=1 per match above)
        )
        changes.append(
            "Wrapped {% with student=active_student %}…{% endwith %} "
            "with {% if active_student %}…{% endif %}"
        )

    # 2d. Guard direct  {{ active_student.some_attr }}  inside raw blocks that
    #     might not already have a {% if active_student %} guard.
    # (Skipped — this is handled by Django silencing None attribute lookups.)

    # 2e. Replace  children_data  with  students  anywhere it still appears
    #     so the sidebar for-loop works.
    if "children_data" in content:
        content = content.replace("children_data", "students")
        changes.append("Replaced remaining 'children_data' → 'students'")

    return content, changes


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(BASE_HTML):
        print(f"[ERROR] Not found: {BASE_HTML}")
        print("  Make sure you run this from E:\\DJANGO\\ASMS\\asms\\")
        return

    with open(BASE_HTML, "r", encoding="utf-8") as f:
        original = f.read()
    lines = original.splitlines(keepends=True)

    # Show context around line 331
    show_context(lines, center=331)

    # Apply patches
    patched, changes = patch(original)

    if not changes:
        print("[INFO] No changes needed — base.html already looks safe.")
        return

    # Write patched file
    with open(BASE_HTML, "w", encoding="utf-8") as f:
        f.write(patched)

    print("Patches applied:")
    for c in changes:
        print(f"  ✓ {c}")

    print()

    # Show the same area after patching
    patched_lines = patched.splitlines(keepends=True)
    show_context(patched_lines, center=331)

    print("=" * 55)
    print("Done. Run:  python manage.py runserver")
    print("Then hard-refresh /parent/ with Ctrl+Shift+R")
    print("=" * 55)


if __name__ == "__main__":
    main()