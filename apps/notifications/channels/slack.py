import logging

logger = logging.getLogger(__name__)


def send_slack_notification(notification):
    """Basic placeholder for Slack delivery channel."""
    logger.info(
        'Slack notification placeholder: id=%s event=%s recipient=%s',
        notification.id,
        notification.event_type,
        notification.recipient_id,
    )
