"""STUB — for validation only. See apps/academics/models.py docstring — same deal."""
from django.db import models


class FeeInvoice(models.Model):
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE)
    student = models.ForeignKey("academics.Student", on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
