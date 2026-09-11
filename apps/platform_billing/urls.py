from django.urls import path
from . import views, payment_views

app_name = 'platform_billing'

urlpatterns = [
    path('', views.register_school, name='register'),
    path('billing/', payment_views.billing_status, name='billing_status'),
    path('billing/pay/', payment_views.initiate_platform_payment, name='initiate_payment'),
    path('billing/callback/', payment_views.payment_callback, name='payment_callback'),
    path('billing/invoices/', payment_views.invoice_list, name='invoice_list'),
    path('billing/invoices/<int:pk>/pdf/', payment_views.invoice_pdf, name='invoice_pdf'),
    path('billing/history/', payment_views.payment_history, name='payment_history'),
]
