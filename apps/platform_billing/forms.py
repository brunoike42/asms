"""
ASMS Platform Billing — Phase 5B: self-onboarding form.
Appendix D.5 / G.5.
"""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django import forms

from apps.core.models import Tenant
from .models import Plan


class SchoolRegistrationForm(forms.Form):
    # School
    school_name = forms.CharField(max_length=200, label='School name')
    school_type = forms.ChoiceField(choices=Tenant.SchoolTypeChoices.choices, initial=Tenant.SchoolTypeChoices.PRIMARY)
    country = forms.ChoiceField(
        choices=[('Uganda', 'Uganda'), ('Kenya', 'Kenya'), ('Tanzania', 'Tanzania'),
                 ('Rwanda', 'Rwanda'), ('Ghana', 'Ghana')],
        initial='Uganda',
    )
    school_phone = forms.CharField(max_length=20, required=False, label='School phone')
    school_email = forms.EmailField(required=False, label='School email')

    # Plan — populated from the DB, not a static enum (Section 5.1)
    plan = forms.ModelChoiceField(
        queryset=Plan.objects.none(), empty_label=None,
        to_field_name='slug', label='Choose your plan',
        widget=forms.RadioSelect,
    )

    # Admin account — created as School Super Admin (Appendix G.5 step)
    admin_first_name = forms.CharField(max_length=100, label='Your first name')
    admin_last_name = forms.CharField(max_length=100, label='Your last name')
    admin_email = forms.EmailField(label='Your email (this is your login)')
    password = forms.CharField(widget=forms.PasswordInput, label='Password')
    password_confirm = forms.CharField(widget=forms.PasswordInput, label='Confirm password')

    def __init__(self, *args, plans=None, **kwargs):
        super().__init__(*args, **kwargs)
        if plans is not None:
            self.fields['plan'].queryset = plans

    def clean_school_name(self):
        return self.cleaned_data['school_name'].strip()

    def clean_admin_email(self):
        from apps.accounts.models import User
        email = self.cleaned_data['admin_email'].strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email

    def clean_password(self):
        password = self.cleaned_data['password']
        # Runs against whatever AUTH_PASSWORD_VALIDATORS is configured with —
        # no assumption made here about what those rules actually are.
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        confirm = cleaned.get('password_confirm')
        if password and confirm and password != confirm:
            self.add_error('password_confirm', "Passwords don't match.")
        return cleaned
