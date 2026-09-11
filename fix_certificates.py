path = "apps/student_portal/views.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()
assert lines[2241].strip() == "from documents.models import StudentDocument", \
    f"Line 2242 unexpected: {lines[2241]!r}"
assert "order_by('-created_at')" in lines[2249], \
    f"Line 2250 unexpected: {lines[2249]!r}"
new_block = [
    "\n",
    "    student  = request.student\n",
    "\n",
    "    try:\n",
    "        from apps.documents.models import StudentDocument\n",
    "        certs = StudentDocument.objects.filter(\n",
    "            student=student, doc_type=" + "'" + "certificate" + "'" + "\n",
    "        ).order_by(" + "'" + "-created_at" + "'" + ")\n",
    "    except ImportError:\n",
    "        certs = []\n",
]
lines[2240:2250] = new_block
with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("certificates() patched.")
