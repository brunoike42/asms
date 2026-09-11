"""
Patch script: fix {% extends "base.html" %} -> {% extends "base/base.html" %}
in all EMIS templates.

Run from your project root (E:\DJANGO\ASMS\asms):
    python patch_emis_base.py

Safe to re-run: if a file has already been patched, it is skipped with a
clear message rather than double-patching or erroring.
"""

import sys
from pathlib import Path

OLD = '{% extends "base.html" %}'
NEW = '{% extends "base/base.html" %}'

FILES = [
    Path("templates/emis/compliance_result.html"),
    Path("templates/emis/dashboard.html"),
    Path("templates/emis/infrastructure_form.html"),
    Path("templates/emis/submission_detail.html"),
    Path("templates/emis/submission_list.html"),
]


def patch_file(path: Path) -> str:
    if not path.exists():
        return f"[SKIP] {path} — file not found"

    text = path.read_text(encoding="utf-8")

    if NEW in text:
        return f"[SKIP] {path} — already patched"

    count = text.count(OLD)
    if count == 0:
        return f"[ABORT] {path} — anchor not found, no changes made. Check the file manually."
    if count > 1:
        return f"[ABORT] {path} — anchor found {count} times (expected 1), refusing to guess. Check the file manually."

    patched = text.replace(OLD, NEW, 1)
    path.write_text(patched, encoding="utf-8")
    return f"[OK] {path} — patched"


def main():
    results = [patch_file(f) for f in FILES]
    for r in results:
        print(r)

    ok = sum(1 for r in results if r.startswith("[OK]"))
    skip = sum(1 for r in results if r.startswith("[SKIP]"))
    abort = sum(1 for r in results if r.startswith("[ABORT]"))

    print(f"\n{ok} patched, {skip} skipped, {abort} aborted (out of {len(results)})")

    if abort:
        sys.exit(1)


if __name__ == "__main__":
    main()