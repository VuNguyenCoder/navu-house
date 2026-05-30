from notifications.models import Notification


def notifications_dropdown(request):
    if not request.user.is_authenticated:
        return {
            'navbar_notifications': [],
            'navbar_notifications_count': 0,
        }

    qs = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    notifications = list(qs[:8])

    return {
        'navbar_notifications': notifications,
        'navbar_notifications_count': qs.count(),
    }
