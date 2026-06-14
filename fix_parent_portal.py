import os

# ── Fix 1: profile.html ──────────────────────────────────────────────────────
profile_path = r'apps\parent_portal\templates\parent\profile.html'
with open(profile_path, encoding='utf-8') as f:
    html = f.read()

if "url 'dashboard'" in html:
    html = html.replace("url 'dashboard'", "url 'parent:dashboard'")
    with open(profile_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ Fixed profile.html: url 'dashboard' → url 'parent:dashboard'")
else:
    print("ℹ️  profile.html already correct")

# ── Fix 2: views.py require_parent decorator ─────────────────────────────────
views_path = r'apps\parent_portal\views.py'
with open(views_path, encoding='utf-8') as f:
    views = f.read()

if "return redirect('dashboard')" in views:
    views = views.replace("return redirect('dashboard')", "return redirect('parent:dashboard')")
    with open(views_path, 'w', encoding='utf-8') as f:
        f.write(views)
    print("✅ Fixed views.py: redirect('dashboard') → redirect('parent:dashboard')")
else:
    print("ℹ️  views.py already correct")

# ── Fix 3: utils.py get_activity_feed – models.Q used before models imported ─
utils_path = r'apps\parent_portal\utils.py'
with open(utils_path, encoding='utf-8') as f:
    utils = f.read()

old_feed = '''def get_activity_feed(student, limit=10):
    """
    Return recent activity posts for this student\'s class.
    Benchmarked: ClassDojo class story, Seesaw learning feed.
    """
    try:
        from .models import ActivityPost
        posts = ActivityPost.objects.filter(
            tenant=student.tenant,
        ).filter(
            models.Q(classroom=student.current_class) |
            models.Q(student=student) |
            models.Q(audience=\'school\')
        ).order_by(\'-is_pinned\', \'-created_at\')[:limit]
        return list(posts)
    except Exception:
        from django.db import models
        return []'''

new_feed = '''def get_activity_feed(student, limit=10):
    """
    Return recent activity posts for this student\'s class.
    Benchmarked: ClassDojo class story, Seesaw learning feed.
    """
    try:
        from django.db.models import Q
        from .models import ActivityPost
        posts = ActivityPost.objects.filter(
            tenant=student.tenant,
        ).filter(
            Q(classroom=student.current_class) |
            Q(student=student) |
            Q(audience=\'school\')
        ).order_by(\'-is_pinned\', \'-created_at\')[:limit]
        return list(posts)
    except Exception:
        return []'''

if 'models.Q(classroom' in utils:
    utils = utils.replace(old_feed, new_feed)
    # Fallback: simpler targeted replace if exact block differs slightly
    if 'models.Q(classroom' in utils:
        utils = utils.replace('models.Q(classroom=student.current_class)', 'Q(classroom=student.current_class)')
        utils = utils.replace('models.Q(student=student)', 'Q(student=student)')
        utils = utils.replace("models.Q(audience='school')", "Q(audience='school')")
        # Add Q import inside the try block
        utils = utils.replace(
            "        from .models import ActivityPost\n        posts = ActivityPost.objects.filter(",
            "        from django.db.models import Q\n        from .models import ActivityPost\n        posts = ActivityPost.objects.filter("
        )
    # Remove the broken 'from django.db import models' from except block
    utils = utils.replace("        from django.db import models\n        return []", "        return []")
    with open(utils_path, 'w', encoding='utf-8') as f:
        f.write(utils)
    print("✅ Fixed utils.py: get_activity_feed models.Q import bug")
else:
    print("ℹ️  utils.py get_activity_feed already correct or already fixed")

print("\nAll fixes applied. Restart server to see changes.")