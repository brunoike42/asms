"""
ASMS Platform Billing — Phase 5B views.
Appendix D.5 (New School Self-Onboards) / Appendix G.5.

Deliberately does NOT attempt to auto-login the new admin across the
subdomain switch: this view runs on the root domain (asms.app/register),
the new tenant lives on {slug}.asms.app, and nothing in this project sets
SESSION_COOKIE_DOMAIN to share a session across subdomains. D.5 and G.5
both describe the real flow as "welcome email with login credentials/link,
then log in" rather than a seamless carry-over — so this follows the spec
rather than fighting the architecture.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta

from apps.core.models import Tenant
from .forms import SchoolRegistrationForm
from .models import Plan
from .tasks import provision_tenant

logger = logging.getLogger(__name__)

TRIAL_DAYS = 14


def register_school(request):
    plans = Plan.objects.filter(is_self_serve=True, is_active=True).order_by('base_price')

    if request.method == 'POST':
        form = SchoolRegistrationForm(request.POST, plans=plans)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                tenant = _create_tenant(data)
                admin_user = _create_school_admin(tenant, data)

            provision_tenant.delay(tenant.id)
            _send_welcome_email(tenant, admin_user)

            return render(request, 'platform_billing/register_success.html', {
                'page_title': 'Welcome to ASMS',
                'tenant': tenant,
                'portal_url': tenant.get_portal_url(),
            })
    else:
        form = SchoolRegistrationForm(plans=plans)

    return render(request, 'platform_billing/register.html', {
        'page_title': 'Start your free trial',
        'form': form,
        'plans': plans,
        'trial_days': TRIAL_DAYS,
    })


def _unique_slug(school_name: str) -> str:
    base = slugify(school_name)[:90] or 'school'
    slug = base
    suffix = 1
    while Tenant.objects.filter(slug=slug).exists():
        suffix += 1
        slug = f'{base}-{suffix}'
    return slug


def _create_tenant(data: dict) -> Tenant:
    now = timezone.now()
    return Tenant.objects.create(
        name=data['school_name'],
        slug=_unique_slug(data['school_name']),
        school_type=data['school_type'],
        country=data['country'],
        phone=data.get('school_phone', ''),
        email=data.get('school_email', ''),
        plan=data['plan'].slug,
        status=Tenant.StatusChoices.TRIAL,
        trial_end=now + timedelta(days=TRIAL_DAYS),
        billing_method='',  # chosen later, at first payment (Phase 5C)
    )


def _create_school_admin(tenant: Tenant, data: dict):
    from apps.accounts.models import User

    user = User(
        email=data['admin_email'],
        first_name=data['admin_first_name'],
        last_name=data['admin_last_name'],
        role=User.RoleChoices.SCHOOL_ADMIN,
        tenant=tenant,
        is_active=True,
        # Explicitly not a Django superuser — a school-side admin role, not
        # platform-level access. is_superuser=True here previously caused a
        # school admin to be silently excluded from EMIS access, since that
        # check keys off the app role, not this Django permission flag.
        is_superuser=False,
    )
    user.set_password(data['password'])
    user.save()
    return user


def _send_welcome_email(tenant: Tenant, admin_user) -> None:
    try:
        send_mail(
            subject=f'Welcome to ASMS — {tenant.name} is live',
            message=(
                f'Hi {admin_user.first_name},\n\n'
                f'{tenant.name} is set up on ASMS. Your {TRIAL_DAYS}-day free trial '
                f'of the {tenant.get_plan_display()} plan has started.\n\n'
                f'Log in here: {tenant.get_portal_url()}\n'
                f'Email: {admin_user.email}\n\n'
                'Next: add your classes, import your students, and set up your fee '
                'structure — everything you need is in the dashboard.\n'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@asms.app'),
            recipient_list=[admin_user.email],
            fail_silently=False,
        )
    except Exception as e:
        # Registration already succeeded — a failed welcome email shouldn't
        # undo it. The success page shows the same login URL regardless.
        logger.error(f'Welcome email failed for {tenant.slug}: {e}')
