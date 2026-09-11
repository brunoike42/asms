path = "apps/student_portal/views.py"

with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Target: lines 1339-1344 (1-indexed) -> list indices 1338:1344
old_slice = "".join(lines[1338:1344])

if "from documents.models import StudentDocument" not in old_slice:
    raise SystemExit("Safety check failed: expected import not found at lines 1339-1344. Aborting, no changes made.")

new_lines = [
    "    student = request.student\n",
    "\n",
    "    try:\n",
    "        from apps.documents.models import StudentDocument\n",
    "        docs = StudentDocument.objects.filter(student=student).order_by('-created_at')\n",
    "    except ImportError:\n",
    "        docs = []\n",
    "\n",
]

lines[1338:1344] = new_lines

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Done — lines 1339-1344 replaced with guarded import block.")