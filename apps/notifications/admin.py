from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'channel', 'status', 'created_at', 'sent_at')
    list_filter = ('channel', 'status', 'created_at')
    search_fields = ('id', 'recipient__username', 'recipient__email', 'subject')
    readonly_fields = ('id', 'created_at', 'sent_at', 'error_message')
    ordering = ('-created_at',)
