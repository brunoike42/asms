# Phase 6, Aspect 3 — Shared Curriculum

45 tests pass: 18 new for this app, 27 already-shipped ones re-run clean
after `apps/networks` was refactored underneath them. The adversarial
case that actually validates the design: School A diverges an unlocked
item, the network publishes v3, and School B advances to v3 while School
A stays frozen at v2 — not merged, not overwritten, not silently dropped.

## 1. `apps/networks/` changed — supersedes the last drop

If you already integrated the Aspect 1/2 zip, **replace `services.py` and
`permissions.py` wholesale** rather than diffing by hand — both changed:

- Added `user_administers_network(user, network)` — the one function
  `get_network_scope()`, the DRF permission class, and now
  `apps/curriculum` all call. Previously the staff-bypass rule was
  hand-copied in two places and had already drifted once; it can't drift
  a third time if there's only one copy.
- `IsNetworkAdminOrPlatformStaff.has_object_permission` now accepts
  anything with a `.network` FK, not just a `Network` instance itself —
  that's what lets `CurriculumResource` reuse it without a second
  permission class.

Nothing about the *behavior* of Aspects 1 or 2 changed — same 27 tests,
same assertions, all still passing. `models.py`, `views.py`, `tasks.py`,
`serializers.py`, `admin.py`, `urls.py`, and the migrations are unchanged
from the last drop.

## 2. New: `apps/curriculum/`

```
apps/curriculum/
├── models.py       CurriculumResource, CurriculumAdoption, CurriculumPublishLog
├── services.py       publish_resource() / sync_resource_to_network() /
│                        adopt_resource() / diverge_adoption() — the
│                        actual Blueprint-style sync logic
├── permissions.py       user_belongs_to_tenant() — the one new check
│                          this app needed (school-level, not network-level)
├── serializers.py          resource + adoption-status serializers
├── views.py                   5 endpoints — table below
├── urls.py                       mounts under /api/v1/curriculum/
├── admin.py                        all three models registered
├── tests/                            18 tests across 2 files
└── migrations/                         0001_initial
```

Add to `INSTALLED_APPS` and mount the URLs:

```python
INSTALLED_APPS = [..., "apps.networks", "apps.curriculum"]

# root urlconf
path("api/v1/curriculum/", include("apps.curriculum.urls")),
```

## 3. Endpoints

| Method | Path | Who |
|---|---|---|
| GET | `/api/v1/curriculum/resources/` | Any authenticated user — staff see all, others see their network's resources plus baseline (no-network) content |
| POST | `/api/v1/curriculum/resources/` | Network admin for their network; platform staff for baseline content |
| POST | `/api/v1/curriculum/resources/{id}/publish/` | Network admin, or staff for baseline — bumps version, syncs, logs |
| GET | `/api/v1/curriculum/resources/{id}/adoptions/` | Network admin, or staff for baseline — **the adoption endpoint** |
| POST | `/api/v1/curriculum/resources/{id}/adopt/` | Staff *at the school* being enrolled |
| POST | `/api/v1/curriculum/adoptions/{id}/diverge/` | Staff at the adoption's own school only — 403 if the resource is locked |

## 4. The one new actor type, and the one new stub it needed

Everything in Aspects 1–2 was a Network Admin acting across schools.
Diverging is the opposite: a school-level user acting on their own
school's copy. `user_belongs_to_tenant()` needed something to check
against, so `apps/core/models.py` in this sandbox now also has:

```python
class Staff(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, default="TEACHER")
```

per Appendix C's `staff_id, tenant_id, user_id, role, department,
employment_status`. If your real Staff model (or role/membership system)
looks different, the fix is local to `user_belongs_to_tenant()` in
`apps/curriculum/permissions.py` — nothing else references it.

## 5. Design decisions worth knowing about, not just field names

- **`default_locked` is set once, by the network, at creation/publish —
  there's no endpoint for a school to lock/unlock anything.** That's
  deliberate, straight from Blueprint: the lock decision belongs to
  whoever owns the shared source, never the consumer.
- **Diverging is permanent for that adoption row.** Nothing re-locks it,
  nothing auto-resyncs it later. If you want a "reset to network version"
  action, that's a new, explicit endpoint to design — not built here,
  because silently resurrecting a school's overwritten local edit is
  exactly the failure mode this design exists to avoid.
- **`effective_from_date` delays the *sync*, not the *publish*.** The
  version number and PUBLISHED status change immediately; schools don't
  see it until the date arrives. This mirrors how NCDC's own curriculum
  changes roll out by cohort rather than applying retroactively —
  verify this is actually the behavior you want before relying on it,
  since "publish now, apply later" is a real product decision, not just
  a technical default.

## 6. Not built yet

- Same two `apps/core` patches as every prior drop: the `Tenant.network`
  FK and the `TenantModel.objects = TenantManager()` confirmation.
- `billing.Subscription` assumption, unchanged.
- `academics`/`finance` field-name assumptions from Aspect 2 — untouched,
  irrelevant to this aspect.
- A "reset to network version" action (see above).
- Curriculum content diffing/preview before a school commits to
  diverging — right now `/diverge/` takes new content and applies it in
  one step.
- Aspect 4 (EMIS export) and Aspect 5 (exam intelligence) — still just
  the seams: `curriculum_source` is there for EMIS to report against,
  nothing consumes it yet.
