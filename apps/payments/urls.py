from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment flow
    path('pay/<int:invoice_pk>/',       views.initiate_payment, name='initiate'),
    path('callback/',                   views.payment_callback, name='callback'),
    path('ipn/',                        views.ipn_handler,      name='ipn'),

    # Result pages
    path('success/<int:pk>/',           views.payment_success,  name='success'),
    path('failed/<int:pk>/',            views.payment_failed,   name='failed'),

    # AJAX polling
    path('status/<int:pk>/check/',      views.check_status,     name='check_status'),

    # History
    path('history/',                    views.payment_history,  name='history'),
]
