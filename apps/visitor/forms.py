"""
ASMS Visitor Management Module — Forms
"""
from django import forms
from django.contrib.auth import get_user_model
from apps.students.models import Student
from .models import Visitor, ExpectedVisitor, VisitorLog, VisitorWatchlistEntry

User = get_user_model()


class VisitorCheckInForm(forms.Form):
    """
    Full check-in form for a visitor not on file (unknown/new visitor path).
    View creates BOTH a Visitor identity record and the VisitorLog entry from this.
    """
    full_name             = forms.CharField(max_length=200)
    id_type                = forms.ChoiceField(choices=Visitor.IDTypeChoices.choices,
                                                initial=Visitor.IDTypeChoices.NIN)
    id_number              = forms.CharField(max_length=50, required=False)
    phone                  = forms.CharField(max_length=20, required=False)
    photo                  = forms.ImageField(required=False)

    purpose                = forms.ChoiceField(choices=VisitorLog.PurposeChoices.choices)
    host                   = forms.ModelChoiceField(queryset=User.objects.none(), required=False)
    student                = forms.ModelChoiceField(queryset=Student.objects.none(), required=False)
    items_carried          = forms.CharField(max_length=255, required=False)
    vehicle_registration   = forms.CharField(max_length=20, required=False)
    notes                  = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        # host not filtered by tenant — accounts.User's tenant relationship
        # isn't confirmed here; verify and narrow this if User is tenant-scoped.
        self.fields['host'].queryset = User.objects.all()
        if tenant is not None:
            self.fields['student'].queryset = Student.objects.filter(tenant=tenant)


class KnownVisitorCheckInForm(forms.ModelForm):
    """Short check-in form when the visitor is already on file (via visitor_lookup)."""
    class Meta:
        model = VisitorLog
        fields = ['purpose', 'host', 'student', 'items_carried', 'vehicle_registration', 'notes']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['host'].queryset = User.objects.all()
        if tenant is not None:
            self.fields['student'].queryset = Student.objects.filter(tenant=tenant)


class ExpectedVisitorForm(forms.ModelForm):
    class Meta:
        model = ExpectedVisitor
        fields = [
            'visitor_name', 'visitor_phone', 'visitor_id_number',
            'expected_date', 'expected_time_from', 'expected_time_to',
            'purpose', 'student', 'notes',
        ]
        widgets = {
            'expected_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_time_from': forms.TimeInput(attrs={'type': 'time'}),
            'expected_time_to': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields['student'].queryset = Student.objects.filter(tenant=tenant)


class VisitorWatchlistEntryForm(forms.ModelForm):
    class Meta:
        model = VisitorWatchlistEntry
        fields = ['full_name', 'phone', 'reason', 'reason_detail', 'related_student', 'is_active']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields['related_student'].queryset = Student.objects.filter(tenant=tenant)