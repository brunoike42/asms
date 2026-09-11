#!/usr/bin/env python3
"""
ASMS Phase 5B patch — self-onboarding flow (Appendix D.5 / G.5).

Requires 5A already applied (apps/platform_billing/ must exist).

What this does:
  1. Adds forms.py, views.py, urls.py, tasks.py to apps/platform_billing/.
  2. Adds templates/platform_billing/register.html and register_success.html
     — standalone pages (not extending base.html): this is a pre-login,
     public page reached at the root domain, not inside the tenant app
     shell, so it deliberately doesn't inherit the internal base template.
  3. Wires 'register/' into config/urls.py, anchored after the existing
     webhooks/sms/ include.

What this does NOT do:
  - No auto-login across the subdomain switch. This view runs on the root
    domain; the new tenant lives on {slug}.PLATFORM_DOMAIN; nothing in this
    project shares a session across subdomains (no SESSION_COOKIE_DOMAIN
    wildcard seen in settings). D.5 and G.5 both describe "welcome email
    with login link, then log in" rather than a seamless carry-over, so
    the success page just sends them to their subdomain to log in fresh.
    If you *do* want seamless auto-login, set
    SESSION_COOKIE_DOMAIN = '.{}'.format(PLATFORM_DOMAIN) and tell me —
    it's a small addition on top of this.
  - No rate limiting on the public POST endpoint. Worth adding
    (django-ratelimit or similar) before this is internet-facing.
  - PesaPal/MoMo/Airtel are not involved yet — trial needs no payment
    method. That's 5C.

One thing worth 30 seconds of your own verification rather than mine:
apps/accounts/models.py's User.save() creates the record via
User(...) + set_password() + save(), never referencing `username`. If your
User class extends AbstractBaseUser directly (no username field at all,
matching what I have on file for it) this is correct as-is. If it actually
extends AbstractUser (keeps a hidden `username` field), two signups in a
row will collide on that field's uniqueness constraint — tested and
reproduced that exact failure against a wrongly-shaped test stub before
catching it. Worth a 10-second look at the class declaration line.

Verified before delivery: reconstructed forms.py/views.py/tasks.py/urls.py
against a Django test Client — GET renders the form with only self-serve
plans shown (Network/Government correctly excluded), a full POST creates
Tenant + School Super Admin + starts the trial clock + provisions academic
year/terms/fee categories, duplicate school names get a suffixed slug,
duplicate admin emails and mismatched passwords are both rejected without
creating an orphan Tenant, and the welcome email contains the portal URL
but never the password.

Usage:
    python phase5_5b_patch.py --root /path/to/asms
"""
import argparse
import sys
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


def patch_file(path: Path, anchor: str, insert_after: str, marker: str, label: str) -> bool:
    if not path.exists():
        print(f'  [SKIP] {label}: {path} does not exist')
        return False
    content = read(path)
    if marker in content:
        print(f'  [OK] {label}: already applied, skipping')
        return False
    count = content.count(anchor)
    if count == 0:
        print(f'  [BLOCKED] {label}: anchor not found in {path}')
        return False
    if count > 1:
        print(f'  [BLOCKED] {label}: anchor found {count} times in {path} (needs to be unique)')
        return False
    write(path, content.replace(anchor, anchor + insert_after, 1))
    print(f'  [DONE] {label}: patched {path}')
    return True


def create_file_safe(path: Path, content: str, label: str) -> bool:
    if path.exists():
        print(f'  [SKIP] {label}: {path} already exists, not overwriting')
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    write(path, content)
    print(f'  [DONE] {label}: created {path}')
    return True


# ─────────────────────────────────────────────────────────────
# File contents (verified against a real Django test Client run)
# ─────────────────────────────────────────────────────────────

FORMS_PY = '"""\nASMS Platform Billing — Phase 5B: self-onboarding form.\nAppendix D.5 / G.5.\n"""\nfrom django.contrib.auth.password_validation import validate_password\nfrom django.core.exceptions import ValidationError\nfrom django import forms\n\nfrom apps.core.models import Tenant\nfrom .models import Plan\n\n\nclass SchoolRegistrationForm(forms.Form):\n    # School\n    school_name = forms.CharField(max_length=200, label=\'School name\')\n    school_type = forms.ChoiceField(choices=Tenant.SchoolTypeChoices.choices, initial=Tenant.SchoolTypeChoices.PRIMARY)\n    country = forms.ChoiceField(\n        choices=[(\'Uganda\', \'Uganda\'), (\'Kenya\', \'Kenya\'), (\'Tanzania\', \'Tanzania\'),\n                 (\'Rwanda\', \'Rwanda\'), (\'Ghana\', \'Ghana\')],\n        initial=\'Uganda\',\n    )\n    school_phone = forms.CharField(max_length=20, required=False, label=\'School phone\')\n    school_email = forms.EmailField(required=False, label=\'School email\')\n\n    # Plan — populated from the DB, not a static enum (Section 5.1)\n    plan = forms.ModelChoiceField(\n        queryset=Plan.objects.none(), empty_label=None,\n        to_field_name=\'slug\', label=\'Choose your plan\',\n        widget=forms.RadioSelect,\n    )\n\n    # Admin account — created as School Super Admin (Appendix G.5 step)\n    admin_first_name = forms.CharField(max_length=100, label=\'Your first name\')\n    admin_last_name = forms.CharField(max_length=100, label=\'Your last name\')\n    admin_email = forms.EmailField(label=\'Your email (this is your login)\')\n    password = forms.CharField(widget=forms.PasswordInput, label=\'Password\')\n    password_confirm = forms.CharField(widget=forms.PasswordInput, label=\'Confirm password\')\n\n    def __init__(self, *args, plans=None, **kwargs):\n        super().__init__(*args, **kwargs)\n        if plans is not None:\n            self.fields[\'plan\'].queryset = plans\n\n    def clean_school_name(self):\n        return self.cleaned_data[\'school_name\'].strip()\n\n    def clean_admin_email(self):\n        from apps.accounts.models import User\n        email = self.cleaned_data[\'admin_email\'].strip().lower()\n        if User.objects.filter(email=email).exists():\n            raise ValidationError(\'An account with this email already exists.\')\n        return email\n\n    def clean_password(self):\n        password = self.cleaned_data[\'password\']\n        # Runs against whatever AUTH_PASSWORD_VALIDATORS is configured with —\n        # no assumption made here about what those rules actually are.\n        validate_password(password)\n        return password\n\n    def clean(self):\n        cleaned = super().clean()\n        password = cleaned.get(\'password\')\n        confirm = cleaned.get(\'password_confirm\')\n        if password and confirm and password != confirm:\n            self.add_error(\'password_confirm\', "Passwords don\'t match.")\n        return cleaned\n'

VIEWS_PY = '"""\nASMS Platform Billing — Phase 5B views.\nAppendix D.5 (New School Self-Onboards) / Appendix G.5.\n\nDeliberately does NOT attempt to auto-login the new admin across the\nsubdomain switch: this view runs on the root domain (asms.app/register),\nthe new tenant lives on {slug}.asms.app, and nothing in this project sets\nSESSION_COOKIE_DOMAIN to share a session across subdomains. D.5 and G.5\nboth describe the real flow as "welcome email with login credentials/link,\nthen log in" rather than a seamless carry-over — so this follows the spec\nrather than fighting the architecture.\n"""\nimport logging\nfrom django.conf import settings\nfrom django.core.mail import send_mail\nfrom django.db import transaction\nfrom django.shortcuts import render, redirect\nfrom django.utils import timezone\nfrom django.utils.text import slugify\nfrom datetime import timedelta\n\nfrom apps.core.models import Tenant\nfrom .forms import SchoolRegistrationForm\nfrom .models import Plan\nfrom .tasks import provision_tenant\n\nlogger = logging.getLogger(__name__)\n\nTRIAL_DAYS = 14\n\n\ndef register_school(request):\n    plans = Plan.objects.filter(is_self_serve=True, is_active=True).order_by(\'base_price\')\n\n    if request.method == \'POST\':\n        form = SchoolRegistrationForm(request.POST, plans=plans)\n        if form.is_valid():\n            data = form.cleaned_data\n            with transaction.atomic():\n                tenant = _create_tenant(data)\n                admin_user = _create_school_admin(tenant, data)\n\n            provision_tenant.delay(tenant.id)\n            _send_welcome_email(tenant, admin_user)\n\n            return render(request, \'platform_billing/register_success.html\', {\n                \'page_title\': \'Welcome to ASMS\',\n                \'tenant\': tenant,\n                \'portal_url\': tenant.get_portal_url(),\n            })\n    else:\n        form = SchoolRegistrationForm(plans=plans)\n\n    return render(request, \'platform_billing/register.html\', {\n        \'page_title\': \'Start your free trial\',\n        \'form\': form,\n        \'plans\': plans,\n        \'trial_days\': TRIAL_DAYS,\n    })\n\n\ndef _unique_slug(school_name: str) -> str:\n    base = slugify(school_name)[:90] or \'school\'\n    slug = base\n    suffix = 1\n    while Tenant.objects.filter(slug=slug).exists():\n        suffix += 1\n        slug = f\'{base}-{suffix}\'\n    return slug\n\n\ndef _create_tenant(data: dict) -> Tenant:\n    now = timezone.now()\n    return Tenant.objects.create(\n        name=data[\'school_name\'],\n        slug=_unique_slug(data[\'school_name\']),\n        school_type=data[\'school_type\'],\n        country=data[\'country\'],\n        phone=data.get(\'school_phone\', \'\'),\n        email=data.get(\'school_email\', \'\'),\n        plan=data[\'plan\'].slug,\n        status=Tenant.StatusChoices.TRIAL,\n        trial_end=now + timedelta(days=TRIAL_DAYS),\n        billing_method=\'\',  # chosen later, at first payment (Phase 5C)\n    )\n\n\ndef _create_school_admin(tenant: Tenant, data: dict):\n    from apps.accounts.models import User\n\n    user = User(\n        email=data[\'admin_email\'],\n        first_name=data[\'admin_first_name\'],\n        last_name=data[\'admin_last_name\'],\n        role=User.RoleChoices.SCHOOL_ADMIN,\n        tenant=tenant,\n        is_active=True,\n        # Explicitly not a Django superuser — a school-side admin role, not\n        # platform-level access. is_superuser=True here previously caused a\n        # school admin to be silently excluded from EMIS access, since that\n        # check keys off the app role, not this Django permission flag.\n        is_superuser=False,\n    )\n    user.set_password(data[\'password\'])\n    user.save()\n    return user\n\n\ndef _send_welcome_email(tenant: Tenant, admin_user) -> None:\n    try:\n        send_mail(\n            subject=f\'Welcome to ASMS — {tenant.name} is live\',\n            message=(\n                f\'Hi {admin_user.first_name},\\n\\n\'\n                f\'{tenant.name} is set up on ASMS. Your {TRIAL_DAYS}-day free trial \'\n                f\'of the {tenant.get_plan_display()} plan has started.\\n\\n\'\n                f\'Log in here: {tenant.get_portal_url()}\\n\'\n                f\'Email: {admin_user.email}\\n\\n\'\n                \'Next: add your classes, import your students, and set up your fee \'\n                \'structure — everything you need is in the dashboard.\\n\'\n            ),\n            from_email=getattr(settings, \'DEFAULT_FROM_EMAIL\', \'noreply@asms.app\'),\n            recipient_list=[admin_user.email],\n            fail_silently=False,\n        )\n    except Exception as e:\n        # Registration already succeeded — a failed welcome email shouldn\'t\n        # undo it. The success page shows the same login URL regardless.\n        logger.error(f\'Welcome email failed for {tenant.slug}: {e}\')\n'

URLS_PY = "from django.urls import path\nfrom . import views\n\napp_name = 'platform_billing'\n\nurlpatterns = [\n    path('', views.register_school, name='register'),\n]\n"

TASKS_PY = '"""\nASMS Platform Billing — Phase 5B tasks.\nAppendix D.5: "Celery task: provision_tenant — set up default academic year,\nterm structure, fee categories."\n"""\nimport logging\nfrom datetime import timedelta\n\nfrom celery import shared_task\nfrom django.utils import timezone\n\nlogger = logging.getLogger(__name__)\n\n\n@shared_task\ndef provision_tenant(tenant_id):\n    """\n    Give a freshly self-onboarded tenant a working starting skeleton:\n    one current academic year, three terms, two fee categories.\n    Idempotent — safe to retry.\n    """\n    from apps.core.models import Tenant, AcademicYear, Term\n    from apps.finance.models import FeeCategory\n\n    try:\n        tenant = Tenant.objects.get(pk=tenant_id)\n    except Tenant.DoesNotExist:\n        logger.error(f\'provision_tenant: tenant {tenant_id} not found\')\n        return\n\n    if AcademicYear.objects.filter(tenant=tenant, is_current=True).exists():\n        logger.info(f\'provision_tenant: {tenant.slug} already provisioned, skipping\')\n        return\n\n    today = timezone.now().date()\n    year_end = today + timedelta(days=365)\n\n    academic_year = AcademicYear.objects.create(\n        tenant=tenant,\n        name=f\'{today.year}/{today.year + 1}\',\n        start_date=today,\n        end_date=year_end,\n        is_current=True,\n    )\n\n    # Placeholder term structure — three roughly-equal terms starting today.\n    # The school edits real dates during onboarding; this just avoids a\n    # totally empty term table blocking attendance/exams/finance screens.\n    span = (year_end - today).days\n    third = span // 3\n    term_specs = [\n        (Term.TermChoices.TERM_1, 0, third),\n        (Term.TermChoices.TERM_2, third, third * 2),\n        (Term.TermChoices.TERM_3, third * 2, span),\n    ]\n    for name, start_offset, end_offset in term_specs:\n        Term.objects.create(\n            tenant=tenant,\n            academic_year=academic_year,\n            name=name,\n            start_date=today + timedelta(days=start_offset),\n            end_date=today + timedelta(days=end_offset),\n            is_current=(name == Term.TermChoices.TERM_1),\n        )\n\n    for order, cat_name in enumerate([\'Tuition\', \'Activity Fee\']):\n        FeeCategory.objects.get_or_create(\n            tenant=tenant, name=cat_name,\n            defaults={\'order\': order},\n        )\n\n    logger.info(f\'provision_tenant: {tenant.slug} provisioned ({academic_year.name}, 3 terms, 2 fee categories)\')\n'

REGISTER_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }} — ASMS</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<style>\n  :root { --asms-primary: #1B3A6B; --asms-secondary: #0A7B8C; }\n  body { background: #f4f6f9; }\n  .asms-hero { background: var(--asms-primary); color: #fff; }\n  .plan-card { cursor: pointer; border: 2px solid #dee2e6; border-radius: .5rem; transition: border-color .15s; height: 100%; }\n  .plan-card:hover { border-color: var(--asms-secondary); }\n  input[type=radio]:checked + label .plan-card,\n  .plan-card.is-selected { border-color: var(--asms-secondary); box-shadow: 0 0 0 2px var(--asms-secondary) inset; }\n  .plan-radio { position: absolute; opacity: 0; pointer-events: none; }\n  .price-tag { font-size: 1.4rem; font-weight: 600; color: var(--asms-primary); }\n</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4">\n  <div class="container text-center">\n    <h1 class="h3 mb-1">ASMS</h1>\n    <p class="mb-0">{{ trial_days }}-day free trial · full feature access · no card required to start</p>\n  </div>\n</div>\n\n<div class="container pb-5" style="max-width: 900px;">\n  <div class="card shadow-sm">\n    <div class="card-body p-4 p-md-5">\n\n      {% if form.non_field_errors %}\n        <div class="alert alert-danger">{{ form.non_field_errors }}</div>\n      {% endif %}\n\n      <form method="post" novalidate>\n        {% csrf_token %}\n\n        <h2 class="h5 mb-3">School details</h2>\n        <div class="row g-3 mb-4">\n          <div class="col-md-8">\n            <label class="form-label" for="{{ form.school_name.id_for_label }}">{{ form.school_name.label }}</label>\n            {{ form.school_name }}\n            {% if form.school_name.errors %}<div class="invalid-feedback d-block">{{ form.school_name.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_type.id_for_label }}">{{ form.school_type.label }}</label>\n            {{ form.school_type }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.country.id_for_label }}">{{ form.country.label }}</label>\n            {{ form.country }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_phone.id_for_label }}">{{ form.school_phone.label }}</label>\n            {{ form.school_phone }}\n          </div>\n          <div class="col-md-4">\n            <label class="form-label" for="{{ form.school_email.id_for_label }}">{{ form.school_email.label }}</label>\n            {{ form.school_email }}\n          </div>\n        </div>\n\n        <h2 class="h5 mb-3">{{ form.plan.label }}</h2>\n        <div class="row g-3 mb-4">\n          {% for radio in form.plan %}\n          <div class="col-sm-4">\n            <label class="d-block position-relative mb-0">\n              {{ radio.tag }}\n              <div class="plan-card p-3 {% if radio.data.selected %}is-selected{% endif %}">\n                <div class="fw-semibold">{{ radio.choice_label }}</div>\n                {% with plan=radio.data.value %}\n                {% for p in plans %}\n                  {% if p.slug == radio.data.value %}\n                    <div class="price-tag">UGX {{ p.base_price|floatformat:0 }}<span class="fs-6 text-muted">/{{ p.get_billing_interval_display|lower }}</span></div>\n                    <div class="small text-muted">up to {{ p.max_students|default:"unlimited" }} students</div>\n                  {% endif %}\n                {% endfor %}\n                {% endwith %}\n              </div>\n            </label>\n          </div>\n          {% endfor %}\n          {% if form.plan.errors %}<div class="invalid-feedback d-block">{{ form.plan.errors|join:", " }}</div>{% endif %}\n        </div>\n\n        <h2 class="h5 mb-3">Your account</h2>\n        <div class="row g-3 mb-4">\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.admin_first_name.id_for_label }}">{{ form.admin_first_name.label }}</label>\n            {{ form.admin_first_name }}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.admin_last_name.id_for_label }}">{{ form.admin_last_name.label }}</label>\n            {{ form.admin_last_name }}\n          </div>\n          <div class="col-md-12">\n            <label class="form-label" for="{{ form.admin_email.id_for_label }}">{{ form.admin_email.label }}</label>\n            {{ form.admin_email }}\n            {% if form.admin_email.errors %}<div class="invalid-feedback d-block">{{ form.admin_email.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.password.id_for_label }}">{{ form.password.label }}</label>\n            {{ form.password }}\n            {% if form.password.errors %}<div class="invalid-feedback d-block">{{ form.password.errors|join:", " }}</div>{% endif %}\n          </div>\n          <div class="col-md-6">\n            <label class="form-label" for="{{ form.password_confirm.id_for_label }}">{{ form.password_confirm.label }}</label>\n            {{ form.password_confirm }}\n            {% if form.password_confirm.errors %}<div class="invalid-feedback d-block">{{ form.password_confirm.errors|join:", " }}</div>{% endif %}\n          </div>\n        </div>\n\n        <button type="submit" class="btn btn-lg w-100 text-white" style="background: var(--asms-secondary);">\n          Start my {{ trial_days }}-day free trial\n        </button>\n        <p class="text-center text-muted small mt-2 mb-0">No payment required now. We\'ll email you before your trial ends.</p>\n      </form>\n\n    </div>\n  </div>\n</div>\n\n</body>\n</html>\n'

REGISTER_SUCCESS_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }}</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<style>\n  body { background: #f4f6f9; }\n  .asms-hero { background: #1B3A6B; color: #fff; }\n</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4">\n  <div class="container text-center"><h1 class="h3 mb-0">ASMS</h1></div>\n</div>\n\n<div class="container text-center pb-5" style="max-width: 560px;">\n  <div class="card shadow-sm">\n    <div class="card-body p-4 p-md-5">\n      <h2 class="h4 mb-3">{{ tenant.name }} is live 🎉</h2>\n      <p class="text-muted">\n        Your trial is running. We\'ve emailed your login link to your account email as well.\n      </p>\n      <a href="{{ portal_url }}" class="btn btn-lg w-100 text-white mt-3" style="background:#0A7B8C;">\n        Go to {{ tenant.name }}\'s dashboard\n      </a>\n      <p class="small text-muted mt-3 mb-0">{{ portal_url }}</p>\n    </div>\n  </div>\n</div>\n\n</body>\n</html>\n'

# ─────────────────────────────────────────────────────────────
# config/urls.py wiring
# ─────────────────────────────────────────────────────────────

URLS_ANCHOR = '    path("webhooks/sms/", include("apps.notifications.urls")),'
URLS_INSERT = "\n    path('register/', include('apps.platform_billing.urls', namespace='platform_billing')),"
URLS_MARKER = "apps.platform_billing.urls"


def main():
    parser = argparse.ArgumentParser(description='Apply the ASMS Phase 5B patch')
    parser.add_argument('--root', default='.', help='Project root (contains manage.py)')
    args = parser.parse_args()
    root = Path(args.root).resolve()

    if not (root / 'apps/platform_billing/models.py').exists():
        print('apps/platform_billing/models.py not found — run the 5A patch first.')
        sys.exit(1)

    print(f'ASMS Phase 5B patch — root: {root}\n')
    changed = []

    print('1. apps/platform_billing/ — forms, views, urls, tasks')
    changed.append(create_file_safe(root / 'apps/platform_billing/forms.py', FORMS_PY, 'forms.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/views.py', VIEWS_PY, 'views.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/urls.py', URLS_PY, 'urls.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/tasks.py', TASKS_PY, 'tasks.py'))

    print('\n2. templates/platform_billing/')
    changed.append(create_file_safe(root / 'templates/platform_billing/register.html', REGISTER_HTML, 'register.html'))
    changed.append(create_file_safe(root / 'templates/platform_billing/register_success.html', REGISTER_SUCCESS_HTML, 'register_success.html'))

    print('\n3. config/urls.py')
    changed.append(patch_file(root / 'config/urls.py', URLS_ANCHOR, URLS_INSERT, URLS_MARKER, "register/ route"))

    print(f'\n{"=" * 60}')
    if any(changed):
        print('Patch applied. Next steps:')
        print('  1. python -m py_compile apps/platform_billing/*.py')
        print('  2. python manage.py check')
        print('  3. Start the dev server, visit /register/, sign up a test school')
        print('  4. Check the console/log backend for the welcome email')
    else:
        print('Nothing to do — already applied, or something was blocked (see [BLOCKED] above).')


if __name__ == '__main__':
    main()