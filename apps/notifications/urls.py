"""
Include this in your project's root urls.py (config/urls.py):

    from django.urls import include, path
    urlpatterns = [
        ...,
        path("webhooks/sms/", include("apps.notifications.urls")),
    ]

Then configure these as your delivery-status callback URLs in each
provider's dashboard/API call:
    Africa's Talking: https://yourdomain.com/webhooks/sms/africastalking/
    Twilio:            https://yourdomain.com/webhooks/sms/twilio/
"""
from django.urls import path

from . import webhooks

app_name = "notifications"

urlpatterns = [
    path("africastalking/", webhooks.africastalking_delivery_report, name="dlr_africastalking"),
    path("twilio/", webhooks.twilio_status_callback, name="dlr_twilio"),
]
