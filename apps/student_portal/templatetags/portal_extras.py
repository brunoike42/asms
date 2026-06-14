"""
ASMS — Student Portal Custom Template Filters
Phase 3

Load in templates with: {% load portal_extras %}
"""
from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter
def humanize_key(value):
    """Converts a snake_case key to Title Case: 'report_card' -> 'Report Card'."""
    try:
        return str(value).replace('_', ' ').title()
    except AttributeError:
        return value


@register.filter
def split(value, delimiter=','):
    """Split a string by delimiter — for hardcoded comma lists in templates."""
    try:
        return [v.strip() for v in value.split(delimiter)]
    except AttributeError:
        return []


@register.filter
def dict_get(d, key):
    """
    Safe dict lookup for templates: {{ my_dict|dict_get:key }}
    Returns None if key is missing or d is not a dict.
    """
    try:
        return d.get(key)
    except (AttributeError, TypeError):
        return None


@register.filter
def index(sequence, position):
    """
    Returns sequence[position]. Works for lists/tuples and dict-like
    objects with integer-castable keys.
    Usage: {{ days|index:i }}  where i is "0","1",...
    """
    try:
        pos = int(position)
    except (ValueError, TypeError):
        return None
    try:
        # dict (e.g. {0: [...], 1: [...]})
        if hasattr(sequence, 'get'):
            return sequence.get(pos, [])
        return sequence[pos]
    except (IndexError, KeyError, TypeError):
        return []


@register.filter
def pct_of(numerator, denominator):
    """
    Returns numerator / denominator * 100, rounded to 0 dp.
    Returns 0 if denominator is 0/None.
    Usage: {{ cleared_count|pct_of:total_count }}
    """
    try:
        num = Decimal(str(numerator))
        den = Decimal(str(denominator))
        if den == 0:
            return 0
        return int(round((num / den) * 100))
    except (InvalidOperation, TypeError, ZeroDivisionError):
        return 0


@register.filter
def filter_cleared(item_statuses):
    """
    Given a queryset/list of StudentClearanceItemStatus, returns the count
    with status == 'cleared' (or 'waived', treated as satisfied).
    Usage: {{ item_statuses|filter_cleared }}
    """
    try:
        return sum(1 for s in item_statuses if s.status in ('cleared', 'waived'))
    except TypeError:
        return 0


@register.filter
def avg_marks(results):
    """
    Given an iterable of ExamResult-like objects with a `.marks` attribute,
    returns the average marks rounded to 1dp. Returns 0 if empty.
    Usage: {{ result_list|avg_marks }}
    """
    try:
        marks = [Decimal(str(r.marks)) for r in results if r.marks is not None]
        if not marks:
            return Decimal('0.0')
        return round(sum(marks) / len(marks), 1)
    except (TypeError, InvalidOperation):
        return Decimal('0.0')


@register.filter
def sum_results(terms_values):
    """
    Given the .values() of a {term: [results]} dict (i.e. a list of result
    lists), flattens them and returns an object with `.avg` — the overall
    average marks across the whole academic year.
    Usage: {{ terms_dict.values|sum_results }} then {{ ...avg }}
    """
    class _Summary:
        def __init__(self, avg):
            self.avg = avg

    try:
        all_results = [r for result_list in terms_values for r in result_list]
        marks = [Decimal(str(r.marks)) for r in all_results if r.marks is not None]
        if not marks:
            return _Summary(None)
        return _Summary(round(sum(marks) / len(marks), 1))
    except (TypeError, InvalidOperation):
        return _Summary(None)


@register.filter
def grade_color(grade):
    """
    Maps a grade string to a bootstrap colour class suffix.
    Usage: <span class="badge bg-{{ result.grade|grade_color }}">
    """
    if not grade:
        return 'secondary'
    grade = str(grade).upper()
    if grade in ('A', 'D1', 'D2'):
        return 'success'
    if grade in ('B', 'C', 'D3', 'D4', 'D5'):
        return 'primary'
    if grade in ('F', 'F9', 'D9', 'D8', 'D7', 'D6'):
        return 'danger'
    return 'secondary'


@register.filter
def currency(value):
    """Format a number with thousands separators, no decimals — for UGX display."""
    try:
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return value
