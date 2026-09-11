"""
Phone number validation and normalization.

Production messaging APIs (Twilio's Lookup API is the canonical example)
validate numbers *before* attempting to send, because a malformed number
still costs a provider round-trip and, on some providers, still gets billed.
We do the equivalent locally and for free using Google's libphonenumber via
the `phonenumbers` package, instead of paying for a lookup call.
"""
from .exceptions import InvalidPhoneNumberError

try:
    import phonenumbers
except ImportError:  # pragma: no cover - exercised only if dependency missing
    phonenumbers = None


def normalize_phone(raw_number, default_region="UG"):
    """Normalize a phone number to E.164 (e.g. '+256712345678').

    default_region is the ISO 3166-1 alpha-2 country code used to interpret
    numbers dialled in local/national format (no country code). Set
    NOTIFICATIONS_DEFAULT_REGION in settings to match where most of your
    guardians/parents are based; override per-call if a tenant operates in
    a different country.

    Raises InvalidPhoneNumberError (permanent — do not retry) if the number
    cannot be parsed or is not a valid, receivable number.
    """
    if not raw_number or not raw_number.strip():
        raise InvalidPhoneNumberError("Phone number is empty")

    if phonenumbers is None:
        # Degrade gracefully rather than hard-crash if the dependency isn't
        # installed yet — but this is not a substitute for real validation.
        cleaned = raw_number.strip()
        if not cleaned.startswith("+") or len(cleaned) < 8:
            raise InvalidPhoneNumberError(
                f"Cannot validate '{raw_number}': 'phonenumbers' package not installed "
                "and number is not already in +E.164 form"
            )
        return cleaned

    try:
        parsed = phonenumbers.parse(raw_number, default_region)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhoneNumberError(f"Cannot parse phone number '{raw_number}': {exc}") from exc

    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumberError(f"'{raw_number}' is not a valid phone number")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
