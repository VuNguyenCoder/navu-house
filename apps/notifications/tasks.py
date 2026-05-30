from celery import shared_task
from .models import Notification
from .services import NotificationService


@shared_task(bind=True, max_retries=3)
def send_notification_async(self, notification_id):
    notification = Notification.objects.get(id=notification_id)
    NotificationService().dispatch(notification)


@shared_task
def retry_failed_notifications():
    failed_notifications = Notification.objects.filter(status='failed').order_by('-created_at')[:100]
    service = NotificationService()
    for notification in failed_notifications:
        service.dispatch(notification)
