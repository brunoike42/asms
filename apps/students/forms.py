from django import forms
from .models import Student, Guardian, ClassRoom, ClassLevel, Enrollment


class StudentForm(forms.ModelForm):
    class Meta:
        model  = Student
        fields = [
            'first_name', 'middle_name', 'last_name', 'preferred_name',
            'date_of_birth', 'gender', 'nationality', 'religion',
            'home_district', 'home_village',
            'nsin', 'birth_cert_number',
            'has_disability', 'disability_type',
            'is_orphan', 'orphan_type', 'is_refugee', 'receives_bursary',
            'blood_group', 'allergies', 'medical_notes',
            'student_phone', 'student_email',
            'photo', 'status', 'admission_date',
        ]
        widgets = {
            'first_name':      forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name':     forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':       forms.TextInput(attrs={'class': 'form-control'}),
            'preferred_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth':   forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender':          forms.Select(attrs={'class': 'form-select'}),
            'nationality':     forms.TextInput(attrs={'class': 'form-control'}),
            'religion':        forms.Select(attrs={'class': 'form-select'}),
            'home_district':   forms.TextInput(attrs={'class': 'form-control'}),
            'home_village':    forms.TextInput(attrs={'class': 'form-control'}),
            'nsin':            forms.TextInput(attrs={'class': 'form-control'}),
            'birth_cert_number': forms.TextInput(attrs={'class': 'form-control'}),
            'disability_type': forms.TextInput(attrs={'class': 'form-control'}),
            'orphan_type':     forms.Select(attrs={'class': 'form-select'}),
            'blood_group':     forms.Select(attrs={'class': 'form-select'}),
            'allergies':       forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'medical_notes':   forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'student_phone':   forms.TextInput(attrs={'class': 'form-control'}),
            'student_email':   forms.EmailInput(attrs={'class': 'form-control'}),
            'status':          forms.Select(attrs={'class': 'form-select'}),
            'admission_date':  forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class GuardianForm(forms.ModelForm):
    class Meta:
        model  = Guardian
        fields = [
            'first_name', 'last_name', 'relationship',
            'phone_primary', 'phone_secondary', 'email',
            'occupation', 'national_id',
            'is_primary', 'is_fee_payer',
            'receives_sms', 'receives_reports',
        ]
        widgets = {
            'first_name':       forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':        forms.TextInput(attrs={'class': 'form-control'}),
            'relationship':     forms.Select(attrs={'class': 'form-select'}),
            'phone_primary':    forms.TextInput(attrs={'class': 'form-control'}),
            'phone_secondary':  forms.TextInput(attrs={'class': 'form-control'}),
            'email':            forms.EmailInput(attrs={'class': 'form-control'}),
            'occupation':       forms.TextInput(attrs={'class': 'form-control'}),
            'national_id':      forms.TextInput(attrs={'class': 'form-control'}),
        }


class ClassRoomForm(forms.ModelForm):
    class Meta:
        model  = ClassRoom
        fields = ['level', 'stream', 'academic_year', 'class_teacher', 'capacity']
        widgets = {
            'level':        forms.Select(attrs={'class': 'form-select'}),
            'stream':       forms.TextInput(attrs={'class': 'form-control'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'class_teacher': forms.Select(attrs={'class': 'form-select'}),
            'capacity':     forms.NumberInput(attrs={'class': 'form-control'}),
        }


class EnrollmentForm(forms.ModelForm):
    class Meta:
        model  = Enrollment
        fields = ['classroom', 'academic_year', 'is_repeating', 'notes']
        widgets = {
            'classroom':    forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'notes':        forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
