"""
Comma-separated currency display, matching the f'{amount:,.0f}' pattern
already used in apps/finance/models.py's __str__ methods -- kept as our
own small filter instead of assuming django.contrib.humanize is in
INSTALLED_APPS, which hasn't been confirmed.
"""
from django import template

register = template.Library()


@register.filter
def commas(value):
    try:
        return f'{float(value):,.0f}'
    except (TypeError, ValueError):
        return value
