# -*- coding: utf-8 -*-
"""
Patch script — templates/base.html

Adds a "Front Desk" sidebar section with a single link to Visitor
Management, placed right after Welfare (Discipline/Counselling) and
before Finance — same one-link-to-dashboard pattern those two already
use. Every other visitor screen (check-in, on-site, expected, muster,
watchlist) is reached from buttons inside the visitor dashboard itself,
not from separate sidebar entries — matching how discipline/counselling
don't list their sub-pages in the sidebar either.

IMPORTANT — unlike the apps/visitor/*.py patches, this one was NOT built
by extracting your real base.html from an uploaded file — it's built
from the text pasted into chat, then verified by rendering it end-to-end
through a real (test) Django project. The anchor below is a single
self-contained <a> block, chosen specifically to avoid a whitespace-only
blank line sitting right after it in the original, since that kind of
line is the easiest thing to transcribe wrong. If the assert below still
fails, it's almost certainly a whitespace difference between this script
and the literal file on disk, not a sign anything is corrupted — safe to
just paste the "Front Desk" block in by hand at that point.

Adjust TARGET below if base.html doesn't live at templates/base.html in
your project.

    py patch_base_html.py
"""
import pathlib

TARGET = pathlib.Path("templates/base.html")

ANCHOR = '''      <a href="{% url 'counselling:dashboard' %}" class="sidebar-link{% if request.resolver_match.namespace == 'counselling' %} active{% endif %}">
        <i class="bi bi-heart-pulse"></i> Counselling & Welfare
      </a>'''

NEW_SECTION = '''

      <div class="nav-section-label">Front Desk</div>
      <a href="{% url 'visitor:dashboard' %}" class="sidebar-link{% if request.resolver_match.namespace == 'visitor' %} active{% endif %}">
        <i class="bi bi-person-badge"></i> Visitor Management
      </a>'''


def main():
    with open(TARGET, "r", encoding="utf-8", newline="") as f:
        text = f.read()

    assert ANCHOR in text, (
        "Counselling sidebar link doesn't match — stopping without writing "
        "anything. Most likely cause: a whitespace difference between this "
        "script (built from pasted text) and the real file. Add the Front "
        "Desk block by hand if so — see the module docstring above."
    )
    assert "Front Desk" not in text, "Already patched?"

    text = text.replace(ANCHOR, ANCHOR + NEW_SECTION)

    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"Patched {TARGET} — added Front Desk / Visitor Management nav link.")


if __name__ == "__main__":
    main()
