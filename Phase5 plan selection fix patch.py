#!/usr/bin/env python3
"""
ASMS — plan-selection fix for the pricing page.

Root cause: SchoolRegistrationForm.plan uses widget=forms.RadioSelect with
no attrs, so the rendered <input type="radio"> never gets class="plan-radio".
register.html's CSS only hides/styles inputs matching .plan-radio, so:
  - the raw native radio circle renders unstyled, floating above each card
    (visually disconnected from it — not just ugly, actively confusing)
  - the .plan-radio:checked + .plan-card-label .plan-card rule that's
    supposed to show a teal border on the selected card never fires,
    because nothing ever matches .plan-radio in the first place

The <label for="..."> already correctly wraps each card and points at the
right input id, so clicking a card does check its radio — there's just
zero visual confirmation that it happened. That's consistent with what
you saw: submit without a plan checked, and Django's ModelChoiceField
correctly (if unhelpfully) reports "This field is required."

Two changes:
  1. apps/platform_billing/forms.py — give the RadioSelect widget the
     class the CSS is already looking for.
  2. templates/platform_billing/register.html — a small CSS addition so
     the "selected" state is actually visible, plus the "Select this
     plan" CTA you asked for at the bottom of each card. It's a <span>,
     not a <button>: a real button nested inside a <label> can eat the
     click in some browsers instead of forwarding it to the radio, and
     there's no need to fight that when the label already does the job.

Not touched: the required-field validation itself, which is correct
Django behavior for an unselected required ModelChoiceField — the fix is
making selection visible, not loosening validation.

Verified before delivery: ran this against a local copy of your actual
forms.py and register.html (as pasted) rather than just reasoning about
the anchors — all three steps applied cleanly.

Usage:
    python phase5_plan_selection_fix_patch.py --root /path/to/asms
"""
import argparse
import sys
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


def replace_file(path: Path, old: str, new: str, marker: str, label: str) -> bool:
    if not path.exists():
        print(f'  [SKIP] {label}: {path} does not exist')
        return False
    content = read(path)
    if marker in content:
        print(f'  [OK] {label}: already applied, skipping')
        return False
    if old not in content:
        print(f'  [BLOCKED] {label}: anchor not found in {path}')
        print('            File may have changed since the last patch. Not touching it.')
        return False
    write(path, content.replace(old, new, 1))
    print(f'  [DONE] {label}: patched {path}')
    return True


# ────────────────────────────────────────────────────────────────
# 1. forms.py — give the radio widget the class its own CSS expects
# ────────────────────────────────────────────────────────────────

FORMS_OLD = """    plan = forms.ModelChoiceField(
        queryset=Plan.objects.none(), empty_label=None,
        to_field_name='slug', label='Choose your plan',
        widget=forms.RadioSelect,
    )"""

FORMS_NEW = """    plan = forms.ModelChoiceField(
        queryset=Plan.objects.none(), empty_label=None,
        to_field_name='slug', label='Choose your plan',
        widget=forms.RadioSelect(attrs={'class': 'plan-radio'}),
    )"""

FORMS_MARKER = "widget=forms.RadioSelect(attrs={'class': 'plan-radio'})"

# ────────────────────────────────────────────────────────────────
# 2. register.html — visible selected-state + "Select this plan" CTA
# ────────────────────────────────────────────────────────────────

CSS_OLD = """  .plan-radio:checked + .plan-card-label .plan-card.featured {
    border-color: var(--gold); box-shadow: 0 0 0 3px rgba(201,154,60,.22);
  }"""

CSS_NEW = """  .plan-radio:checked + .plan-card-label .plan-card.featured {
    border-color: var(--gold); box-shadow: 0 0 0 3px rgba(201,154,60,.22);
  }
  .plan-select-cta {
    display: block; text-align: center; margin-top: 16px; padding: 10px;
    border-radius: 8px; font-weight: 600; font-size: .85rem;
    background: var(--paper); color: var(--teal); border: 1.5px solid var(--teal);
    transition: background .15s ease, color .15s ease;
  }
  .plan-radio:checked + .plan-card-label .plan-select-cta {
    background: var(--teal); color: #fff;
  }"""

CSS_MARKER = '.plan-select-cta {'

CTA_OLD = """            {% if p.not_included %}
            <ul class="not-included">
              {% for item in p.not_included %}<li>{{ item }}</li>{% endfor %}
            </ul>
            {% endif %}
          </div>
        </label>"""

CTA_NEW = """            {% if p.not_included %}
            <ul class="not-included">
              {% for item in p.not_included %}<li>{{ item }}</li>{% endfor %}
            </ul>
            {% endif %}
            <span class="plan-select-cta">Select this plan</span>
          </div>
        </label>"""

CTA_MARKER = 'class="plan-select-cta"'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    root = Path(args.root).resolve()

    forms_path = root / 'apps/platform_billing/forms.py'
    template_path = root / 'templates/platform_billing/register.html'

    if not forms_path.exists():
        print(f'{forms_path} not found — run this from the asms root, or pass --root.')
        sys.exit(1)

    print(f'ASMS plan-selection fix — root: {root}\n')
    changed = []

    print('1. apps/platform_billing/forms.py — radio widget class')
    changed.append(replace_file(forms_path, FORMS_OLD, FORMS_NEW, FORMS_MARKER, 'plan-radio class'))

    print('\n2. templates/platform_billing/register.html — selected-state CSS')
    changed.append(replace_file(template_path, CSS_OLD, CSS_NEW, CSS_MARKER, 'selected-state CSS'))

    print('\n3. templates/platform_billing/register.html — "Select this plan" CTA')
    changed.append(replace_file(template_path, CTA_OLD, CTA_NEW, CTA_MARKER, 'Select this plan CTA'))

    print(f'\n{"=" * 60}')
    if any(changed):
        print('Patch applied. Next:')
        print('  1. python -m py_compile apps/platform_billing/forms.py')
        print('  2. python manage.py runserver, then open /register/ and click a card —')
        print('     confirm it visibly highlights (teal border + filled CTA) before you submit.')
    else:
        print('Nothing to do, or something was blocked — see above.')
        print("If a step was blocked: the file has likely drifted from what this patches")
        print("against. Paste its current content back and I'll patch against that.")


if __name__ == '__main__':
    main()