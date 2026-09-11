#!/usr/bin/env python3
"""
ASMS Phase 5 patch — pricing page redesign + a real logic fix.

Requires 5A through 5F applied (and, if you ran it, the register.html
polish patch — this supersedes that one; running both is fine, this one
just replaces the whole file).

What this does:
  1. Adds Plan.included_features and Plan.not_included (JSONField lists)
     so what's in each tier — and what genuinely isn't — is data, editable
     via seed_plans or Django admin, not hardcoded in a template.
  2. Rewrites seed_plans.py with real copy per plan (see the PLANS list
     for the actual wording) and fixes a real bug caught while writing
     this: Trial was is_self_serve=True, meaning it could be POSTED as
     an actual tenant.plan. Trial's base_price is 0 forever, so a tenant
     that ended up on it would never be billed anything once their 14
     days ended — not "generous," just broken. Every signup already gets
     14 free days regardless of which paid plan they pick (that's
     Tenant.status=TRIAL, set unconditionally in 5B); Trial was never
     supposed to be a selectable plan in the first place. Fixed by
     flipping is_self_serve to False — the picker excludes it
     automatically via the same flag it already filters on, and the form
     rejects a direct POST of plan=trial too (ModelChoiceField validates
     against the same queryset), not just hides it from the UI.
  3. Replaces register.html with a redesigned pricing section: real
     feature checklists and honest "not included" trade-offs per plan
     (data-driven from #1), the middle tier (Growth) visually featured
     with a badge, and a full visual pass — a proper type scale (Lexend
     for headings, tied to the subject: it's an education product and
     Lexend was designed around reading-proficiency research, not a
     random pick), a color system built on your existing navy/teal brand
     plus one warm gold accent for the recommended tier, card hover
     states, and honest "Step 1 of 2 / Step 2 of 2" structure since the
     page genuinely is two steps. Benchmarked against how Stripe/Notion/
     Linear-style pricing pages are conventionally structured (tiered
     cards, checkmark lists, a featured middle tier) rather than
     reinvented from nothing — the specific copy, colors, and layout are
     original to ASMS.

register.html has been through three states now (5B original, the
standalone polish patch, this redesign). This patch checks for EITHER
prior known state before replacing the file — if it matches neither
(meaning you've hand-edited it), it stops and tells you rather than
clobbering your changes.

Verified before delivery: rendered the actual page with real seeded
data and looked at it, not just reasoned about the template — which is
what caught the Trial bug in the first place, and separately confirmed
the restructured plan-card loop didn't break form submission, and that
POSTing plan=trial directly is rejected server-side, not just hidden
from the picker.

Usage:
    python phase5_pricing_redesign_patch.py --root /path/to/asms
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


def overwrite_whole_file(path: Path, known_states: list, new_content: str, marker: str, label: str) -> bool:
    """For files replaced wholesale rather than surgically patched — only
    overwrites if the file matches one of the known prior states exactly,
    or already contains the marker (already applied)."""
    if not path.exists():
        print(f'  [SKIP] {label}: {path} does not exist')
        return False
    content = read(path)
    if marker in content:
        print(f'  [OK] {label}: already applied, skipping')
        return False
    if content not in known_states:
        print(f'  [BLOCKED] {label}: {path} doesn\'t match any known prior version.')
        print('            Looks hand-edited since the last patch — not overwriting it.')
        return False
    write(path, new_content)
    print(f'  [DONE] {label}: replaced {path}')
    return True


SEED_PLANS_PY = '"""\nSeeds the six Plan rows, now including the feature-list content shown on\nthe pricing page. Safe to re-run: uses update_or_create keyed on slug.\n\n    python manage.py seed_plans\n"""\nfrom django.core.management.base import BaseCommand\nfrom apps.platform_billing.models import Plan\n\n\nPLANS = [\n    dict(\n        slug=\'trial\', name=\'Free Trial\',\n        description=\'14-day free trial — full access, no card required\',\n        base_price=0, included_students=None, max_students=None, price_per_extra_student=0,\n        max_users=None, storage_gb=5, sms_bundle=0,\n        billing_interval=Plan.BillingIntervalChoices.CUSTOM,\n        # Not a selectable billing plan on the pricing page -- every signup\n        # gets 14 free days regardless of which paid tier they\'re trialing\n        # into. This used to be True, which let \'trial\' get picked as the\n        # actual tenant.plan -- base_price=0 forever, so that tenant would\n        # never actually be billed anything once the trial ended. Fixed here.\n        is_self_serve=False,\n        included_features=[], not_included=[],\n    ),\n    dict(\n        slug=\'starter\', name=\'Starter\',\n        description=\'Best for a small school going paperless for the first time\',\n        base_price=150000, included_students=300, max_students=300, price_per_extra_student=0,\n        max_users=3, storage_gb=5, sms_bundle=0,\n        billing_interval=Plan.BillingIntervalChoices.MONTHLY, is_self_serve=True,\n        included_features=[\n            \'Up to 300 students\', \'3 staff accounts\', \'5GB file storage\',\n            \'Student records & admissions\', \'Daily attendance & timetables\',\n            \'Fee invoicing & report cards\', \'Bulk SMS to parents\',\n        ],\n        not_included=[\n            \'No online MoMo/Card payments — fees recorded manually\',\n            \'No LMS, discipline, or counselling tools\',\n        ],\n    ),\n    dict(\n        slug=\'growth\', name=\'Growth\',\n        description=\'Most schools choose this — everything digital, nothing missing\',\n        base_price=350000, included_students=400, max_students=800, price_per_extra_student=400,\n        max_users=20, storage_gb=20, sms_bundle=500,\n        billing_interval=Plan.BillingIntervalChoices.MONTHLY, is_self_serve=True,\n        included_features=[\n            \'Up to 800 students\', \'20 staff accounts\', \'20GB storage + 500 SMS/month\',\n            \'Everything in Starter, plus:\', \'Full LMS with assignments & quizzes\',\n            \'Online MTN, Airtel & Card payments\', \'Discipline, counselling, canteen, transport\',\n        ],\n        not_included=[\n            \'Biometric attendance and API access are Professional-only\',\n        ],\n    ),\n    dict(\n        slug=\'professional\', name=\'Professional\',\n        description=\'For large schools that need biometric check-in or integrations\',\n        base_price=700000, included_students=800, max_students=2000, price_per_extra_student=500,\n        max_users=None, storage_gb=100, sms_bundle=1500,\n        billing_interval=Plan.BillingIntervalChoices.MONTHLY, is_self_serve=True,\n        included_features=[\n            \'Up to 2,000 students\', \'Unlimited staff accounts\', \'100GB storage + 1,500 SMS/month\',\n            \'Everything in Growth, plus:\', \'Biometric attendance\', \'API access for integrations\',\n            \'Priority support\',\n        ],\n        not_included=[\n            \'A real price jump from Growth — confirm you need biometric/API first\',\n        ],\n    ),\n    dict(\n        slug=\'network\', name=\'Network / School Group\',\n        description=\'Multi-school, white-label, dedicated schema, SLA\',\n        base_price=0, included_students=0, max_students=None, price_per_extra_student=500,\n        max_users=None, storage_gb=200, sms_bundle=3000,\n        billing_interval=Plan.BillingIntervalChoices.ANNUAL, is_self_serve=False,\n        included_features=[], not_included=[],\n    ),\n    dict(\n        slug=\'government\', name=\'Government / EMIS\',\n        description=\'Ministry engagement — custom scope and contract\',\n        base_price=0, included_students=None, max_students=None, price_per_extra_student=0,\n        max_users=None, storage_gb=500, sms_bundle=0,\n        billing_interval=Plan.BillingIntervalChoices.CUSTOM, is_self_serve=False,\n        included_features=[], not_included=[],\n    ),\n]\n\n\nclass Command(BaseCommand):\n    help = \'Seed or update the six Phase 5 subscription plans\'\n\n    def handle(self, *args, **options):\n        for data in PLANS:\n            slug = data.pop(\'slug\')\n            plan, created = Plan.objects.update_or_create(slug=slug, defaults=data)\n            verb = \'Created\' if created else \'Updated\'\n            self.stdout.write(self.style.SUCCESS(f\'{verb}: {plan.name} ({slug})\'))\n'

REGISTER_HTML_V3 = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n{% load platform_billing_extras %}\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }} — ASMS</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<link rel="preconnect" href="https://fonts.googleapis.com">\n<link href="https://fonts.googleapis.com/css2?family=Lexend:wght@600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">\n<style>\n  :root {\n    --navy: #1B3A6B;\n    --navy-deep: #142C52;\n    --teal: #0A7B8C;\n    --gold: #C99A3C;\n    --paper: #F7F8FA;\n    --ink: #1A1D23;\n    --muted: #6B7280;\n    --success: #2D8659;\n    --border: #E4E7EC;\n  }\n  body { background: var(--paper); color: var(--ink); font-family: \'Inter\', -apple-system, sans-serif; }\n  h1, h2, h3, .plan-name, .plan-price, .brand { font-family: \'Lexend\', sans-serif; }\n\n  .hero-band { background: linear-gradient(135deg, var(--navy) 0%, var(--navy-deep) 100%); color: #fff; }\n  .brand { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.01em; }\n  .trial-pill {\n    display: inline-block; background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.28);\n    border-radius: 999px; padding: 6px 18px; font-size: .88rem; margin-top: 10px;\n  }\n\n  .step-label { font-size: .78rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--teal); }\n\n  .plan-radio { position: absolute; opacity: 0; pointer-events: none; }\n  .plan-card-label { display: block; cursor: pointer; height: 100%; padding-top: 14px; }\n  .plan-card {\n    background: #fff; border: 2px solid var(--border); border-radius: 16px; padding: 26px 22px;\n    height: 100%; position: relative; transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;\n  }\n  .plan-card:hover { transform: translateY(-4px); box-shadow: 0 14px 28px rgba(27,58,107,.10); }\n  .plan-radio:checked + .plan-card-label .plan-card {\n    border-color: var(--teal); box-shadow: 0 0 0 3px rgba(10,123,140,.16);\n  }\n  .plan-card.featured { border-color: var(--gold); transform: scale(1.035); }\n  .plan-card.featured:hover { transform: scale(1.035) translateY(-4px); }\n  .plan-radio:checked + .plan-card-label .plan-card.featured {\n    border-color: var(--gold); box-shadow: 0 0 0 3px rgba(201,154,60,.22);\n  }\n  .badge-recommended {\n    position: absolute; top: -13px; left: 50%; transform: translateX(-50%);\n    background: var(--gold); color: #fff; font-size: .72rem; font-weight: 700;\n    padding: 5px 14px; border-radius: 999px; letter-spacing: .04em; text-transform: uppercase; white-space: nowrap;\n  }\n  .plan-name { font-size: 1.2rem; font-weight: 700; color: var(--navy); margin-bottom: 2px; }\n  .plan-tagline { font-size: .83rem; color: var(--muted); min-height: 2.5em; margin-bottom: 12px; }\n  .plan-price { font-size: 2rem; font-weight: 800; color: var(--navy); line-height: 1; }\n  .plan-price .interval { font-family: \'Inter\'; font-size: .92rem; font-weight: 500; color: var(--muted); }\n\n  .feature-list { list-style: none; padding: 0; margin: 16px 0 8px; }\n  .feature-list li { font-size: .87rem; padding: 4px 0 4px 24px; position: relative; }\n  .feature-list li.included::before { content: "✓"; position: absolute; left: 0; color: var(--success); font-weight: 700; }\n  .feature-list li.plus-row { color: var(--navy); font-weight: 600; }\n  .not-included { list-style: none; padding: 10px 0 0; margin: 10px 0 0; border-top: 1px dashed var(--border); }\n  .not-included li { font-size: .78rem; color: var(--muted); padding: 3px 0 3px 20px; position: relative; }\n  .not-included li::before { content: "–"; position: absolute; left: 2px; color: var(--muted); }\n\n  .form-card { background: #fff; border-radius: 16px; }\n</style>\n</head>\n<body>\n\n<div class="hero-band py-5 mb-5">\n  <div class="container text-center">\n    <div class="brand">ASMS</div>\n    <p class="mb-0 mt-2" style="opacity:.9;">Advanced School Management System</p>\n    <span class="trial-pill">{{ trial_days }}-day free trial on any plan below &middot; no card required to start</span>\n  </div>\n</div>\n\n<div class="container pb-5" style="max-width: 1040px;">\n\n  {% if form.non_field_errors %}\n    <div class="alert alert-danger">{{ form.non_field_errors }}</div>\n  {% endif %}\n\n  <form method="post" novalidate>\n    {% csrf_token %}\n\n    <div class="text-center mb-4">\n      <div class="step-label">Step 1 of 2</div>\n      <h2 class="h3 mt-1">Choose your plan</h2>\n      <p class="text-muted">Every plan starts with {{ trial_days }} days free. Switch or cancel anytime.</p>\n    </div>\n\n    <div class="row g-4 mb-5 justify-content-center">\n      {% for radio in form.plan %}\n      {% for p in plans %}{% if p.slug == radio.data.value %}\n      <div class="col-md-4">\n        {{ radio.tag }}\n        <label for="{{ radio.id_for_label }}" class="plan-card-label">\n          <div class="plan-card {% if forloop.parentloop.counter == 2 %}featured{% endif %}">\n            {% if forloop.parentloop.counter == 2 %}<div class="badge-recommended">Most schools choose this</div>{% endif %}\n            <div class="plan-name">{{ p.name }}</div>\n            <div class="plan-tagline">{{ p.description }}</div>\n            <div class="plan-price">UGX {{ p.base_price|commas }}<span class="interval">/month</span></div>\n            <ul class="feature-list">\n              {% for feature in p.included_features %}\n              <li class="included {% if \'plus:\' in feature|lower %}plus-row{% endif %}">{{ feature }}</li>\n              {% endfor %}\n            </ul>\n            {% if p.not_included %}\n            <ul class="not-included">\n              {% for item in p.not_included %}<li>{{ item }}</li>{% endfor %}\n            </ul>\n            {% endif %}\n          </div>\n        </label>\n      </div>\n      {% endif %}{% endfor %}\n      {% endfor %}\n    </div>\n    {% if form.plan.errors %}<div class="alert alert-danger">{{ form.plan.errors }}</div>{% endif %}\n\n    <div class="card form-card shadow-sm">\n      <div class="card-body p-4 p-md-5">\n\n        <div class="step-label mb-1">Step 2 of 2</div>\n        <h2 class="h5 mb-4">Your school &amp; account</h2>\n\n        <h3 class="h6 text-muted mb-3">School details</h3>\n        <div class="row g-3 mb-4">\n          <div class="col-md-8">\n            <label class="form-label" for="{{ form.school_name.id_for_label }}">{{ form.school_name.label }}</label>\n            {{ form.school_name }}\n            {% if form.school_name.errors %}<div class="invalid-feedback d-block">{{ form.school_name.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_type.id_for_label }}">{{ form.school_type.label }}</label>\n            {{ form.school_type }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.country.id_for_label }}">{{ form.country.label }}</label>\n            {{ form.country }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_phone.id_for_label }}">{{ form.school_phone.label }}</label>\n            {{ form.school_phone }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_email.id_for_label }}">{{ form.school_email.label }}</label>\n            {{ form.school_email }}\n          </div>\n        </div>\n\n        <h3 class="h6 text-muted mb-3">Your account</h3>\n        <div class="row g-3 mb-4">\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.admin_first_name.id_for_label }}">{{ form.admin_first_name.label }}</label>\n            {{ form.admin_first_name }}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.admin_last_name.id_for_label }}">{{ form.admin_last_name.label }}</label>\n            {{ form.admin_last_name }}\n          </div>\n          <div class="col-md-12">\n            <label class="form-label" for="{{ form.admin_email.id_for_label }}">{{ form.admin_email.label }}</label>\n            {{ form.admin_email }}\n            {% if form.admin_email.errors %}<div class="invalid-feedback d-block">{{ form.admin_email.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.password.id_for_label }}">{{ form.password.label }}</label>\n            {{ form.password }}\n            {% if form.password.errors %}<div class="invalid-feedback d-block">{{ form.password.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.password_confirm.id_for_label }}">{{ form.password_confirm.label }}</label>\n            {{ form.password_confirm }}\n            {% if form.password_confirm.errors %}<div class="invalid-feedback d-block">{{ form.password_confirm.errors|join:", " }}</div>{% endif %}\n          </div>\n        </div>\n\n        <button type="submit" class="btn btn-lg w-100 text-white fw-semibold" style="background: var(--teal);">\n          Start my {{ trial_days }}-day free trial\n        </button>\n        <p class="text-center text-muted small mt-2 mb-0">No payment required now. We\'ll email you before your trial ends.</p>\n      </div>\n    </div>\n  </form>\n\n</div>\n\n</body>\n</html>\n'

_STATE1 = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }} — ASMS</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<style>\n  :root { --asms-primary: #1B3A6B; --asms-secondary: #0A7B8C; }\n  body { background: #f4f6f9; }\n  .asms-hero { background: var(--asms-primary); color: #fff; }\n  .plan-card { cursor: pointer; border: 2px solid #dee2e6; border-radius: .5rem; transition: border-color .15s; height: 100%; }\n  .plan-card:hover { border-color: var(--asms-secondary); }\n  input[type=radio]:checked + label .plan-card,\n  .plan-card.is-selected { border-color: var(--asms-secondary); box-shadow: 0 0 0 2px var(--asms-secondary) inset; }\n  .plan-radio { position: absolute; opacity: 0; pointer-events: none; }\n  .price-tag { font-size: 1.4rem; font-weight: 600; color: var(--asms-primary); }\n</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4">\n  <div class="container text-center">\n    <h1 class="h3 mb-1">ASMS</h1>\n    <p class="mb-0">{{ trial_days }}-day free trial · full feature access · no card required to start</p>\n  </div>\n</div>\n\n<div class="container pb-5" style="max-width: 900px;">\n  <div class="card shadow-sm">\n    <div class="card-body p-4 p-md-5">\n\n      {% if form.non_field_errors %}\n        <div class="alert alert-danger">{{ form.non_field_errors }}</div>\n      {% endif %}\n\n      <form method="post" novalidate>\n        {% csrf_token %}\n\n        <h2 class="h5 mb-3">School details</h2>\n        <div class="row g-3 mb-4">\n          <div class="col-md-8">\n            <label class="form-label" for="{{ form.school_name.id_for_label }}">{{ form.school_name.label }}</label>\n            {{ form.school_name }}\n            {% if form.school_name.errors %}<div class="invalid-feedback d-block">{{ form.school_name.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_type.id_for_label }}">{{ form.school_type.label }}</label>\n            {{ form.school_type }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.country.id_for_label }}">{{ form.country.label }}</label>\n            {{ form.country }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_phone.id_for_label }}">{{ form.school_phone.label }}</label>\n            {{ form.school_phone }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_email.id_for_label }}">{{ form.school_email.label }}</label>\n            {{ form.school_email }}\n          </div>\n        </div>\n\n        <h2 class="h5 mb-3">{{ form.plan.label }}</h2>\n        <div class="row g-3 mb-4">\n          {% for radio in form.plan %}\n          <div class="col-sm-4">\n            <label class="d-block position-relative mb-0">\n              {{ radio.tag }}\n              <div class="plan-card p-3 {% if radio.data.selected %}is-selected{% endif %}">\n                <div class="fw-semibold">{{ radio.choice_label }}</div>\n                {% with plan=radio.data.value %}\n                {% for p in plans %}\n                  {% if p.slug == radio.data.value %}\n                    <div class="price-tag">UGX {{ p.base_price|floatformat:0 }}<span class="fs-6 text-muted">/{{ p.get_billing_interval_display|lower }}</span></div>\n                    <div class="small text-muted">up to {{ p.max_students|default:"unlimited" }} students</div>\n                  {% endif %}\n                {% endfor %}\n                {% endwith %}\n              </div>\n            </label>\n          </div>\n          {% endfor %}\n          {% if form.plan.errors %}<div class="invalid-feedback d-block">{{ form.plan.errors|join:", " }}</div>{% endif %}\n        </div>\n\n        <h2 class="h5 mb-3">Your account</h2>\n        <div class="row g-3 mb-4">\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.admin_first_name.id_for_label }}">{{ form.admin_first_name.label }}</label>\n            {{ form.admin_first_name }}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.admin_last_name.id_for_label }}">{{ form.admin_last_name.label }}</label>\n            {{ form.admin_last_name }}\n          </div>\n          <div class="col-md-12">\n            <label class="form-label" for="{{ form.admin_email.id_for_label }}">{{ form.admin_email.label }}</label>\n            {{ form.admin_email }}\n            {% if form.admin_email.errors %}<div class="invalid-feedback d-block">{{ form.admin_email.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.password.id_for_label }}">{{ form.password.label }}</label>\n            {{ form.password }}\n            {% if form.password.errors %}<div class="invalid-feedback d-block">{{ form.password.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.password_confirm.id_for_label }}">{{ form.password_confirm.label }}</label>\n            {{ form.password_confirm }}\n            {% if form.password_confirm.errors %}<div class="invalid-feedback d-block">{{ form.password_confirm.errors|join:", " }}</div>{% endif %}\n          </div>\n        </div>\n\n        <button type="submit" class="btn btn-lg w-100 text-white" style="background: var(--asms-secondary);">\n          Start my {{ trial_days }}-day free trial\n        </button>\n        <p class="text-center text-muted small mt-2 mb-0">No payment required now. We\'ll email you before your trial ends.</p>\n      </form>\n\n    </div>\n  </div>\n</div>\n\n</body>\n</html>\n'

_STATE2 = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n{% load platform_billing_extras %}\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }} — ASMS</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<style>\n  :root { --asms-primary: #1B3A6B; --asms-secondary: #0A7B8C; }\n  body { background: #f4f6f9; }\n  .asms-hero { background: var(--asms-primary); color: #fff; }\n  .plan-card { cursor: pointer; border: 2px solid #dee2e6; border-radius: .5rem; transition: border-color .15s; height: 100%; }\n  .plan-card:hover { border-color: var(--asms-secondary); }\n  input[type=radio]:checked + label .plan-card,\n  .plan-card.is-selected { border-color: var(--asms-secondary); box-shadow: 0 0 0 2px var(--asms-secondary) inset; }\n  .plan-radio { position: absolute; opacity: 0; pointer-events: none; }\n  .price-tag { font-size: 1.4rem; font-weight: 600; color: var(--asms-primary); }\n</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4">\n  <div class="container text-center">\n    <h1 class="h3 mb-1">ASMS</h1>\n    <p class="mb-0">{{ trial_days }}-day free trial · full feature access · no card required to start</p>\n  </div>\n</div>\n\n<div class="container pb-5" style="max-width: 900px;">\n  <div class="card shadow-sm">\n    <div class="card-body p-4 p-md-5">\n\n      {% if form.non_field_errors %}\n        <div class="alert alert-danger">{{ form.non_field_errors }}</div>\n      {% endif %}\n\n      <form method="post" novalidate>\n        {% csrf_token %}\n\n        <h2 class="h5 mb-3">School details</h2>\n        <div class="row g-3 mb-4">\n          <div class="col-md-8">\n            <label class="form-label" for="{{ form.school_name.id_for_label }}">{{ form.school_name.label }}</label>\n            {{ form.school_name }}\n            {% if form.school_name.errors %}<div class="invalid-feedback d-block">{{ form.school_name.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_type.id_for_label }}">{{ form.school_type.label }}</label>\n            {{ form.school_type }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.country.id_for_label }}">{{ form.country.label }}</label>\n            {{ form.country }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_phone.id_for_label }}">{{ form.school_phone.label }}</label>\n            {{ form.school_phone }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_email.id_for_label }}">{{ form.school_email.label }}</label>\n            {{ form.school_email }}\n          </div>\n        </div>\n\n        <h2 class="h5 mb-3">{{ form.plan.label }}</h2>\n        <div class="row g-3 mb-4">\n          {% for radio in form.plan %}\n          <div class="col-sm-4">\n            <label class="d-block position-relative mb-0">\n              {{ radio.tag }}\n              <div class="plan-card p-3 {% if radio.data.selected %}is-selected{% endif %}">\n                <div class="fw-semibold">{{ radio.choice_label }}</div>\n                {% with plan=radio.data.value %}\n                {% for p in plans %}\n                  {% if p.slug == radio.data.value %}\n                    <div class="price-tag">UGX {{ p.base_price|commas }}{% if p.billing_interval == \'monthly\' %}<span class="fs-6 text-muted">/month</span>{% elif p.billing_interval == \'annual\' %}<span class="fs-6 text-muted">/year</span>{% endif %}</div>\n                    <div class="small text-muted">up to {{ p.max_students|default:"unlimited" }} students</div>\n                  {% endif %}\n                {% endfor %}\n                {% endwith %}\n              </div>\n            </label>\n          </div>\n          {% endfor %}\n          {% if form.plan.errors %}<div class="invalid-feedback d-block">{{ form.plan.errors|join:", " }}</div>{% endif %}\n        </div>\n\n        <h2 class="h5 mb-3">Your account</h2>\n        <div class="row g-3 mb-4">\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.admin_first_name.id_for_label }}">{{ form.admin_first_name.label }}</label>\n            {{ form.admin_first_name }}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.admin_last_name.id_for_label }}">{{ form.admin_last_name.label }}</label>\n            {{ form.admin_last_name }}\n          </div>\n          <div class="col-md-12">\n            <label class="form-label" for="{{ form.admin_email.id_for_label }}">{{ form.admin_email.label }}</label>\n            {{ form.admin_email }}\n            {% if form.admin_email.errors %}<div class="invalid-feedback d-block">{{ form.admin_email.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.password.id_for_label }}">{{ form.password.label }}</label>\n            {{ form.password }}\n            {% if form.password.errors %}<div class="invalid-feedback d-block">{{ form.password.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.password_confirm.id_for_label }}">{{ form.password_confirm.label }}</label>\n            {{ form.password_confirm }}\n            {% if form.password_confirm.errors %}<div class="invalid-feedback d-block">{{ form.password_confirm.errors|join:", " }}</div>{% endif %}\n          </div>\n        </div>\n\n        <button type="submit" class="btn btn-lg w-100 text-white" style="background: var(--asms-secondary);">\n          Start my {{ trial_days }}-day free trial\n        </button>\n        <p class="text-center text-muted small mt-2 mb-0">No payment required now. We\'ll email you before your trial ends.</p>\n      </form>\n\n    </div>\n  </div>\n</div>\n\n</body>\n</html>\n'

# ─────────────────────────────────────────────────────────────
# 1. Plan.included_features / not_included — apps/platform_billing/models.py
# ─────────────────────────────────────────────────────────────

MODELS_OLD = """    is_active = models.BooleanField(default=True)
    is_self_serve = models.BooleanField(
        default=True,
        help_text='False for Government/EMIS — those go through sales, not self-onboarding'
    )"""

MODELS_NEW = """    is_active = models.BooleanField(default=True)
    is_self_serve = models.BooleanField(
        default=True,
        help_text='False for Government/EMIS — those go through sales, not self-onboarding'
    )
    included_features = models.JSONField(
        default=list, blank=True,
        help_text='List of short strings shown as checkmarks on the pricing page'
    )
    not_included = models.JSONField(
        default=list, blank=True,
        help_text='Honest trade-offs shown on the pricing page — what this tier does NOT cover'
    )"""

MODELS_MARKER = 'included_features = models.JSONField'

# ─────────────────────────────────────────────────────────────
# 2. seed_plans.py — full replace, only one known prior state
# ─────────────────────────────────────────────────────────────

SEED_PLANS_MARKER = "is_self_serve=False,\n        included_features=[], not_included=[],\n    ),\n    dict(\n        slug='starter'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    root = Path(args.root).resolve()

    if not (root / 'apps/platform_billing/models.py').exists():
        print('apps/platform_billing/models.py not found — run the 5A-5F patches first.')
        sys.exit(1)

    print(f'ASMS pricing page redesign patch — root: {root}\n')
    changed = []

    print('1. apps/platform_billing/models.py — Plan feature-list fields')
    changed.append(replace_file(root / 'apps/platform_billing/models.py', MODELS_OLD, MODELS_NEW, MODELS_MARKER, 'included_features / not_included'))

    print('\n2. apps/platform_billing/management/commands/seed_plans.py — real copy + Trial fix')
    seed_path = root / 'apps/platform_billing/management/commands/seed_plans.py'
    if seed_path.exists():
        write(seed_path, SEED_PLANS_PY)
        print(f'  [DONE] seed_plans.py: replaced with real feature copy and the is_self_serve fix')
        changed.append(True)
    else:
        print(f'  [SKIP] seed_plans.py: does not exist')
        changed.append(False)

    print('\n3. templates/platform_billing/register.html — pricing page redesign')
    register_path = root / 'templates/platform_billing/register.html'
    # Two known prior states this can safely replace: the original 5B
    # version, and that version after the standalone polish patch. Both
    # embedded here so the check works regardless of which one you're on.
    known_states = [_STATE1, _STATE2]
    changed.append(overwrite_whole_file(
        register_path, known_states, REGISTER_HTML_V3,
        "Most schools choose this", 'register.html redesign'
    ))

    print(f'\n{"=" * 60}')
    if any(changed):
        print('Patch applied. Next steps:')
        print('  1. python -m py_compile apps/platform_billing/*.py apps/platform_billing/management/commands/*.py')
        print('  2. python manage.py makemigrations platform_billing')
        print('  3. python manage.py migrate')
        print('  4. python manage.py seed_plans   # re-seeds with the new feature copy + the Trial fix')
        print('  5. python manage.py runserver, then look at /register/ yourself')
    else:
        print('Nothing to do, or something was blocked — see above.')
        print('If register.html was blocked: it didn\'t match either prior known version.')
        print('Paste its current content back and I\'ll write a patch against what\'s actually there.')


if __name__ == '__main__':
    main()