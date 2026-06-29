from django.db import models
from django.contrib.auth.models import User

class Notification(models.Model):
    """In-app notifications system to alert users of assignments or status updates"""
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    url = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.message[:30]}"

    class Meta:
        ordering = ['-created_at']
