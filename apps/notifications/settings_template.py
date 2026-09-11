"""
Not imported by the app — this documents exactly what to add to
config/settings.py. See the README for the step that tells you where.

NOTE: this project's SMSMessage model inherits apps.core.models.TenantModel
directly (same as Vehicle, Driver, etc.) — there is no NOTIFICATIONS_TENANT_MODEL
setting to configure, unlike a from-scratch install of this package.
"""

# Your settings.py already has these three (Africa's Talking) — this block
# just reshapes them into the structure notifications/sms.py reads, so nothing
# is duplicated or re-entered. Twilio is optional: only added to the chain if
# TWILIO_ACCOUNT_SID is actually set, so leaving it unset gives you a
# single-provider setup (still gets circuit-breaker protection, no failover
# until you add real Twilio credentials).
NOTIFICATIONS_PROVIDERS = [
    {
        "type": "africastalking",
        "username": AFRICASTALKING_USERNAME,
        "api_key": AFRICASTALKING_API_KEY,
        "sender_id": AFRICASTALKING_SENDER_ID,
    },
]

_twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
if _twilio_sid:
    NOTIFICATIONS_PROVIDERS.append({
        "type": "twilio",
        "account_sid": _twilio_sid,
        "auth_token": os.getenv("TWILIO_AUTH_TOKEN", ""),
        "from_number": os.getenv("TWILIO_FROM_NUMBER", ""),
    })

NOTIFICATIONS_CACHE_ALIAS = "default"

NOTIFICATIONS_CIRCUIT_BREAKER = {
    "failure_threshold": 5,
    "recovery_timeout_seconds": 30,
    "half_open_max_calls": 1,
}

NOTIFICATIONS_RATE_LIMIT = {
    "rate_per_second": 5,
    "capacity": 20,
}

NOTIFICATIONS_IDEMPOTENCY = {
    "enabled": True,
    "ttl_seconds": 3600,
}

NOTIFICATIONS_DEFAULT_REGION = "UG"


# --------------------------------------------------------------------------
# Production note: CACHES currently uses LocMemCache (per-process memory).
# The circuit breaker / rate limiter / idempotency guard all need a SHARED
# cache once you run more than one Celery worker or Gunicorn process, or
# they'll each get their own view of "is Africa's Talking down right now" —
# defeating the point. You already have REDIS_URL defined for Celery; point
# CACHES at it too once you deploy with multiple workers:
#
#   CACHES = {
#       "default": {
#           "BACKEND": "django_redis.cache.RedisCache",
#           "LOCATION": REDIS_URL,
#           "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
#       }
#   }
#
# (pip install django-redis first). Not required for local dev with
# `runserver` — LocMemCache is fine there since it's a single process.
# --------------------------------------------------------------------------
