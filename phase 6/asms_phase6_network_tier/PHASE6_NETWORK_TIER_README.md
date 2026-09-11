# Phase 6, Aspect 1 — Network / Group Tier

27 tests pass against a throwaway Django 4.2.30 + DRF 3.18 + Celery 5.6
sandbox: models, the audited service, permissions, views, and now the
nightly rollup task. The two adversarial test cases matter most — School A
and School B are sized 3:1 apart with deliberately far-apart rates (50% vs
100% fee collection), specifically so a naive "average the two schools'
rates" bug would fail the test instead of silently shipping. It didn't —
both landed on the correctly weighted figure.

Still true from before: this proves the app is internally correct, not
that it matches your real `apps/core`, `apps/billing`, `apps/academics`,
or `apps/finance`, because I don't have those files. See sections 3 and 4.

## 1. Drop-in part

```
apps/networks/
├── models.py        Network, NetworkAdminRole, NetworkMembership,
│                     NetworkQueryLog, NetworkDailyMetric
├── services.py        get_network_scope() / network_scoped_queryset()
│                        — now with the is_staff bypass fixed at the
│                        service layer too (see section 2)
├── tasks.py             compute_network_rollups — the nightly job
├── permissions.py         IsNetworkAdminOrPlatformStaff
├── serializers.py           Network, school, admin-role, query-log,
│                              daily-metric serializers
├── views.py                    7 endpoints — table below
├── urls.py                       mounts under /api/v1/networks/
├── api_utils.py                    Appendix E response envelope
├── admin.py                          all five models registered
├── tests/                              27 tests across 3 files
└── migrations/                           0001 → 0003
```

Copy the folder in. `INSTALLED_APPS` needs `"rest_framework"` and
`"apps.networks"` if they aren't already there. Add
`compute_network_rollups` to your existing Celery Beat schedule next to
`extract_tenant_patterns` (Appendix H):

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    ...,
    "compute-network-rollups": {
        "task": "apps.networks.tasks.compute_network_rollups",
        "schedule": crontab(hour=0, minute=30),  # after extract_tenant_patterns
    },
}
```

## 2. A real bug this pass caught and fixed

`get_network_scope()`'s platform-staff bypass previously only existed in
`permissions.py` at the view layer — the service function itself required
a `NetworkAdminRole` row with no exception. That's not just an
inconsistency: it meant the rollup task had no legitimate way to read
across a network's schools without either (a) manually granting itself an
admin role on every network, which is exactly the kind of silent
self-authorization the audit system exists to catch, or (b) a second,
divergent permission path. Fixed by moving the `is_staff` bypass into
`get_network_scope()` itself, so there's one rule, enforced once, and the
rollup task authenticates as a real `is_staff`, `is_active=False` system
account rather than bypassing the check.

## 3. Endpoints (new row is `/rollups/`)

| Method | Path | Who |
|---|---|---|
| GET | `/api/v1/networks/networks/` | Any authenticated user — staff see all, others see only networks they administer |
| POST | `/api/v1/networks/networks/` | Platform staff only |
| GET | `/api/v1/networks/networks/{id}/` | Network Admin of that network, or staff |
| GET/POST | `/api/v1/networks/networks/{id}/schools/` | Network Admin, or staff |
| DELETE | `/api/v1/networks/networks/{id}/schools/{tenant_id}/` | Network Admin, or staff |
| GET/POST | `/api/v1/networks/networks/{id}/admins/` | Network Admin, or staff |
| GET | `/api/v1/networks/networks/{id}/logs/` | Network Admin, or staff |
| GET | `/api/v1/networks/networks/{id}/rollups/` | Network Admin, or staff — `?metric=&date_from=&date_to=&scope=network\|schools` |

`scope=network` returns only the network-wide total rows, `scope=schools`
only the per-school breakdown, omitted returns both — the Stripe Connect
"Aggregated report vs. Single report" toggle from the benchmark, as a
query parameter.

## 4. The patches still needed — same two as before, nothing new

**`apps/core/models.py`** — add the `network` FK to `Tenant`, confirm
`TenantModel` sets `objects = TenantManager()`. Unchanged from the last
drop.

**Field-name assumptions, now covering four models instead of two:**
`billing.Subscription`, `core.Tenant` (as before), plus `tasks.py` now
assumes `academics.Student` (`tenant`, `status`), `academics.AttendanceRecord`
(`tenant`, `student`, `date`, `status` with a `"PRESENT"` value),
`academics.ExamResult` (`tenant`, `student`, `passed`), and
`finance.FeeInvoice` (`tenant`, `total`, `amount_paid`) — all per
Appendix C. If your real field names differ, the fix is local to the
four `_metric_name(network, user)` functions in `tasks.py`, not the task's
overall structure.

`reference_stubs/academics/` and `reference_stubs/finance/` are **not**
meant to be dropped into your project — they're what the test suite in
`apps/networks/tests/test_tasks.py` actually ran against, included so you
can diff field names against your real apps, or run the test suite
standalone in a scratch project the way I did. If your real models match
closely enough, you may not need them at all.

## 5. Not built yet

- Shared Curriculum's push-down (Aspect 3), EMIS export using
  `type=GOVERNMENT_DISTRICT` (Aspect 4), and Exam Intelligence's peer
  comparison (Aspect 5) — still just the seams described in the design.
- A recompute-on-demand admin action calling `compute_rollups_for_network`
  directly (the function's already factored out for exactly this) —
  natural next small piece, not built because nothing asked for it yet.
- More metrics. Four are wired up (`ENROLLMENT_COUNT`, `ATTENDANCE_RATE`,
  `FEE_COLLECTION_RATE`, `EXAM_PASS_RATE`); adding another is one function
  in `tasks.py` plus one line in `METRIC_COMPUTERS`, following the same
  per-tenant-plus-weighted-total shape as the existing four.
