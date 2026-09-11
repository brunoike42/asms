import pytest

from ..exceptions import InvalidPhoneNumberError
from ..phone import normalize_phone


def test_normalizes_local_ugandan_number_to_e164():
    assert normalize_phone("0712345678", default_region="UG") == "+256712345678"


def test_accepts_already_e164_number():
    assert normalize_phone("+256712345678", default_region="UG") == "+256712345678"


def test_rejects_empty_number():
    with pytest.raises(InvalidPhoneNumberError):
        normalize_phone("", default_region="UG")


def test_rejects_garbage_input():
    with pytest.raises(InvalidPhoneNumberError):
        normalize_phone("not-a-phone-number", default_region="UG")


def test_rejects_too_short_number():
    with pytest.raises(InvalidPhoneNumberError):
        normalize_phone("123", default_region="UG")
