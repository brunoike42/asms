"""
ASMS Student Portal — Initial Migration
Phase 3

Run with: python manage.py migrate student_portal
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants',   '0001_initial'),
        ('students',  '0001_initial'),
        ('academics', '0001_initial'),
        ('staff',     '0001_initial'),
    ]

    operations = [

        # ── TermEnrollment ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='TermEnrollment',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('status',       models.CharField(choices=[
                                    ('new','New Student'),('continuing','Continuing Student'),
                                    ('retake','Completed with Retakes'),('deferral','Deferred / Dead Year'),
                                    ('completed','Programme Completed')
                                 ], default='continuing', max_length=20)),
                ('study_year',   models.PositiveSmallIntegerField()),
                ('enrolled_at',  models.DateTimeField(auto_now_add=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('is_confirmed', models.BooleanField(default=False)),
                ('notes',        models.TextField(blank=True)),
                ('tenant',       models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant', db_index=True)),
                ('student',      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='students.student')),
                ('term',         models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='academics.term')),
            ],
            options={'ordering': ['-term__start_date'], 'verbose_name': 'Term Enrollment'},
        ),
        migrations.AddConstraint(
            model_name='TermEnrollment',
            constraint=models.UniqueConstraint(fields=['tenant','student','term'], name='unique_student_term_enrollment'),
        ),

        # ── CourseUnitRegistration ───────────────────────────────────────────
        migrations.CreateModel(
            name='CourseUnitRegistration',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('paper_type',    models.CharField(choices=[
                                     ('normal','Normal Paper'),('retake','Retake'),
                                     ('supplementary','Supplementary'),('missed','Missed Paper'),
                                     ('elective','Elective Subject')
                                  ], default='normal', max_length=20)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('is_active',     models.BooleanField(default=True)),
                ('tenant',        models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant', db_index=True)),
                ('enrollment',    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_registrations', to='student_portal.termenrollment')),
                ('subject',       models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_registrations', to='academics.subject')),
            ],
            options={'ordering': ['subject__name'], 'verbose_name': 'Course Unit Registration'},
        ),
        migrations.AddConstraint(
            model_name='CourseUnitRegistration',
            constraint=models.UniqueConstraint(fields=['tenant','enrollment','subject'], name='unique_course_unit_registration'),
        ),

        # ── ExamPermit ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='ExamPermit',
            fields=[
                ('id',             models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('permit_number',  models.CharField(max_length=30, unique=True)),
                ('status',         models.CharField(choices=[
                                      ('pending','Pending'),('issued','Issued'),
                                      ('blocked','Blocked — Clearance Incomplete'),('revoked','Revoked')
                                   ], default='pending', max_length=10)),
                ('issued_at',      models.DateTimeField(blank=True, null=True)),
                ('blocked_reason', models.TextField(blank=True)),
                ('pdf_path',       models.CharField(blank=True, max_length=500)),
                ('tenant',         models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant', db_index=True)),
                ('enrollment',     models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='exam_permit', to='student_portal.termenrollment')),
            ],
            options={'ordering': ['-issued_at'], 'verbose_name': 'Exam Permit'},
        ),

        # ── ExamAppeal ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='ExamAppeal',
            fields=[
                ('id',               models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('appeal_type',      models.CharField(choices=[
                                        ('remark','Re-mark Request'),('clerical','Clerical Error'),
                                        ('missing','Missing Result'),('query','General Query')
                                     ], max_length=15)),
                ('status',           models.CharField(choices=[
                                        ('submitted','Submitted'),('acknowledged','Acknowledged'),
                                        ('under_review','Under Review'),('resolved','Resolved'),
                                        ('rejected','Rejected')
                                     ], default='submitted', max_length=15)),
                ('original_marks',   models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('statement',        models.TextField()),
                ('admin_response',   models.TextField(blank=True)),
                ('revised_marks',    models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('submitted_at',     models.DateTimeField(auto_now_add=True)),
                ('resolved_at',      models.DateTimeField(blank=True, null=True)),
                ('reference_number', models.CharField(blank=True, max_length=30, unique=True)),
                ('tenant',           models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant', db_index=True)),
                ('student',          models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_appeals', to='students.student')),
                ('term',             models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academics.term')),
                ('subject',          models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academics.subject')),
                ('resolved_by',      models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='staff.staff')),
            ],
            options={'ordering': ['-submitted_at'], 'verbose_name': 'Exam Appeal'},
        ),

        # ── ProgramChangeRequest ──────────────────────────────────────────────
        migrations.CreateModel(
            name='ProgramChangeRequest',
            fields=[
                ('id',                  models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('reason',              models.TextField()),
                ('supporting_document', models.CharField(blank=True, max_length=500)),
                ('status',              models.CharField(choices=[
                                           ('pending','Pending Review'),('approved','Approved'),('rejected','Rejected')
                                        ], default='pending', max_length=10)),
                ('admin_comment',       models.TextField(blank=True)),
                ('submitted_at',        models.DateTimeField(auto_now_add=True)),
                ('reviewed_at',         models.DateTimeField(blank=True, null=True)),
                ('tenant',              models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant', db_index=True)),
                ('student',             models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='program_changes', to='students.student')),
                ('current_class',       models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='change_from', to='academics.class')),
                ('requested_class',     models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='change_to', to='academics.class')),
                ('reviewed_by',         models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='staff.staff')),
            ],
            options={'ordering': ['-submitted_at'], 'verbose_name': 'Programme Change Request'},
        ),

        # ── LeaveOfAbsenceRequest ─────────────────────────────────────────────
        migrations.CreateModel(
            name='LeaveOfAbsenceRequest',
            fields=[
                ('id',                   models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('leave_type',           models.CharField(choices=[
                                            ('medical','Medical Leave'),('financial','Financial Hardship'),
                                            ('personal','Personal Reasons'),('bereavement','Bereavement'),
                                            ('official','Official / Scholarship'),('other','Other')
                                         ], max_length=15)),
                ('reason',               models.TextField()),
                ('supporting_document',  models.CharField(blank=True, max_length=500)),
                ('status',               models.CharField(choices=[
                                            ('pending','Pending'),('approved','Approved'),
                                            ('rejected','Rejected'),('reinstated','Reinstated')
                                         ], default='pending', max_length=12)),
                ('admin_comment',        models.TextField(blank=True)),
                ('submitted_at',         models.DateTimeField(auto_now_add=True)),
                ('reviewed_at',          models.DateTimeField(blank=True, null=True)),
                ('tenant',               models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant', db_index=True)),
                ('student',              models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leave_requests', to='students.student')),
                ('from_term',            models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='leave_from', to='academics.term')),
                ('expected_return_term', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='leave_return', to='academics.term')),
                ('reviewed_by',          models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='staff.staff')),
            ],
            options={'ordering': ['-submitted_at'], 'verbose_name': 'Leave of Absence Request'},
        ),

        # ── AcademicClearanceItem ─────────────────────────────────────────────
        migrations.CreateModel(
            name='AcademicClearanceItem',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name',        models.CharField(max_length=100)),
                ('department',  models.CharField(choices=[
                                   ('library','Library'),('finance','Finance / Accounts'),
                                   ('academics','Academic Registrar'),('sports','Sports / PE'),
                                   ('health','Health / Nurse'),('hostel','Hostel / Boarding'),
                                   ('it','ICT Department'),('custom','Other Department')
                                ], max_length=15)),
                ('description', models.TextField(blank=True)),
                ('is_active',   models.BooleanField(default=True)),
                ('order',       models.PositiveSmallIntegerField(default=0)),
                ('tenant',      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant', db_index=True)),
            ],
            options={'ordering': ['order', 'name']},
        ),

        # ── StudentClearance ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='StudentClearance',
            fields=[
                ('id',             models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('overall_status', models.CharField(choices=[
                                      ('in_progress','In Progress'),('cleared','Cleared'),('blocked','Blocked')
                                   ], default='in_progress', max_length=15)),
                ('requested_at',   models.DateTimeField(auto_now_add=True)),
                ('cleared_at',     models.DateTimeField(blank=True, null=True)),
                ('notes',          models.TextField(blank=True)),
                ('tenant',         models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant', db_index=True)),
                ('student',        models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clearances', to='students.student')),
                ('academic_year',  models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academics.academicyear')),
            ],
            options={'ordering': ['-academic_year__start_date']},
        ),
        migrations.AddConstraint(
            model_name='StudentClearance',
            constraint=models.UniqueConstraint(fields=['tenant','student','academic_year'], name='unique_student_clearance'),
        ),

        # ── StudentClearanceItemStatus ────────────────────────────────────────
        migrations.CreateModel(
            name='StudentClearanceItemStatus',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('status',     models.CharField(choices=[
                                  ('pending','Pending'),('cleared','Cleared'),
                                  ('blocked','Blocked'),('waived','Waived')
                               ], default='pending', max_length=10)),
                ('cleared_at', models.DateTimeField(blank=True, null=True)),
                ('remarks',    models.TextField(blank=True)),
                ('clearance',  models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='item_statuses', to='student_portal.studentclearance')),
                ('item',       models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='student_portal.academicclearanceitem')),
                ('cleared_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='staff.staff')),
            ],
            options={'ordering': ['item__order']},
        ),

        # ── AcademicCalendarEvent ─────────────────────────────────────────────
        migrations.CreateModel(
            name='AcademicCalendarEvent',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('title',        models.CharField(max_length=200)),
                ('event_type',   models.CharField(choices=[
                                    ('term_start','Term / Semester Start'),('term_end','Term / Semester End'),
                                    ('exam_period','Examination Period'),('registration','Registration Window'),
                                    ('fee_deadline','Fee Payment Deadline'),('holiday','Public Holiday / Break'),
                                    ('submission','Assignment / Project Deadline'),('graduation','Graduation / Prize Day'),
                                    ('sports','Sports Day / Competition'),('open_day','Open Day / Visiting Day'),
                                    ('announcement','General School Event')
                                 ], max_length=20)),
                ('description',  models.TextField(blank=True)),
                ('start_date',   models.DateField()),
                ('end_date',     models.DateField(blank=True, null=True)),
                ('audience',     models.CharField(choices=[
                                    ('all','All Students'),('primary','Primary Only'),
                                    ('secondary','Secondary Only'),('tertiary','Tertiary Only'),('class','Specific Class/Year')
                                 ], default='all', max_length=15)),
                ('is_published', models.BooleanField(default=True)),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('tenant',       models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant', db_index=True)),
                ('academic_year', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='academics.academicyear')),
                ('term',         models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='academics.term')),
                ('created_by',   models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='staff.staff')),
            ],
            options={'ordering': ['start_date'], 'verbose_name': 'Academic Calendar Event'},
        ),

        # ── PortalNotification ────────────────────────────────────────────────
        migrations.CreateModel(
            name='PortalNotification',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('category',   models.CharField(choices=[
                                  ('academic','Academic'),('finance','Finance'),('attendance','Attendance'),
                                  ('discipline','Discipline'),('welfare','Welfare'),('document','Document Ready'),
                                  ('system','System'),('general','General')
                               ], default='general', max_length=15)),
                ('title',      models.CharField(max_length=200)),
                ('body',       models.TextField()),
                ('action_url', models.CharField(blank=True, max_length=300)),
                ('is_read',    models.BooleanField(default=False)),
                ('read_at',    models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant',     models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant', db_index=True)),
                ('student',    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='portal_notifications', to='students.student')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
