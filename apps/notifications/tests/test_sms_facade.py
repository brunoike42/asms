import pytest

from ..models import SMSMessage
from ..sms import send_sms
from apps.core.models import Tenant


@pytest.mark.django_db
def test_send_sms_with_default_console_provider_logs_a_sent_message():
    tenant = Tenant.objects.create(name="Test School")

    result = send_sms(tenant, "0712345678", "The bus has arrived at Main Gate.")

    assert result is True
    record = SMSMessage.objects.get(tenant=tenant)
    assert record.status == "sent"
    assert record.provider == "console"
    assert record.phone_e164 == "+256712345678"


@pytest.mark.django_db
def test_send_sms_never_raises_on_invalid_number():
    tenant = Tenant.objects.create(name="Test School")

    result = send_sms(tenant, "garbage", "hello")

    assert result is False
    record = SMSMessage.objects.get(tenant=tenant)
    assert record.status == "invalid_number"
