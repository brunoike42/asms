from django.urls import path
from . import views
app_name = 'finance'
urlpatterns = [
    path('invoices/',                          views.invoice_list,     name='invoice_list'),
    path('invoices/<int:pk>/',                 views.invoice_detail,   name='invoice_detail'),
    path('invoices/<int:invoice_pk>/pay/',     views.record_payment,   name='record_payment'),
    path('reports/arrears/',                views.arrears_report, name='arrears_report'),
     path('invoices/generate/',              views.generate_invoice, name='generate_invoice'),
      path('payments/<int:pk>/receipt/',      views.receipt_pdf, name='receipt_pdf'),
]
