# ASMS v3.0 — Advanced School Management System

**Multi-Institutional SaaS Platform | Django 4.2 + PostgreSQL | Africa-first**

---

## Phase 1 MVP — What Is Built

| Module | Status | Description |
|---|---|---|
| Multi-Tenant Architecture | ✅ Done | Tenant model, middleware, row-level isolation |
| User Auth & 12 Roles | ✅ Done | Custom User model, login, role-based access |
| Student Management | ✅ Done | CRUD, EMIS fields, enrollment, guardians |
| Class & Stream Management | ✅ Done | ClassLevel, ClassRoom, academic year |
| Admissions Pipeline | ✅ Done | Application → shortlist → accept → enroll |
| Daily Attendance | ✅ Done | Mark register, SMS on absence, 30-day report |
| Fee Invoicing | ✅ Done | Structure, invoices, manual payments, receipts |
| SMS Communication | ✅ Done | Africa's Talking integration (dev mode console) |
| Admin Dashboard | ✅ Done | Bootstrap 5 sidebar, stats cards, quick actions |
| Sample Data Seeder | ✅ Done | 45 Ugandan students with attendance + finance |

---

## Quick Start

### 1. Clone and set up environment

```bash
cd asms/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY and DATABASE_URL
```

### 3. Run migrations

```bash
python manage.py migrate
```

### 4. Create pilot school and admin users

```bash
python manage.py shell
# Then paste the seed script from docs/seed_tenant.py
# OR run the sample data command:
python manage.py seed_sample_data --students 45
```

### 5. Start the development server

```bash
python manage.py runserver
```

Visit: **http://localhost:8000/**

---

## Login Credentials (Development)

| Role | Email | Password |
|---|---|---|
| Platform Admin | admin@asms.app | ASMSadmin2025! |
| School Admin | admin@stamarys.ac.ug | school2025! |
| Principal | principal@stamarys.ac.ug | school2025! |
| Teacher | teacher@stamarys.ac.ug | school2025! |

---

## Project Structure

```
asms/
├── apps/
│   ├── core/           # Tenant, AcademicYear, Term, middleware, dashboard
│   ├── accounts/       # Custom User model, 12 roles, auth views
│   ├── students/       # Student, ClassRoom, Enrollment, Guardian
│   ├── academics/      # Subjects, timetable (Phase 2)
│   ├── admissions/     # Application pipeline
│   ├── attendance/     # Daily register, SMS triggers, summaries
│   ├── finance/        # FeeCategory, FeeStructure, Invoice, Payment
│   └── communication/  # SMS service, Announcements
├── config/
│   ├── settings.py     # Full settings (SQLite dev, PostgreSQL prod)
│   └── urls.py         # Root URL configuration
├── templates/          # All HTML templates (Bootstrap 5)
├── static/             # CSS, JS, images
├── requirements.txt
└── .env.example
```

---

## Multi-Tenant Architecture

Every model inherits `TenantModel`. The `TenantMiddleware` resolves a school
from the request subdomain and sets `request.tenant`. All QuerySets are
automatically scoped — no cross-tenant data leaks are possible.

```
stamarys.asms.app  →  Tenant(slug='stamarys')  →  all queries filtered
localhost:8000     →  first active Tenant (development mode)
```

---

## Key Design Decisions

**Why SQLite in development?**
Zero setup. Switch to PostgreSQL in production by setting `DATABASE_URL` in `.env`.

**Why Africa's Talking for SMS?**
Works across Uganda, Kenya, Tanzania, Ghana, Rwanda. In dev mode (`DEBUG=True`),
SMS is printed to console — no API key required to develop.

**Why custom User model (not `django.contrib.auth.User`)?**
We need email-based login and 12 distinct roles. Swapping later is painful —
always define `AUTH_USER_MODEL` before first migration.

**Why no REST API yet?**
Phase 1 is server-rendered (Django templates). REST API + React portal comes
in Phase 3 when the biometric devices and mobile PWA need it.

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Django secret key |
| `DATABASE_URL` | Production | PostgreSQL connection string |
| `AFRICASTALKING_API_KEY` | SMS | Africa's Talking API key |
| `AFRICASTALKING_USERNAME` | SMS | Username (use `sandbox` for testing) |
| `FLUTTERWAVE_SECRET_KEY` | Phase 3 | Payments — not needed in Phase 1 |
| `CLOUDINARY_URL` | Phase 3 | File storage — not needed in Phase 1 |

---

## Running Tests

```bash
python manage.py test apps.core apps.students apps.finance apps.attendance
```

---

## Deployment (Railway)

1. Push to GitHub
2. Create new Railway project → connect repo
3. Add PostgreSQL add-on
4. Set environment variables in Railway dashboard
5. Railway auto-deploys on every push to `main`

```bash
# Procfile (already included)
web: gunicorn config.wsgi --bind 0.0.0.0:$PORT
```

---

## What Comes Next — Phase 2

| Component | Description |
|---|---|
| Exams & Grades | Mark entry, ranking, report cards |
| LMS (built-in) | Lessons, quizzes, assignments |
| Staff & HR | Staff profiles, leave, payroll |
| Library | Catalogue, borrow/return, fines |
| Enhanced Timetable | Constraint-based solver (OR-Tools) |

---

## Version

**ASMS v3.0** — Adaptive Intelligence Edition  
Phase 1 MVP complete. Django 4.2 + SQLite (dev) / PostgreSQL (prod).  
See `ASMS_v3_Adaptive_Intelligence_Specification.pdf` for full platform spec.
