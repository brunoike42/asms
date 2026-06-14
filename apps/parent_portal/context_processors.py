"""
apps/parent_portal/context_processors.py
Injects `students` and `active_student` into every parent-portal template.
Referenced in settings.py as:
    apps.parent_portal.context_processors.parent_context
"""


def parent_context(request):
    """
    Makes `students` and `active_student` available in all templates
    that extend parent/base.html, bridging the old children_data
    convention with the new sidebar variables.
    """
    if not request.user.is_authenticated:
        return {}

    if not request.path.startswith("/parent"):
        return {}

    try:
        profile = getattr(request.user, "parent_profile", None)
        if profile is None:
            return {"students": [], "active_student": None}

        students = []
        if hasattr(profile, "children"):
            students = list(profile.children.all())
        elif hasattr(profile, "students"):
            students = list(profile.students.all())

        active_student = students[0] if students else None

        # Honour ?child_id= switcher chip
        child_id = (
            request.GET.get("child_id")
            or request.session.get("active_child_id")
        )
        if child_id:
            for s in students:
                if str(s.pk) == str(child_id):
                    active_student = s
                    request.session["active_child_id"] = str(child_id)
                    break

        return {
            "students": students,
            "active_student": active_student,
        }
    except Exception:
        return {"students": [], "active_student": None}


# Alias kept for any legacy references
parent_students = parent_context
