"""
ASMS — Student Portal Forms
Phase 3
"""
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import (
    TermEnrollment,
    CourseUnitRegistration,
    ExamAppeal,
    ProgramChangeRequest,
    LeaveOfAbsenceRequest,
)


class TermEnrollmentForm(forms.ModelForm):
    """Student confirms enrollment for the upcoming term/semester."""

    class Meta:
        model  = TermEnrollment
        fields = ['status', 'study_year', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'study_year': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                           'placeholder': 'Any notes for the registrar (optional)'}),
        }
        labels = {
            'status': 'Enrollment Status',
            'study_year': 'Your Current Year of Study',
        }


class ExamAppealForm(forms.ModelForm):
    """Student submits a formal exam result appeal."""

    class Meta:
        model  = ExamAppeal
        fields = ['subject', 'term', 'appeal_type', 'statement']
        widgets = {
            'subject':     forms.Select(attrs={'class': 'form-select'}),
            'term':        forms.Select(attrs={'class': 'form-select'}),
            'appeal_type': forms.Select(attrs={'class': 'form-select'}),
            'statement':   forms.Textarea(attrs={
                'class': 'form-control', 'rows': 5,
                'placeholder': 'State the grounds for your appeal clearly. '
                               'Include the result you received and why you believe it should be reviewed.'
            }),
        }

    def __init__(self, student, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit subjects to those the student is enrolled in
        from apps.academics.models import Subject
        from apps.exams.models import ExamResult
        self.student = student
        result_subject_ids = ExamResult.objects.filter(
            student=student
        ).values_list('subject_id', flat=True).distinct()
        self.fields['subject'].queryset = Subject.objects.filter(id__in=result_subject_ids)
        # Limit to recent terms (last 4)
        from apps.academics.models import Term
        self.fields['term'].queryset = Term.objects.order_by('-start_date')[:4]


class ProgramChangeRequestForm(forms.ModelForm):
    """Student applies to change programme or class stream."""

    class Meta:
        model  = ProgramChangeRequest
        fields = ['requested_class', 'reason', 'supporting_document']
        widgets = {
            'requested_class': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Explain why you would like to change your programme or stream.'
            }),
            'supporting_document': forms.HiddenInput(),  # populated by JS upload widget
        }

    def __init__(self, student, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.students.models import ClassRoom
        # Exclude student's current class
        self.fields['requested_class'].queryset = ClassRoom.objects.exclude(
            id=student.current_class.id if student.current_class else None
        ).order_by('level', 'stream')


class LeaveOfAbsenceRequestForm(forms.ModelForm):
    """Student applies for a leave of absence / deferment."""

    class Meta:
        model  = LeaveOfAbsenceRequest
        fields = ['leave_type', 'from_term', 'expected_return_term', 'reason', 'supporting_document']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'from_term':  forms.Select(attrs={'class': 'form-select'}),
            'expected_return_term': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Provide details about your situation and the period you need leave for.'
            }),
            'supporting_document': forms.HiddenInput(),
        }
        labels = {
            'from_term':            'Leave Starting From Term',
            'expected_return_term': 'Expected Return Term (optional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.academics.models import Term
        upcoming = Term.objects.filter(
            start_date__gte=__import__('django.utils.timezone', fromlist=['now']).now().date()
        ).order_by('start_date')
        self.fields['from_term'].queryset = upcoming
        self.fields['expected_return_term'].queryset = upcoming
        self.fields['expected_return_term'].required = False


class ProfileUpdateForm(forms.Form):
    """Student can update their contact information and notification preferences."""
    phone        = forms.CharField(max_length=20, required=False, label='Phone Number',
                                   widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}))
    email        = forms.EmailField(required=False, label='Email Address',
                                    widget=forms.EmailInput(attrs={'class': 'form-control form-control-sm'}))
    notify_sms   = forms.BooleanField(required=False, label='Receive SMS notifications',
                                      widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    notify_email = forms.BooleanField(required=False, label='Receive email notifications',
                                      widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    notify_push  = forms.BooleanField(required=False, label='Receive push notifications',
                                      widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))


class PasswordChangeForm(forms.Form):
    """Simple student password change form."""
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='Current Password'
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='New Password',
        min_length=8
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='Confirm New Password'
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('new_password') != cleaned.get('confirm_password'):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned


class ExcuseAbsenceForm(forms.Form):
    """Student (or parent) submits an absence excuse note."""
    date       = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    reason     = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label='Reason for Absence'
    )
    attachment = forms.FileField(required=False, label='Supporting Document (optional)',
                                 widget=forms.FileInput(attrs={'class': 'form-control'}))
