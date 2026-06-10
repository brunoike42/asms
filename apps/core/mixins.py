"""
View mixins for tenant-scoped QuerySets.
Every view that touches the database should use TenantQuerySetMixin.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class TenantQuerySetMixin:
    """
    Automatically scopes get_queryset() to the current request.tenant.
    Use on any class-based view that renders a model list or detail.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, 'tenant', None)
        if tenant is None:
            return qs.none()
        return qs.filter(tenant=tenant)


class TenantRequiredMixin(LoginRequiredMixin, TenantQuerySetMixin):
    """
    Combined mixin: user must be logged in AND a valid tenant must be resolved.
    Use this as the base for all ASMS views.
    """

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request, 'tenant', None):
            raise PermissionDenied('No school context found.')
        return super().dispatch(request, *args, **kwargs)


def require_roles(*roles):
    """
    Decorator for function-based views.
    Usage: @require_roles('principal', 'school_admin')
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.shortcuts import redirect
                return redirect('accounts:login')
            if request.user.role not in roles and not request.user.is_superuser:
                raise PermissionDenied('You do not have permission to access this page.')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
