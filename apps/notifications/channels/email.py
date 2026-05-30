from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_email_notification(notification):
    recipient_email = notification.recipient.email
    if not recipient_email:
        raise ValueError('Recipient does not have an email address.')

    context = {
        'recipient': notification.recipient,
        'subject': notification.subject,
        'message': notification.message,
        'payload': notification.payload,
    }
    html_body = render_to_string('email/new_analytic.html', context)

    send_mail(
        subject=notification.subject,
        message=notification.message,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@tf-feedback.local'),
        recipient_list=[recipient_email],
        html_message=html_body,
        fail_silently=False,
    )
