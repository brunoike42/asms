import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")  # adjust if your settings module differs -- check manage.py for the exact value
django.setup()
import asyncio
import random
from apps.core.models import get_current_tenant, set_current_tenant, clear_current_tenant
class FakeTenant:
    def __init__(self, id, name):
        self.id = id
        self.name = name
    def __repr__(self):
        return f"Tenant({self.name})"
async def simulate_request(tenant, request_id):
    """Mirrors what TenantMiddleware now does per-request, but runs
    concurrently with other 'requests' on the same event loop / thread --
    exactly the case threading.local() would fail."""
    token = set_current_tenant(tenant)
    try:
        await asyncio.sleep(random.uniform(0.01, 0.05))
        seen = get_current_tenant()
        assert seen is tenant, f"LEAK on request {request_id}: expected {tenant}, got {seen}"
        await asyncio.sleep(random.uniform(0.01, 0.05))
        seen_again = get_current_tenant()
        assert seen_again is tenant, f"LEAK on request {request_id} (2nd check): expected {tenant}, got {seen_again}"
        return f"request {request_id} OK -- stayed on {tenant}"
    finally:
        clear_current_tenant(token)
async def main():
    tenant_a = FakeTenant(1, "School A")
    tenant_b = FakeTenant(2, "School B")
    tasks = [
        simulate_request(tenant_a if i % 2 == 0 else tenant_b, i)
        for i in range(40)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        print(f"\nFAILED -- {len(failures)} cross-tenant leak(s):")
        for f in failures:
            print(f"  {f}")
    else:
        print(f"\nPASSED -- all {len(results)} concurrent simulated requests stayed isolated. contextvars fix confirmed.")
    leftover = get_current_tenant()
    assert leftover is None, f"Context not clean after run -- leftover: {leftover}"
    print("Post-run context is clean (get_current_tenant() -> None).")
asyncio.run(main())
