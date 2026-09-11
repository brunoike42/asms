"""
simulate_scan.py

Simulates a biometric device POSTing a scan event to the ASMS ingestion
endpoint. Use this to test the endpoint end-to-end before you have real
hardware.

Usage:
    pip install requests   (if not already installed)
    python simulate_scan.py
"""
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import requests

# ---- EDIT THESE ----
BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = "/api/biometric/v1/scan/"   # adjust if you chose Option A in the urls guide
SERIAL = "ZK-TEST-001"                  # must match BiometricDevice.serial_number
SECRET = "PASTE_DEVICE_SECRET_KEY_HERE" # from device.secret_key when you created it
TEMPLATE_ID = "1"                       # must match BiometricTemplate.template_id
# ---------------------

def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def main():
    payload = {
        "device_serial": SERIAL,
        "template_id": TEMPLATE_ID,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "timestamp": time.time(),
    }
    body = json.dumps(payload).encode("utf-8")
    signature = sign(SECRET, body)

    resp = requests.post(
        BASE_URL + ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-ASMS-Signature": signature,
        },
    )
    print("Status:", resp.status_code)
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    main()
