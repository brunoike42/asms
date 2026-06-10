from django import forms
from .models import AdmissionApplication


class AdmissionApplicationForm(forms.ModelForm):
    class Meta:
        model  = AdmissionApplication
        fields = [
            'first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender', 'nationality',
            'applying_for_level', 'applying_for_year',
            'guardian_name', 'guardian_phone', 'guardian_email', 'guardian_relationship',
            'previous_school', 'previous_class', 'previous_school_results',
            'status', 'interview_date', 'decision_notes',
        ]
        widgets = {
            'first_name':        forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name':       forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':         forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth':     forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender':            forms.Select(attrs={'class': 'form-select'}),
            'nationality':       forms.TextInput(attrs={'class': 'form-control'}),
            'applying_for_level': forms.Select(attrs={'class': 'form-select'}),
            'applying_for_year': forms.Select(attrs={'class': 'form-select'}),
            'guardian_name':     forms.TextInput(attrs={'class': 'form-control'}),
            'guardian_phone':    forms.TextInput(attrs={'class': 'form-control'}),
            'guardian_email':    forms.EmailInput(attrs={'class': 'form-control'}),
            'guardian_relationship': forms.TextInput(attrs={'class': 'form-control'}),
            'previous_school':   forms.TextInput(attrs={'class': 'form-control'}),
            'previous_class':    forms.TextInput(attrs={'class': 'form-control'}),
            'previous_school_results': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status':            forms.Select(attrs={'class': 'form-select'}),
            'interview_date':    forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'decision_notes':    forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
