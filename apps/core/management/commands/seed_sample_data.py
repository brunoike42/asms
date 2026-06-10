"""
Management command: seed_sample_data
Populates the pilot school with realistic Ugandan student data.
Run: python manage.py seed_sample_data
"""
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.models import Tenant, AcademicYear, Term
from apps.accounts.models import User
from apps.students.models import Student, ClassRoom, ClassLevel, Enrollment, Guardian
from apps.finance.models import FeeCategory, FeeStructure, FeeInvoice, FeeInvoiceItem, Payment
from apps.attendance.models import AttendanceRecord, AttendanceSummary

# ── Ugandan name lists ──────────────────────────────────────────
MALE_FIRST = ['Kato', 'Ssali', 'Walugembe', 'Mukasa', 'Ssebuliba', 'Kaggwa', 'Bbosa',
              'Nsereko', 'Kayiira', 'Musisi', 'Ivan', 'Brian', 'Emmanuel', 'Joseph', 'David']
FEMALE_FIRST = ['Nakato', 'Nantongo', 'Namutebi', 'Nalwoga', 'Namugga', 'Nabirye', 'Namukasa',
                'Nassali', 'Grace', 'Immaculate', 'Patricia', 'Esther', 'Sarah', 'Flavia', 'Rita']
LAST_NAMES = ['Ssekandi', 'Mugisha', 'Tumwine', 'Ochieng', 'Akello', 'Namutebi', 'Wasswa',
              'Kizito', 'Lubega', 'Byamukama', 'Mwesige', 'Ssebunya', 'Kagawa', 'Nakimuli',
              'Ssempala', 'Kirunda', 'Namuli', 'Kawuma', 'Ntambi', 'Sembatya']
DISTRICTS = ['Kampala', 'Wakiso', 'Mukono', 'Jinja', 'Mbarara', 'Gulu', 'Lira', 'Mbale',
             'Fort Portal', 'Masaka', 'Arua', 'Soroti']
GUARDIAN_OCCUPATIONS = ['Teacher', 'Trader', 'Farmer', 'Civil Servant', 'Business Person',
                        'Driver', 'Engineer', 'Nurse', 'Tailor', 'Mechanic']


class Command(BaseCommand):
    help = 'Seeds realistic sample data for the ASMS pilot school'

    def add_arguments(self, parser):
        parser.add_argument('--students', type=int, default=45,
                            help='Number of students to create (default: 45)')
        parser.add_argument('--clear', action='store_true',
                            help='Clear existing student/finance data first')

    def handle(self, *args, **options):
        tenant = Tenant.objects.first()
        if not tenant:
            self.stderr.write('No tenant found. Run the server and check seed data.')
            return

        if options['clear']:
            Student.objects.filter(tenant=tenant).delete()
            FeeCategory.objects.filter(tenant=tenant).delete()
            self.stdout.write('Cleared existing data.')

        self.stdout.write(f'Seeding data for: {tenant.name}')

        ay = AcademicYear.objects.filter(tenant=tenant, is_current=True).first()
        term = Term.objects.filter(tenant=tenant, is_current=True).first()
        classrooms = list(ClassRoom.objects.filter(tenant=tenant).select_related('level'))

        if not classrooms:
            self.stderr.write('No classrooms found. Create classrooms first.')
            return

        # ── 1. Fee Categories & Structure ──────────────────────────
        self.stdout.write('Creating fee categories...')
        cats = {}
        for name, order in [('Tuition Fee', 1), ('Activity Fee', 2),
                              ('Library Fee', 3), ('Examination Fee', 4)]:
            cat, _ = FeeCategory.objects.get_or_create(
                tenant=tenant, name=name, defaults={'order': order}
            )
            cats[name] = cat

        for classroom in classrooms:
            level = classroom.level
            for cat_name, amount in [
                ('Tuition Fee', 380000), ('Activity Fee', 70000),
                ('Library Fee', 20000), ('Examination Fee', 30000)
            ]:
                FeeStructure.objects.get_or_create(
                    tenant=tenant, class_level=level,
                    term=term, category=cats[cat_name],
                    defaults={'amount': amount}
                )

        # ── 2. Students ────────────────────────────────────────────
        n = options['students']
        self.stdout.write(f'Creating {n} students...')
        created = 0
        existing_count = Student.objects.filter(tenant=tenant).count()

        for i in range(n):
            gender = random.choice(['M', 'F'])
            first  = random.choice(MALE_FIRST if gender == 'M' else FEMALE_FIRST)
            last   = random.choice(LAST_NAMES)
            dob    = date.today() - timedelta(days=random.randint(4380, 6570))  # 12–18 years
            classroom = random.choice(classrooms)
            sid = f'{tenant.slug.upper()[:3]}{existing_count + i + 1:04d}'

            student = Student.objects.create(
                tenant=tenant,
                student_id=sid,
                first_name=first,
                last_name=last,
                date_of_birth=dob,
                gender=gender,
                nationality='Ugandan',
                home_district=random.choice(DISTRICTS),
                has_disability=random.random() < 0.03,
                is_orphan=random.random() < 0.08,
                receives_bursary=random.random() < 0.10,
                blood_group=random.choice(['A+', 'B+', 'O+', 'AB+', 'A-', 'O-']),
                status='active',
                admission_date=date(2025, 2, 3),
            )

            # Enrollment
            Enrollment.objects.create(
                tenant=tenant, student=student,
                classroom=classroom, academic_year=ay,
                is_active=True
            )

            # Guardian
            g_gender = random.choice(['M', 'F'])
            g_first  = random.choice(MALE_FIRST if g_gender == 'M' else FEMALE_FIRST)
            g_last   = last  # same surname
            phone    = f'+25670{random.randint(1000000, 9999999)}'

            Guardian.objects.create(
                tenant=tenant, student=student,
                first_name=g_first, last_name=g_last,
                relationship=random.choice(['father', 'mother', 'guardian']),
                phone_primary=phone,
                occupation=random.choice(GUARDIAN_OCCUPATIONS),
                is_primary=True, is_fee_payer=True, receives_sms=True,
            )

            # Fee Invoice
            total = 500000  # UGX 500,000 per term
            paid  = random.choice([0, 100000, 250000, 380000, 500000])
            inv_status = 'paid' if paid >= total else ('partial' if paid > 0 else 'issued')
            inv = FeeInvoice.objects.create(
                tenant=tenant, student=student,
                term=term, academic_year=ay,
                issued_date=date(2025, 2, 3),
                due_date=date(2025, 3, 7),
                total_amount=total,
                amount_paid=paid,
                status=inv_status,
                issued_by=User.objects.filter(tenant=tenant, role='accountant').first()
                          or User.objects.filter(tenant=tenant, role='school_admin').first(),
            )
            # Line items
            FeeInvoiceItem.objects.create(
                invoice=inv, category=cats['Tuition Fee'],
                description='Tuition Fee — Term 1 2025', amount=380000
            )
            FeeInvoiceItem.objects.create(
                invoice=inv, category=cats['Activity Fee'],
                description='Activity Fee — Term 1 2025', amount=70000
            )
            FeeInvoiceItem.objects.create(
                invoice=inv, category=cats['Library Fee'],
                description='Library Fee — Term 1 2025', amount=20000
            )
            FeeInvoiceItem.objects.create(
                invoice=inv, category=cats['Examination Fee'],
                description='Examination Fee — Term 1 2025', amount=30000
            )
            if paid > 0:
                Payment.objects.create(
                    tenant=tenant, invoice=inv, student=student, term=term,
                    amount=paid, method=random.choice(['cash', 'mtn_momo', 'bank', 'airtel']),
                    payment_date=date(2025, 2, random.randint(3, 28)),
                    recorded_by=User.objects.filter(tenant=tenant, role='school_admin').first(),
                )

            # Attendance (last 14 school days)
            for day_offset in range(14):
                att_date = date.today() - timedelta(days=day_offset)
                if att_date.weekday() < 5:  # weekdays only
                    rand = random.random()
                    status = 'P' if rand > 0.12 else ('A' if rand > 0.05 else 'L')
                    AttendanceRecord.objects.get_or_create(
                        tenant=tenant, student=student, date=att_date,
                        defaults={
                            'classroom': classroom,
                            'status': status,
                            'marked_by': User.objects.filter(tenant=tenant, role='teacher').first(),
                        }
                    )
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Done! Created:\n'
            f'   {created} students\n'
            f'   {created} enrollments\n'
            f'   {created} guardians\n'
            f'   {created} fee invoices\n'
            f'   14 days of attendance per student\n'
            f'\nYou can now log in and see real data.'
        ))
