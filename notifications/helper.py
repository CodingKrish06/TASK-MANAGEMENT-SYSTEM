from .models import Notification

def send_notification(recipient, message, sender=None, url=None):
    """Utility helper to create and trigger an in-app notification for a user"""
    return Notification.objects.create(
        recipient=recipient,
        sender=sender,
        message=message,
        url=url
    )
