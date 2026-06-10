"""
Run from your Phase 1 project root (where manage.py is).
Reads your actual core/models.py and patches all Phase 2 apps to match.

Usage:
  cd E:\DJANGO\ASMS\asms
  python fix_imports.py
"""
import os, re, sys

ROOT = os.getcwd()
APPS_DIR = os.path.join(ROOT, 'apps')
NEW_APPS = ['academics', 'exams', 'staff_hr', 'library', 'lms', 'assignments']

print("\n═══ ASMS Phase 2 — Import Compatibility Fix ═══\n")

# ── 1. Read what Phase 1 core/models.py actually exports ────────────────
core_models_path = os.path.join(APPS_DIR, 'core', 'models.py')
if not os.path.exists(core_models_path):
    print(f"✗ Cannot find: {core_models_path}")
    sys.exit(1)

with open(core_models_path, encoding='utf-8') as f:
    core_content = f.read()

# Find all class names defined in core/models.py
defined_classes = re.findall(r'^class\s+(\w+)', core_content, re.MULTILINE)
# Find all functions defined
defined_funcs = re.findall(r'^def\s+(\w+)', core_content, re.MULTILINE)
defined_all = set(defined_classes + defined_funcs)

print(f"✓ Read core/models.py — found: {', '.join(sorted(defined_all))}")

# ── 2. Determine what's missing that Phase 2 needs ──────────────────────
NEEDS_TENANT_MANAGER = 'TenantManager' not in defined_all
NEEDS_GET_TENANT     = 'get_current_tenant' not in defined_all
NEEDS_SET_TENANT     = 'set_current_tenant' not in defined_all
NEEDS_ACADEMIC_YEAR  = 'AcademicYear' not in defined_all
NEEDS_TERM           = 'Term' not in defined_all

print(f"\n  TenantManager      : {'✓ exists' if not NEEDS_TENANT_MANAGER else '✗ MISSING'}")
print(f"  get_current_tenant : {'✓ exists' if not NEEDS_GET_TENANT else '✗ MISSING'}")
print(f"  set_current_tenant : {'✓ exists' if not NEEDS_SET_TENANT else '✗ MISSING'}")
print(f"  AcademicYear       : {'✓ exists' if not NEEDS_ACADEMIC_YEAR else '✗ MISSING'}")
print(f"  Term               : {'✓ exists' if not NEEDS_TERM else '✗ MISSING'}")

# ── 3. Append missing pieces to core/models.py ──────────────────────────
additions = []

if NEEDS_GET_TENANT or NEEDS_SET_TENANT or NEEDS_TENANT_MANAGER:
    additions.append("""
# ── Phase 2 compatibility additions ─────────────────────────────────────
import threading as _threading

_thread_locals = _threading.local()

def get_current_tenant():
    return getattr(_thread_locals, 'tenant', None)

def set_current_tenant(tenant):
    _thread_locals.tenant = tenant
""")

if NEEDS_TENANT_MANAGER:
    additions.append("""
class TenantManager(models.Manager):
    \"\"\"Automatically filters querysets by the current request tenant.\"\"\"
    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant:
            return qs.filter(tenant=tenant)
        return qs
""")

if NEEDS_ACADEMIC_YEAR:
    additions.append("""
class AcademicYear(models.Model):
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicYear.all_objects.filter(tenant=self.tenant, is_current=True).update(is_current=False)
        super().save(*args, **kwargs)
""")

if NEEDS_TERM:
    additions.append("""
class Term(models.Model):
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='terms')
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        return f"{self.academic_year.name} — {self.name}"
""")

if additions:
    # Make sure 'models' is imported in core/models.py
    if 'from django.db import models' not in core_content and 'import models' not in core_content:
        additions.insert(0, 'from django.db import models\n')

    with open(core_models_path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(additions))
    print(f"\n✓ Appended {len(additions)} missing pieces to apps/core/models.py")
else:
    print("\n✓ core/models.py already has everything needed")

# ── 4. Now scan Phase 2 apps and fix any remaining bad imports ───────────
# Build the actual import map: what each Phase 2 app needs vs what exists

# After our additions, rebuild the known set
with open(core_models_path, encoding='utf-8') as f:
    core_content_updated = f.read()

# Find Tenant model name (Phase 1 might call it School, Tenant, Organisation...)
tenant_class_candidates = re.findall(r'class\s+(\w+)\s*\(models\.Model\)', core_content_updated)
print(f"\n  Models in core: {tenant_class_candidates}")

# ── 5. Fix each Phase 2 app's files ─────────────────────────────────────
def patch_file(filepath):
    if not os.path.exists(filepath):
        return False
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    original = content

    # Ensure all_objects manager exists where needed
    # Fix: if a model uses TenantManager but no all_objects, add a note
    # (We just ensure imports are correct here)

    # Remove duplicate 'apps.' prefixes introduced by previous fix runs
    content = re.sub(r'\bapps\.apps\.', 'apps.', content)

    # Fix any import of threading (already added to core)
    content = re.sub(r'^import threading\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^_thread_locals\s*=.*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^def get_current_tenant.*?^$', '', content, flags=re.MULTILINE|re.DOTALL)
    content = re.sub(r'^def set_current_tenant.*?^$', '', content, flags=re.MULTILINE|re.DOTALL)
    content = re.sub(r'^class TenantManager.*?(?=^class|\Z)', '', content, flags=re.MULTILINE|re.DOTALL)

    # Clean up blank lines
    content = re.sub(r'\n{4,}', '\n\n', content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

patched = 0
for app in NEW_APPS:
    app_dir = os.path.join(APPS_DIR, app)
    for fname in ['models.py', 'views.py', 'admin.py', 'urls.py']:
        fpath = os.path.join(app_dir, fname)
        if patch_file(fpath):
            patched += 1
            print(f"✓ Cleaned: apps/{app}/{fname}")

# ── 6. Check if Tenant model needs 'all_objects' manager ────────────────
# Phase 2 uses Model.all_objects — check if Phase 1 models have it
all_objects_in_core = 'all_objects' in core_content_updated
if not all_objects_in_core:
    print("\n⚠ Phase 1 models may not have 'all_objects = models.Manager()'")
    print("  The new apps use .all_objects for cross-tenant queries.")
    print("  Add this to any Phase 1 model that the new apps reference:")
    print("    all_objects = models.Manager()")

print(f"\n✓ Patched {patched} files")
print("\n═══════════════════════════════════════════════════════════")
print("  NOW RUN:")
print("    python manage.py makemigrations")
print("    python manage.py migrate")
print("═══════════════════════════════════════════════════════════\n")