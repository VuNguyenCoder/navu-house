import logging

logger = logging.getLogger(__name__)


def send_websocket_notification(notification):
    """Basic placeholder for WebSocket delivery channel."""
    logger.info(
        'WebSocket notification placeholder: id=%s event=%s recipient=%s',
        notification.id,
        notification.event_type,
        notification.recipient_id,
    )
