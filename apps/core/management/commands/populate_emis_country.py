"""
populate_emis_country — one-time backfill for Tenant.emis_country from the
existing free-text Tenant.country field. Safe to re-run: only touches rows
where emis_country is still blank. Deliberately does NOT guess on values it
can't confidently map — it lists them so you set those manually instead.

Usage:
    python manage.py populate_emis_country
    python manage.py populate_emis_country --dry-run
"""
from django.core.management.base import BaseCommand
from apps.core.models import Tenant

COUNTRY_MAP = {
    "uganda": Tenant.EMISCountryChoices.UGANDA,
    "kenya": Tenant.EMISCountryChoices.KENYA,
    "rwanda": Tenant.EMISCountryChoices.RWANDA,
    "tanzania": Tenant.EMISCountryChoices.TANZANIA,
}


class Command(BaseCommand):
    help = "Backfill Tenant.emis_country from the free-text Tenant.country field."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        tenants = Tenant.objects.filter(emis_country="")
        matched, unmatched = 0, []

        for tenant in tenants:
            key = (tenant.country or "").strip().lower()
            code = COUNTRY_MAP.get(key)
            if code:
                matched += 1
                self.stdout.write(f"{tenant.name}: '{tenant.country}' -> {code}")
                if not dry_run:
                    tenant.emis_country = code
                    tenant.save(update_fields=["emis_country"])
            else:
                unmatched.append(tenant)

        self.stdout.write(self.style.SUCCESS(f"{matched} tenant(s) matched."))
        if unmatched:
            self.stdout.write(self.style.WARNING(
                f"{len(unmatched)} tenant(s) could not be matched automatically — "
                f"set emis_country manually for these (Django admin, or shell):"
            ))
            for t in unmatched:
                self.stdout.write(f"   - {t.name} (id={t.pk}): country='{t.country}'")
        if dry_run:
            self.stdout.write(self.style.NOTICE("Dry run — no changes saved."))
