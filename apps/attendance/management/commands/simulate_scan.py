import json
import hmac
import hashlib
import time

from django.conf import settings
from django.utils import timezone
from django.test import Client
from django.core.management.base import BaseCommand

from apps.core.models import Tenant  # adjust if Tenant lives elsewhere
from apps.attendance.models import BiometricDevice, BiometricTemplate
from apps.students.models import Student


class Command(BaseCommand):
    help = "Simulate a biometric scanner POSTing to /api/biometric/v1/scan/"

    def handle(self, *args, **options):
        if 'testserver' not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS.append('testserver')

        tenant = Tenant.objects.first()
        if not tenant:
            self.stderr.write("No Tenant in the DB — create one first.")
            return

        device, _ = BiometricDevice.objects.get_or_create(
            tenant=tenant, serial_number='TEST-SIM-001',
            defaults={'name': 'Simulated Test Scanner'},
        )

        student = Student.objects.filter(tenant=tenant).first()
        if not student:
            self.stderr.write("No Student in the DB for this tenant — create one first.")
            return

        template, _ = BiometricTemplate.objects.get_or_create(
            tenant=tenant, device=device, template_id='TEST-TPL-001',
            defaults={'student': student},
        )

        scan_time = timezone.localtime().replace(hour=7, minute=15, second=0, microsecond=0)
        payload = {
            "device_serial": device.serial_number,
            "template_id": template.template_id,
            "scanned_at": scan_time.isoformat(),
            "timestamp": int(time.time()),
        }
        raw_body = json.dumps(payload).encode('utf-8')
        signature = hmac.new(device.secret_key.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()

        client = Client()
        response = client.post(
            '/api/biometric/v1/scan/',
            data=raw_body,
            content_type='application/json',
            HTTP_X_ASMS_SIGNATURE=signature,
        )
        self.stdout.write(f"Status: {response.status_code}")
        try:
            self.stdout.write(json.dumps(response.json(), indent=2))
        except Exception:
            self.stdout.write(response.content.decode())