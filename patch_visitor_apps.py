# -*- coding: utf-8 -*-
"""
Patch script — apps/visitor/apps.py
Adds ready() so signals.py (host SMS notification on check-in) actually
gets connected on startup — Django never imports signals.py on its own.

    py patch_visitor_apps.py
    py -m py_compile apps\visitor\apps.py
"""
import pathlib

TARGET = pathlib.Path("apps/visitor/apps.py")

ANCHOR = '''class VisitorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.visitor"
    verbose_name = "Visitor Management"'''

REPLACEMENT = '''class VisitorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.visitor"
    verbose_name = "Visitor Management"

    def ready(self):
        from . import signals  # noqa: F401'''


def main():
    with open(TARGET, "r", encoding="utf-8", newline="") as f:
        text = f.read()

    assert ANCHOR in text, "apps.py doesn't match expected content — stopping without writing anything."
    assert "def ready(self):" not in text, "Already patched?"

    text = text.replace(ANCHOR, REPLACEMENT)

    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"Patched {TARGET} — added ready() hook.")


if __name__ == "__main__":
    main()
