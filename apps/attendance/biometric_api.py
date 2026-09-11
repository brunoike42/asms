# ============================================================
# NEW FILE: apps/attendance/biometric_api.py
# ============================================================
"""
Biometric scan ingestion endpoint.

Per spec Section 13 / Appendix E:
    POST /api/biometric/v1/scan/
    Authenticated via HMAC-SHA256 signed request (not JWT) — devices
    don't hold user credentials, they hold a per-device secret key.

Expected request body (JSON):
{
    "device_serial": "ZK-001",         # or use device.id if you prefer
    "template_id": "17",               # fingerprint template ID from the device
    "scanned_at": "2026-07-02T07:14:03Z",
    "timestamp": 1751440443             # unix timestamp, used for anti-replay
}

Expected headers:
    X-ASMS-Signature: <hex hmac-sha256 of raw request body using device.secret_key>

Anti-replay: reject if abs(now - timestamp) > 300 seconds (5 minute window).

Attendance window: reject with OUT_OF_WINDOW if scan falls outside the school's
configured attendance marking window (default 06:00-09:00 local, adjust as needed —
see ATTENDANCE_WINDOW_START / ATTENDANCE_WINDOW_END below).
"""

import hmac
import hashlib
import time
from datetime import datetime, time as dt_time

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.students.models import ClassRoom
from .models import (
    AttendanceRecord,
    BiometricDevice,
    BiometricTemplate,
    BiometricScanLog,
)

# Adjust to your school's actual attendance window
ATTENDANCE_WINDOW_START = dt_time(6, 0)
ATTENDANCE_WINDOW_END = dt_time(9, 30)

REPLAY_WINDOW_SECONDS = 300  # 5 minutes


def verify_signature(device: BiometricDevice, raw_body: bytes, signature_header: str) -> bool:
    """Constant-time HMAC-SHA256 verification."""
    if not signature_header:
        return False
    expected = hmac.new(
        key=device.secret_key.encode('utf-8'),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


class BiometricScanView(APIView):
    """
    Public-facing endpoint (no user JWT) — authenticated purely via
    device-specific HMAC signature. Devices are identified by device_serial.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        raw_body = request.body
        signature = request.headers.get('X-ASMS-Signature', '')

        device_serial = request.data.get('device_serial')
        template_id = request.data.get('template_id')
        scanned_at_raw = request.data.get('scanned_at')
        req_timestamp = request.data.get('timestamp')

        # --- 1. Resolve device ---
        try:
            device = BiometricDevice.objects.get(
                serial_number=device_serial,
                status=BiometricDevice.DeviceStatus.ACTIVE,
            )
        except BiometricDevice.DoesNotExist:
            return Response(
                {'status': 'error', 'code': 'DEVICE_NOT_FOUND',
                 'message': 'Unknown or inactive device'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # --- 2. Verify signature ---
        if not verify_signature(device, raw_body, signature):
            BiometricScanLog.objects.create(
                tenant=device.tenant,
                device=device,
                template_id_raw=template_id or '',
                scanned_at=timezone.now(),
                result=BiometricScanLog.ScanResult.INVALID_SIG,
                raw_payload=request.data,
            )
            return Response(
                {'status': 'error', 'code': 'INVALID_SIGNATURE',
                 'message': 'HMAC signature verification failed'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # --- 3. Anti-replay check ---
        if req_timestamp:
            try:
                if abs(time.time() - float(req_timestamp)) > REPLAY_WINDOW_SECONDS:
                    return Response(
                        {'status': 'error', 'code': 'STALE_REQUEST',
                         'message': 'Request timestamp outside acceptable window'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except (TypeError, ValueError):
                return Response(
                    {'status': 'error', 'code': 'BAD_TIMESTAMP',
                     'message': 'Invalid timestamp format'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        device.mark_seen()

        scanned_at = parse_datetime(scanned_at_raw) if scanned_at_raw else timezone.now()
        if scanned_at is None:
            scanned_at = timezone.now()

        # --- 4. Resolve student from template ---
        try:
            template = BiometricTemplate.objects.select_related('student').get(
                device=device, template_id=template_id, is_active=True,
            )
        except BiometricTemplate.DoesNotExist:
            BiometricScanLog.objects.create(
                tenant=device.tenant,
                device=device,
                template_id_raw=template_id or '',
                scanned_at=scanned_at,
                result=BiometricScanLog.ScanResult.UNKNOWN,
                raw_payload=request.data,
            )
            return Response(
                {'status': 'error', 'code': 'UNKNOWN_TEMPLATE',
                 'message': 'No student enrolled with this template ID on this device'},
                status=status.HTTP_404_NOT_FOUND,
            )

        student = template.student

        # --- 5. Attendance window check ---
        local_time = timezone.localtime(scanned_at).time()
        if not (ATTENDANCE_WINDOW_START <= local_time <= ATTENDANCE_WINDOW_END):
            BiometricScanLog.objects.create(
                tenant=device.tenant,
                device=device,
                student=student,
                template_id_raw=template_id,
                scanned_at=scanned_at,
                result=BiometricScanLog.ScanResult.OUT_OF_WINDOW,
                raw_payload=request.data,
            )
            return Response(
                {'status': 'success', 'data': {'result': 'OUT_OF_WINDOW'},
                 'meta': {}},
                status=status.HTTP_200_OK,
            )

        # --- 6. Duplicate check (already marked today) ---
        today = timezone.localdate(scanned_at)
        existing = AttendanceRecord.objects.filter(student=student, date=today).first()
        if existing and existing.status == AttendanceRecord.StatusChoices.PRESENT:
            BiometricScanLog.objects.create(
                tenant=device.tenant,
                device=device,
                student=student,
                template_id_raw=template_id,
                scanned_at=scanned_at,
                result=BiometricScanLog.ScanResult.DUPLICATE,
                attendance_record=existing,
                raw_payload=request.data,
            )
            return Response(
                {'status': 'success', 'data': {'result': 'DUPLICATE'}, 'meta': {}},
                status=status.HTTP_200_OK,
            )

        # --- 7. Write / update AttendanceRecord ---
        # This reuses the same model your manual mark_attendance view writes to,
        # so any post_save signal you have wired for SMS / risk-score updates
        # (Appendix D.1) fires automatically here too — no duplicate logic needed.
        classroom = device.classroom or getattr(
            student.enrollments.filter(is_active=True).first(), 'classroom', None
        )
        record, created = AttendanceRecord.objects.update_or_create(
            tenant=device.tenant,
            student=student,
            date=today,
            defaults={
                'classroom': classroom,
                'status': AttendanceRecord.StatusChoices.PRESENT,
                'marked_by': None,  # device-marked, not a staff user
                'notes': f'Biometric scan via {device.name}',
            },
        )

        BiometricScanLog.objects.create(
            tenant=device.tenant,
            device=device,
            student=student,
            template_id_raw=template_id,
            scanned_at=scanned_at,
            result=BiometricScanLog.ScanResult.MATCHED,
            attendance_record=record,
            raw_payload=request.data,
        )

        return Response(
            {
                'status': 'success',
                'data': {
                    'result': 'MATCHED',
                    'student_id': student.id,
                    'attendance_record_id': record.id,
                    'created': created,
                },
                'meta': {},
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
