import uuid
from django.db import models


class Notification(models.Model):
    CHANNELS = [
        ('email', 'Email'),
        ('slack', 'Slack'),
        ('websocket', 'WebSocket'),
    ]

    STATUSES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='notifications')
    channel = models.CharField(max_length=20, choices=CHANNELS, default='email')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default='pending')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event_type}:{self.channel}:{self.recipient}"
