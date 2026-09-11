from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def create_student_profile(sender, instance, created, **kwargs):
    """
    When a new STUDENT-role user is created, ensure a Student row exists
    for their tenant and is linked to them.
    """
    if not created:
        return
    if getattr(instance, 'role', None) != 'STUDENT':
        return
    if not hasattr(instance, 'tenant') or instance.tenant is None:
        return

    from apps.students.models import Student

    # Only create if no Student row already claims this user
    if not Student.objects.filter(user=instance).exists():
        Student.objects.create(
            user=instance,
            tenant=instance.tenant,
            first_name=instance.first_name or '',
            last_name=instance.last_name or '',
            # student_id / class_room etc. left for admin to complete
        )