from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from main.models import Settings, Subscription, Usage
from main.views import get_linked_restroom_usage_context, get_previous_usage_context


def _get_dashboard_period(request):
    default_settings = Settings.get_solo()
    today = default_settings.get_default_usage_period(timezone.localdate())
    period_value = request.GET.get('period')
    month_value = request.GET.get('month')
    year_value = request.GET.get('year')
    try:
        if period_value:
            parsed_year, parsed_month = period_value.split('-', 1)
            return date(year=int(parsed_year), month=int(parsed_month), day=1)
        if month_value and year_value:
            return date(year=int(year_value), month=int(month_value), day=1)
    except (TypeError, ValueError):
        pass
    return today


def _build_usage_dashboard_totals(usage):
    previous_context = get_previous_usage_context(usage.subscription, usage.period, exclude_usage_id=usage.pk)
    previous_electricity = previous_context['previous_electricity_reading']
    previous_water = previous_context['previous_water_reading']
    electricity_consumed = max(usage.latest_electricity_reading - previous_electricity, 0)
    water_consumed = max(usage.latest_water_reading - previous_water, 0)
    tenant_count = usage.tenant_count or 0

    linked_restroom_context = get_linked_restroom_usage_context(usage.subscription, usage.period)
    linked_restroom_electricity_amount = Decimal('0')
    linked_restroom_water_amount = Decimal('0')
    if linked_restroom_context and linked_restroom_context.get('has_usage'):
        total_linked_tenants = linked_restroom_context['other_linked_tenants'] + tenant_count
        if total_linked_tenants > 0:
            linked_restroom_electricity_amount = (
                linked_restroom_context['electricity_amount'] / Decimal(total_linked_tenants)
            ) * Decimal(tenant_count)
            linked_restroom_water_amount = (
                linked_restroom_context['water_amount'] / Decimal(total_linked_tenants)
            ) * Decimal(tenant_count)

    room_amount = Decimal(usage.room_price or 0)
    electricity_amount = Decimal(electricity_consumed) * Decimal(usage.electricity_price or 0)
    water_amount = Decimal(water_consumed) * Decimal(usage.water_price or 0)
    internet_amount = Decimal(usage.internet_price or 0) if usage.use_internet else Decimal('0')
    cleaning_amount = Decimal(tenant_count) * Decimal(usage.cleaning_price or 0)
    laundry_amount = Decimal(tenant_count) * Decimal(usage.laundry_price or 0) if usage.use_laundry else Decimal('0')

    return {
        'electricity_consumed': electricity_consumed,
        'water_consumed': water_consumed,
        'electricity_revenue': electricity_amount + linked_restroom_electricity_amount,
        'water_revenue': water_amount + linked_restroom_water_amount,
        'room_revenue': room_amount,
        'total_amount': (
            room_amount
            + electricity_amount
            + water_amount
            + internet_amount
            + cleaning_amount
            + laundry_amount
            + linked_restroom_electricity_amount
            + linked_restroom_water_amount
        ),
    }


def _format_number(value):
    if isinstance(value, Decimal):
        return f'{value:,.0f}'
    return f'{int(value):,}'


def _build_dashboard_period_choices(period):
    current_month = timezone.localdate().replace(day=1)
    choices = []
    start_index = current_month.year * 12 + current_month.month - 11
    end_index = current_month.year * 12 + current_month.month + 2
    for month_index in range(start_index, end_index + 1):
        year = (month_index - 1) // 12
        month = (month_index - 1) % 12 + 1
        value = f'{year}-{month:02d}'
        label = f'{month:02d}/{year}'
        choices.append((value, label))
    return list(reversed(choices))


@login_required(login_url='account_login')
def home(request):
    period = _get_dashboard_period(request)
    selected_month = period.strftime('%m')
    selected_year = str(period.year)

    subscriptions = list(
        Subscription.objects.select_related('room')
        .filter(
            Q(status=Subscription.Status.ENABLED)
            | Q(usages__period=period)
        )
        .distinct()
        .order_by('room__room_name', '-start_date')
    )

    usage_queryset = (
        Usage.objects.select_related('subscription', 'subscription__room')
        .filter(subscription__in=subscriptions, period=period)
        .order_by('subscription_id', '-updated_at', '-id')
    )
    usage_by_subscription_id = {}
    for usage in usage_queryset:
        usage_by_subscription_id.setdefault(usage.subscription_id, usage)

    total_electricity_consumed = 0
    total_water_consumed = 0
    total_electricity_revenue = Decimal('0')
    total_water_revenue = Decimal('0')
    total_room_revenue = Decimal('0')
    total_revenue = Decimal('0')

    usage_status_cells = []
    shared_restroom_status_cells = []
    for subscription in subscriptions:
        is_rest_room_subscription = subscription.room.type == subscription.room.RoomType.REST
        usage = usage_by_subscription_id.get(subscription.pk)
        if usage:
            usage_totals = _build_usage_dashboard_totals(usage)
            total_electricity_consumed += usage_totals['electricity_consumed']
            total_water_consumed += usage_totals['water_consumed']
            if not is_rest_room_subscription:
                total_electricity_revenue += usage_totals['electricity_revenue']
                total_water_revenue += usage_totals['water_revenue']
            total_room_revenue += usage_totals['room_revenue']
            if not is_rest_room_subscription:
                total_revenue += usage_totals['total_amount']
            is_paid = usage.status == Usage.Status.PAID
            if not is_rest_room_subscription:
                usage_status_cells.append({
                    'room_name': subscription.room.room_name,
                    'description': subscription.description or '',
                    'status': usage.status,
                    'status_label': _('Paid') if is_paid else _('Unpaid'),
                    'status_class': 'dashboard-cell-paid' if is_paid else 'dashboard-cell-new',
                    'total_amount_display': f"{_format_number(usage_totals['total_amount'])} VND",
                    'usage_id': usage.pk,
                    'target_url': reverse('usage_details', kwargs={'pk': usage.pk}),
                })
            else:
                linked_invoice_status = usage.get_restroom_linked_invoice_status()
                shared_restroom_status_cells.append({
                    'room_name': subscription.room.room_name,
                    'description': subscription.description or '',
                    'has_usage': True,
                    'paid_count': linked_invoice_status['paid_linked_usages'],
                    'total_count': linked_invoice_status['total_linked_subscriptions'],
                    'status_class': (
                        'text-bg-success'
                        if linked_invoice_status['total_linked_subscriptions'] > 0
                        and linked_invoice_status['paid_linked_usages'] == linked_invoice_status['total_linked_subscriptions']
                        else 'text-bg-warning'
                        if linked_invoice_status['paid_linked_usages'] > 0
                        else 'text-bg-secondary'
                    ),
                    'usage_label': _('Usage created'),
                    'target_url': reverse('usage_details', kwargs={'pk': usage.pk}),
                })
        else:
            if not is_rest_room_subscription:
                usage_status_cells.append({
                    'room_name': subscription.room.room_name,
                    'description': subscription.description or '',
                    'status': 'missing',
                    'status_label': _('Not created'),
                    'status_class': 'dashboard-cell-missing',
                    'total_amount_display': '',
                    'usage_id': None,
                    'target_url': (
                        f"{reverse('usage_create')}?subscription={subscription.pk}"
                        f"&month={selected_month}&year={selected_year}"
                    ),
                })
            else:
                linked_invoice_status = Usage(
                    subscription=subscription,
                    period=period,
                ).get_restroom_linked_invoice_status()
                shared_restroom_status_cells.append({
                    'room_name': subscription.room.room_name,
                    'description': subscription.description or '',
                    'has_usage': False,
                    'paid_count': linked_invoice_status['paid_linked_usages'],
                    'total_count': linked_invoice_status['total_linked_subscriptions'],
                    'status_class': (
                        'text-bg-success'
                        if linked_invoice_status['total_linked_subscriptions'] > 0
                        and linked_invoice_status['paid_linked_usages'] == linked_invoice_status['total_linked_subscriptions']
                        else 'text-bg-warning'
                        if linked_invoice_status['paid_linked_usages'] > 0
                        else 'text-bg-secondary'
                    ),
                    'usage_label': _('Usage not created yet'),
                    'target_url': (
                        f"{reverse('usage_create')}?subscription={subscription.pk}"
                        f"&month={selected_month}&year={selected_year}"
                    ),
                })

    context = {
        'dashboard_period': period,
        'dashboard_period_label': period.strftime('%m/%Y'),
        'selected_period': period.strftime('%Y-%m'),
        'period_choices': _build_dashboard_period_choices(period),
        'selected_month': selected_month,
        'selected_year': selected_year,
        'summary_groups': [
            {
                'title': _('Subscriptions'),
                'accent_class': 'summary-card-subscriptions',
                'items': [
                    {
                        'label': _('Total subscriptions'),
                        'value': _format_number(len(subscriptions)),
                    },
                ],
            },
            {
                'title': _('Electricity'),
                'accent_class': 'summary-card-electricity',
                'items': [
                    {
                        'label': _('Total electricity consumed'),
                        'value': f"{_format_number(total_electricity_consumed)} kWh",
                    },
                    {
                        'label': _('Total electricity revenue'),
                        'value': f"{_format_number(total_electricity_revenue)} VND",
                    },
                ],
            },
            {
                'title': _('Water'),
                'accent_class': 'summary-card-water',
                'items': [
                    {
                        'label': _('Total water consumed'),
                        'value': f"{_format_number(total_water_consumed)} m3",
                    },
                    {
                        'label': _('Total water revenue'),
                        'value': f"{_format_number(total_water_revenue)} VND",
                    },
                ],
            },
            {
                'title': _('Room'),
                'accent_class': 'summary-card-room',
                'items': [
                    {
                        'label': _('Total room revenue'),
                        'value': f"{_format_number(total_room_revenue)} VND",
                    },
                ],
            },
            {
                'title': _('Total'),
                'accent_class': 'summary-card-total',
                'items': [
                    {
                        'label': _('Grand total amount'),
                        'value': f"{_format_number(total_revenue)} VND",
                    },
                ],
            },
        ],
        'usage_status_cells': sorted(usage_status_cells, key=lambda cell: cell['room_name'].lower()),
        'shared_restroom_status_cells': sorted(shared_restroom_status_cells, key=lambda cell: cell['room_name'].lower()),
    }
    return render(request, 'home.html', context)


def signup_disabled(request):
    raise Http404("Sign up is disabled")
