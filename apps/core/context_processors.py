"""
Context processors for ASMS.
tenant_context  — provides {{ tenant }} to every template
role_context    — provides role flags (can_see_finance, etc.) for sidebar filtering
"""
ADMIN_ROLES = (
    "school_admin",
    "principal",
    "platform_admin",
    "network_admin",
)
def tenant_context(request):
    """Makes {{ tenant }} available in every template."""
    return {"tenant": getattr(request, "tenant", None)}
def role_context(request):
    """Sidebar visibility flags based on the logged-in user's role."""
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {}
    role = getattr(request.user, "role", "")
    return {
        "is_full_admin":          role in ADMIN_ROLES,
        "can_see_students":       role in ADMIN_ROLES + ("teacher", "receptionist", "counsellor", "nurse"),
        "can_see_academics":      role in ADMIN_ROLES + ("teacher",),
        "can_see_finance":        role in ADMIN_ROLES + ("accountant",),
        "can_see_welfare":        role in ADMIN_ROLES + ("counsellor", "teacher"),
        "can_see_communication":  role in ADMIN_ROLES + ("receptionist",),
        "can_see_staff":          role in ADMIN_ROLES,
        "can_see_library":        role in ADMIN_ROLES + ("librarian",),
        "can_see_staff_or_library": role in ADMIN_ROLES + ("librarian",),
    }
