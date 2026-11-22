from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Role, User, UserProfile, UserRole


@receiver(post_save, sender=User)
def ensure_profile_and_customer_role(sender, instance, created, **kwargs):
    if not created:
        return
    UserProfile.objects.get_or_create(user=instance)
    customer, _ = Role.objects.get_or_create(
        name="Customer",
        defaults={"description": "Default customer role"},
    )
    UserRole.objects.get_or_create(user=instance, role=customer)
