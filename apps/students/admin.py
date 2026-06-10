from django.contrib import admin
from .models import Student, ClassLevel, ClassRoom, Enrollment, Guardian


@admin.register(ClassLevel)
class ClassLevelAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'category', 'order', 'tenant']
    list_filter  = ['category', 'tenant']


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'academic_year', 'class_teacher', 'capacity', 'student_count', 'tenant']
    list_filter  = ['academic_year', 'tenant']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display  = ['student_id', 'get_full_name', 'gender', 'status', 'admission_date', 'tenant']
    list_filter   = ['status', 'gender', 'tenant']
    search_fields = ['first_name', 'last_name', 'student_id', 'nsin']
    raw_id_fields = ['user']


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display  = ['student', 'classroom', 'academic_year', 'is_active']
    list_filter   = ['is_active', 'academic_year', 'tenant']


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display  = ['get_full_name', 'relationship', 'student', 'phone_primary', 'is_primary']
    list_filter   = ['relationship', 'is_primary', 'tenant']
    search_fields = ['first_name', 'last_name', 'phone_primary']
