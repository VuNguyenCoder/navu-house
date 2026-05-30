from django.utils import timezone
from users.models import User
from .models import Notification
from .channels.email import send_email_notification
from .channels.slack import send_slack_notification
from .channels.websocket import send_websocket_notification


class NotificationService:
    # def notify_reviewers_pending_feedback(self, feedback):
    #     recipients = User.objects.filter(role__in=['reviewer', 'operator'])
    #     for recipient in recipients:
    #         notification = Notification.objects.create(
    #             recipient=recipient,
    #             feedback=feedback,
    #             channel='email',
    #             event_type='pending_feedback',
    #             subject='New feedback requires review',
    #             message=(
    #                 f'Feedback {feedback.feedback_id} '
    #                 f'was submitted by {feedback.user.username}.'
    #             ),
    #             payload={
    #                 'feedback_id': str(feedback.feedback_id),
    #                 'feedback_type': feedback.feedback_type,
    #                 'input_type': feedback.input_type,
    #                 'submitted_by': feedback.user.username,
    #             },
    #         )
    #         self.dispatch(notification)

    def dispatch(self, notification):
        senders = {
            'email': send_email_notification,
            'slack': send_slack_notification,
            'websocket': send_websocket_notification,
        }

        sender = senders.get(notification.channel)
        if sender is None:
            notification.status = 'failed'
            notification.error_message = f'Unsupported channel: {notification.channel}'
            notification.save(update_fields=['status', 'error_message'])
            return

        try:
            sender(notification)
            notification.status = 'sent'
            notification.error_message = ''
            notification.sent_at = timezone.now()
            notification.save(update_fields=['status', 'error_message', 'sent_at'])
        except Exception as exc:
            notification.status = 'failed'
            notification.error_message = str(exc)
            notification.save(update_fields=['status', 'error_message'])
