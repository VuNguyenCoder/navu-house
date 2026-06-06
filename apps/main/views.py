from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
import os
from django.conf import settings

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import PriceTemplateForm, RoomForm, SettingsForm, SubscriptionForm, UsageForm, VehicleForm
from .models import PriceTemplate, Room, Settings, Subscription, Usage, Vehicle


def user_can_manage_pricing(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, 'role', None) == 'operator')


def usage_is_locked(usage):
    return usage.status == Usage.Status.PAID


def get_previous_usage_context(subscription, period, exclude_usage_id=None):
    previous_usage = (
        Usage.objects.filter(subscription=subscription, period__lt=period)
        .exclude(pk=exclude_usage_id)
        .order_by('-period', '-updated_at', '-id')
        .first()
    )

    if previous_usage:
        return {
            'previous_electricity_reading': previous_usage.latest_electricity_reading,
            'previous_water_reading': previous_usage.latest_water_reading,
            'is_first_month': False,
        }

    return {
        'previous_electricity_reading': subscription.start_electricity_reading,
        'previous_water_reading': subscription.start_water_reading,
        'is_first_month': True,
    }


def get_subscription_edit_url(subscription_id=None):
    base_url = reverse('subscription_list')
    if subscription_id:
        return f"{reverse('subscription_details', kwargs={'pk': subscription_id})}#usage-records"
    return base_url


def get_subscription_vehicle_url(subscription_id=None):
    base_url = reverse('subscription_list')
    if subscription_id:
        return f"{reverse('subscription_details', kwargs={'pk': subscription_id})}#vehicle-records"
    return base_url


def _format_file_size(size_bytes):
    size = float(size_bytes)
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == 'B':
                return f'{int(size)} {unit}'
            return f'{size:.1f} {unit}'
        size /= 1024


def get_backup_history_items():
    backup_root = Path(settings.BACKUP_HISTORY_ROOT)
    if not backup_root.exists() or not backup_root.is_dir():
        return []

    items = []
    for backup_file in sorted(backup_root.glob('*.tar.gz'), key=lambda item: item.stat().st_mtime, reverse=True):
        stat = backup_file.stat()
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc)
        items.append({
            'name': backup_file.name,
            'size_bytes': stat.st_size,
            'size_display': _format_file_size(stat.st_size),
            'modified_at': modified_at,
        })
    return items


def get_backup_trigger_file():
    return Path(settings.BACKUP_TRIGGER_DIR) / 'request-now'


def get_backup_running_file():
    return Path(settings.BACKUP_TRIGGER_DIR) / 'running'


def get_backup_delete_request_dir():
    return Path(settings.BACKUP_TRIGGER_DIR) / 'delete-requests'


def get_usage_period_from_form(form, fallback=None):
    if form is None:
        return fallback or date.today().replace(day=1)

    if form.is_bound:
        month_value = form.data.get('billing_month')
        year_value = form.data.get('billing_year')
        try:
            if month_value and year_value:
                return date(year=int(year_value), month=int(month_value), day=1)
        except ValueError:
            pass

    if getattr(form.instance, 'pk', None) and form.instance.period:
        return form.instance.period

    field_initial = form.fields.get('period').initial if form.fields.get('period') else None
    if field_initial:
        return field_initial

    return fallback or date.today().replace(day=1)


def get_room_subscription_for_period(room, period):
    usage_subscription_id = (
        Usage.objects.filter(subscription__room=room, period=period)
        .order_by('-updated_at', '-id')
        .values_list('subscription_id', flat=True)
        .first()
    )
    if usage_subscription_id:
        return Subscription.objects.select_related('room').filter(pk=usage_subscription_id).first()

    started_queryset = room.subscriptions.filter(start_date__lte=period).order_by('-start_date', '-updated_at', '-id')
    enabled_started = started_queryset.filter(status=Subscription.Status.ENABLED).first()
    if enabled_started:
        return enabled_started

    fallback_enabled = room.subscriptions.filter(status=Subscription.Status.ENABLED).order_by('-start_date', '-updated_at', '-id').first()
    if fallback_enabled:
        return fallback_enabled

    return room.subscriptions.order_by('-start_date', '-updated_at', '-id').first()


def get_subscription_tenant_count_for_period(subscription, period):
    period_usage = subscription.usages.filter(period=period).order_by('-updated_at', '-id').first()
    if period_usage and period_usage.tenant_count is not None:
        return period_usage.tenant_count

    previous_usage = subscription.usages.filter(period__lt=period).order_by('-period', '-updated_at', '-id').first()
    if previous_usage and previous_usage.tenant_count is not None:
        return previous_usage.tenant_count

    latest_usage = subscription.usages.order_by('-period', '-updated_at', '-id').first()
    if latest_usage and latest_usage.tenant_count is not None:
        return latest_usage.tenant_count

    return subscription.tenant_count or 0


def get_linked_restroom_usage_context(subscription, period):
    room = subscription.room
    if room.type != Room.RoomType.UNENCLOSED or not room.linked_restroom_id:
        return None

    linked_restroom = room.linked_restroom
    other_linked_tenants = 0
    other_linked_subscriptions = []
    has_incomplete_other_usage = False
    linked_rooms = Room.objects.filter(type=Room.RoomType.UNENCLOSED, linked_restroom=linked_restroom).order_by('room_name')
    for linked_room in linked_rooms:
        linked_subscription = get_room_subscription_for_period(linked_room, period)
        if not linked_subscription or linked_subscription.pk == subscription.pk:
            continue
        period_usage = linked_subscription.usages.filter(period=period).order_by('-updated_at', '-id').first()
        tenant_count = get_subscription_tenant_count_for_period(linked_subscription, period)
        other_linked_tenants += tenant_count
        if not period_usage:
            has_incomplete_other_usage = True
        other_linked_subscriptions.append({
            'subscription_id': linked_subscription.pk,
            'room_name': linked_subscription.room.room_name,
            'subscription_description': linked_subscription.description or '',
            'tenant_count': tenant_count,
            'has_usage_for_period': bool(period_usage),
        })

    context = {
        'is_applicable': True,
        'restroom_room_name': linked_restroom.room_name,
        'restroom_room_id': linked_restroom.pk,
        'period_label': period.strftime('%m/%Y'),
        'other_linked_tenants': other_linked_tenants,
        'other_linked_subscriptions': other_linked_subscriptions,
        'has_incomplete_other_usage': has_incomplete_other_usage,
        'has_subscription': False,
        'has_usage': False,
    }

    restroom_subscription = get_room_subscription_for_period(linked_restroom, period)
    if not restroom_subscription:
        return context

    context['has_subscription'] = True
    context['restroom_subscription_id'] = restroom_subscription.pk

    restroom_usage = (
        Usage.objects.filter(subscription=restroom_subscription, period=period)
        .order_by('-updated_at', '-id')
        .first()
    )
    if not restroom_usage:
        return context

    previous_context = get_previous_usage_context(restroom_subscription, period, exclude_usage_id=restroom_usage.pk)
    previous_electricity = previous_context['previous_electricity_reading']
    previous_water = previous_context['previous_water_reading']
    electricity_consumed = max(restroom_usage.latest_electricity_reading - previous_electricity, 0)
    water_consumed = max(restroom_usage.latest_water_reading - previous_water, 0)
    electricity_amount = Decimal(electricity_consumed) * Decimal(restroom_usage.electricity_price or 0)
    water_amount = Decimal(water_consumed) * Decimal(restroom_usage.water_price or 0)

    context.update({
        'has_usage': True,
        'restroom_usage_id': restroom_usage.pk,
        'previous_electricity_reading': previous_electricity,
        'latest_electricity_reading': restroom_usage.latest_electricity_reading,
        'electricity_consumed': electricity_consumed,
        'electricity_unit_price': Decimal(restroom_usage.electricity_price or 0),
        'electricity_amount': electricity_amount,
        'previous_water_reading': previous_water,
        'latest_water_reading': restroom_usage.latest_water_reading,
        'water_consumed': water_consumed,
        'water_unit_price': Decimal(restroom_usage.water_price or 0),
        'water_amount': water_amount,
    })
    return context


def serialize_linked_restroom_usage_context(context):
    if context is None:
        return None

    def normalize(value):
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, Decimal):
            if value == value.to_integral():
                return int(value)
            return float(value)
        return value

    return {key: normalize(value) for key, value in context.items()}


def build_subscription_usage_rows(subscription):
    usages = list(subscription.usages.order_by('-period', '-updated_at', '-id'))
    usage_rows = []

    for index, usage in enumerate(usages, start=1):
        previous_context = get_previous_usage_context(subscription, usage.period, exclude_usage_id=usage.pk)
        previous_electricity = previous_context['previous_electricity_reading']
        previous_water = previous_context['previous_water_reading']
        electricity_consumed = max(usage.latest_electricity_reading - previous_electricity, 0)
        water_consumed = max(usage.latest_water_reading - previous_water, 0)
        tenant_count = usage.tenant_count or 0
        linked_restroom_context = get_linked_restroom_usage_context(subscription, usage.period)
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
        total_amount = (
            Decimal(usage.room_price or 0)
            + Decimal(electricity_consumed) * Decimal(usage.electricity_price)
            + Decimal(water_consumed) * Decimal(usage.water_price)
            + Decimal(usage.internet_price or 0)
            + Decimal(tenant_count) * Decimal(usage.cleaning_price or 0)
            + Decimal(tenant_count) * Decimal(usage.laundry_price or 0)
            + Decimal(usage.surcharge_amount or 0)
            + linked_restroom_electricity_amount
            + linked_restroom_water_amount
        )
        usage_rows.append({
            'index': index,
            'usage': usage,
            'electricity_consumed': electricity_consumed,
            'water_consumed': water_consumed,
            'total_amount': total_amount,
            'total_amount_display': f'{total_amount:,.0f}',
        })

    return usage_rows


class OperatorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = 'account_login'
    raise_exception = True

    def test_func(self):
        return user_can_manage_pricing(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied(_("You do not have permission to access this page."))
        return super().handle_no_permission()


class ManagementDeleteView(OperatorRequiredMixin, DeleteView):
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.get_success_message())
        return response

    def get_success_message(self):
        return _("Deleted successfully.")


class RoomListView(OperatorRequiredMixin, ListView):
    model = Room
    template_name = 'main/room_list.html'
    context_object_name = 'rooms'


class RoomCreateView(OperatorRequiredMixin, SuccessMessageMixin, CreateView):
    model = Room
    form_class = RoomForm
    template_name = 'main/room_form.html'
    success_url = reverse_lazy('room_list')
    success_message = _('Room created successfully.')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': _('Add room'),
            'submit_label': _('Create room'),
            'cancel_url': self.success_url,
        })
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class RoomUpdateView(OperatorRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Room
    form_class = RoomForm
    template_name = 'main/room_form.html'
    success_message = _('Room updated successfully.')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': _('Room details'),
            'submit_label': _('Save changes'),
            'cancel_url': reverse('room_list'),
        })
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('room_details', kwargs={'pk': self.object.pk})


class RoomDeleteView(ManagementDeleteView):
    model = Room
    template_name = 'main/confirm_delete.html'
    success_url = reverse_lazy('room_list')

    def get_success_message(self):
        return _('Room deleted successfully.')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': _('Delete room'),
            'object_label': self.object.room_name,
            'cancel_url': self.success_url,
            'breadcrumb_list_url': reverse('room_list'),
            'breadcrumb_list_label': _('Rooms'),
        })
        return context

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                _('This room cannot be deleted because it still has subscriptions attached.'),
            )
            return redirect(self.success_url)


class VehicleListView(OperatorRequiredMixin, ListView):
    model = Vehicle
    template_name = 'main/vehicle_list.html'
    context_object_name = 'vehicles'

    def get_queryset(self):
        queryset = Vehicle.objects.select_related('subscription', 'subscription__room')
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(license_plate__icontains=query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '').strip()
        return context


class VehicleCreateView(OperatorRequiredMixin, SuccessMessageMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'main/vehicle_form.html'
    success_url = reverse_lazy('vehicle_list')
    success_message = _('Vehicle created successfully.')

    def get_initial(self):
        initial = super().get_initial()
        subscription_id = self.request.GET.get('subscription')
        month_value = self.request.GET.get('month')
        year_value = self.request.GET.get('year')
        if subscription_id:
            initial['subscription'] = subscription_id
        try:
            if month_value and year_value:
                initial['period'] = date(year=int(year_value), month=int(month_value), day=1)
        except ValueError:
            pass
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription_id = self.request.GET.get('subscription')
        selected_subscription = None
        if subscription_id:
            selected_subscription = Subscription.objects.select_related('room').filter(pk=subscription_id).first()
        context.update({
            'page_title': _('Add vehicle'),
            'submit_label': _('Create vehicle'),
            'cancel_url': get_subscription_vehicle_url(subscription_id) if subscription_id else self.success_url,
            'selected_subscription': selected_subscription,
        })
        return context

    def get_success_url(self):
        return get_subscription_vehicle_url(self.object.subscription_id)


class VehicleUpdateView(OperatorRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'main/vehicle_form.html'
    success_message = _('Vehicle updated successfully.')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': _('Vehicle details'),
            'submit_label': _('Save changes'),
            'cancel_url': get_subscription_vehicle_url(self.object.subscription_id),
            'selected_subscription': self.object.subscription,
        })
        return context

    def get_success_url(self):
        return reverse('vehicle_details', kwargs={'pk': self.object.pk})


class VehicleDeleteView(ManagementDeleteView):
    model = Vehicle
    template_name = 'main/confirm_delete.html'
    success_url = reverse_lazy('vehicle_list')

    def get_success_message(self):
        return _('Vehicle deleted successfully.')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': _('Delete vehicle'),
            'object_label': self.object.license_plate,
            'cancel_url': get_subscription_vehicle_url(self.object.subscription_id),
            'breadcrumb_list_url': reverse('subscription_details', kwargs={'pk': self.object.subscription_id}),
            'breadcrumb_list_label': _('Subscription details'),
            'breadcrumb_parent_label': self.object.subscription.room.room_name,
        })
        return context

    def get_success_url(self):
        return get_subscription_vehicle_url(self.object.subscription_id)


class SubscriptionListView(OperatorRequiredMixin, ListView):
    model = Subscription
    template_name = 'main/subscription_list.html'
    context_object_name = 'subscriptions'

    def get_queryset(self):
        queryset = Subscription.objects.select_related('room').prefetch_related('vehicles')

        room_id = self.request.GET.get('room', '').strip()
        status = self.request.GET.get('status', Subscription.Status.ENABLED).strip() or Subscription.Status.ENABLED
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()

        if room_id:
            queryset = queryset.filter(room_id=room_id)
        if status in {Subscription.Status.ENABLED, Subscription.Status.DISABLED}:
            queryset = queryset.filter(status=status)
        if date_from:
            queryset = queryset.filter(start_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(start_date__lte=date_to)

        return queryset.order_by('room__room_name', '-start_date', '-updated_at', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'filter_rooms': Room.objects.order_by('room_name'),
            'selected_room': self.request.GET.get('room', '').strip(),
            'selected_status': self.request.GET.get('status', Subscription.Status.ENABLED).strip() or Subscription.Status.ENABLED,
            'selected_date_from': self.request.GET.get('date_from', '').strip(),
            'selected_date_to': self.request.GET.get('date_to', '').strip(),
        })
        return context


class SubscriptionCreateView(OperatorRequiredMixin, SuccessMessageMixin, CreateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name = 'main/subscription_form.html'
    success_url = reverse_lazy('subscription_list')
    success_message = _('Subscription created successfully.')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': _('Add subscription'),
            'submit_label': _('Create subscription'),
            'cancel_url': self.success_url,
        })
        return context

    def form_valid(self, form):
        form.instance.status = Subscription.Status.ENABLED
        return super().form_valid(form)


class SubscriptionUpdateView(OperatorRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name = 'main/subscription_form.html'
    success_message = _('Subscription updated successfully.')

    def get_queryset(self):
        return Subscription.objects.select_related('room').prefetch_related('usages')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': _('Subscription details'),
            'submit_label': _('Save changes'),
            'cancel_url': reverse('subscription_list'),
            'subscription_usage_rows': build_subscription_usage_rows(self.object),
            'subscription_vehicles': self.object.vehicles.order_by('license_plate'),
        })
        return context

    def get_success_url(self):
        return reverse('subscription_details', kwargs={'pk': self.object.pk})


class SubscriptionDeleteView(ManagementDeleteView):
    model = Subscription
    template_name = 'main/confirm_delete.html'
    success_url = reverse_lazy('subscription_list')

    def get_success_message(self):
        return _('Subscription deleted successfully.')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': _('Delete subscription'),
            'object_label': str(self.object),
            'cancel_url': self.success_url,
            'breadcrumb_list_url': reverse('subscription_list'),
            'breadcrumb_list_label': _('Subscriptions'),
            'breadcrumb_parent_label': self.object.room.room_name,
        })
        return context


@login_required(login_url='account_login')
def subscription_deactivate(request, pk):
    if not user_can_manage_pricing(request.user):
        raise PermissionDenied(_("You do not have permission to access this page."))
    if request.method != 'POST':
        return redirect('subscription_details', pk=pk)

    subscription = get_object_or_404(Subscription, pk=pk)
    if subscription.status == Subscription.Status.ENABLED:
        subscription.status = Subscription.Status.DISABLED
        subscription.save(update_fields=['status', 'updated_at'])
        messages.success(request, _('Subscription deactivated successfully.'))

    return redirect('subscription_details', pk=subscription.pk)


class UsageListView(OperatorRequiredMixin, ListView):
    model = Usage
    template_name = 'main/usage_list.html'
    context_object_name = 'usages'

    def get(self, request, *args, **kwargs):
        return redirect('subscription_list')


class UsageCreateView(OperatorRequiredMixin, SuccessMessageMixin, CreateView):
    model = Usage
    form_class = UsageForm
    template_name = 'main/usage_form.html'
    success_message = _('Usage record created successfully.')

    def get_initial(self):
        initial = super().get_initial()
        subscription_id = self.request.GET.get('subscription')
        if subscription_id:
            initial['subscription'] = subscription_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get('form')
        subscription = form._get_selected_subscription() if form else None
        period = get_usage_period_from_form(form)
        usage_context = get_previous_usage_context(subscription, period) if subscription else None
        context.update({
            'page_title': _('Add usage record'),
            'submit_label': _('Create usage record'),
            'cancel_url': get_subscription_edit_url(subscription.pk if subscription else None),
            'usage_previous_context': usage_context,
            'selected_subscription': subscription,
            'rest_room_subscription_ids': form.rest_room_subscription_ids if form else [],
            'subscription_room_names': form.subscription_room_names if form else {},
        })
        return context

    def get_success_url(self):
        return get_subscription_edit_url(self.object.subscription_id)


class UsageUpdateView(OperatorRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Usage
    form_class = UsageForm
    template_name = 'main/usage_form.html'
    success_message = _('Usage record updated successfully.')

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if usage_is_locked(self.object):
            messages.error(request, _('A paid usage record cannot be edited.'))
            return redirect('usage_details', pk=self.object.pk)
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get('form')
        period = get_usage_period_from_form(form, fallback=self.object.period)
        usage_context = get_previous_usage_context(self.object.subscription, period, exclude_usage_id=self.object.pk)
        context.update({
            'page_title': _('Usage record details'),
            'submit_label': _('Save changes'),
            'cancel_url': get_subscription_edit_url(self.object.subscription_id),
            'usage_previous_context': usage_context,
            'selected_subscription': self.object.subscription,
            'rest_room_subscription_ids': form.rest_room_subscription_ids if form else [],
            'subscription_room_names': form.subscription_room_names if form else {},
            'usage_is_paid': usage_is_locked(self.object),
        })
        return context

    def get_success_url(self):
        return reverse('usage_details', kwargs={'pk': self.object.pk})


class UsageDeleteView(ManagementDeleteView):
    model = Usage
    template_name = 'main/confirm_delete.html'

    def get_success_message(self):
        return _('Usage record deleted successfully.')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if usage_is_locked(self.object):
            messages.error(request, _('A paid usage record cannot be deleted.'))
            return redirect('usage_details', pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if usage_is_locked(self.object):
            messages.error(request, _('A paid usage record cannot be deleted.'))
            return redirect('usage_details', pk=self.object.pk)
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': _('Delete usage record'),
            'object_label': str(self.object),
            'cancel_url': get_subscription_edit_url(self.object.subscription_id),
            'breadcrumb_list_url': reverse('subscription_details', kwargs={'pk': self.object.subscription_id}),
            'breadcrumb_list_label': _('Subscription details'),
            'breadcrumb_parent_label': self.object.subscription.room.room_name,
        })
        return context

    def get_success_url(self):
        return get_subscription_edit_url(self.object.subscription_id)


@login_required(login_url='account_login')
def price_template(request):
    if not (request.user.is_superuser or request.user.role == 'operator'):
        raise PermissionDenied(_("You do not have permission to access the price template page."))

    instance = PriceTemplate.get_solo()

    if request.method == 'POST':
        form = PriceTemplateForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Price template updated successfully.'))
            return redirect('price_template')
    else:
        form = PriceTemplateForm(instance=instance)

    return render(
        request,
        'price_template.html',
        {
            'form': form,
            'price_template': instance,
        },
    )


@login_required(login_url='account_login')
def settings_page(request):
    if not user_can_manage_pricing(request.user):
        raise PermissionDenied(_("You do not have permission to access the settings page."))

    instance = Settings.get_solo()

    if request.method == 'POST':
        form = SettingsForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Settings updated successfully.'))
            return redirect('settings_page')
    else:
        form = SettingsForm(instance=instance)

    return render(
        request,
        'setting.html',
        {
            'form': form,
            'app_settings': instance,
        },
    )


@login_required(login_url='account_login')
def backup_history(request):
    if not user_can_manage_pricing(request.user):
        raise PermissionDenied(_("You do not have permission to access the backup page."))

    trigger_file = get_backup_trigger_file()
    running_file = get_backup_running_file()
    return render(
        request,
        'backup_history.html',
        {
            'backup_items': get_backup_history_items(),
            'backup_trigger_pending': trigger_file.exists() or running_file.exists(),
            'backup_is_running': running_file.exists(),
            'backup_display_path': settings.BACKUP_DISPLAY_PATH,
        },
    )


@login_required(login_url='account_login')
def backup_run_now(request):
    if not user_can_manage_pricing(request.user):
        raise PermissionDenied(_("You do not have permission to run backups."))
    if request.method != 'POST':
        return redirect('backup_history')

    trigger_file = get_backup_trigger_file()
    running_file = get_backup_running_file()
    trigger_file.parent.mkdir(parents=True, exist_ok=True)

    if trigger_file.exists() or running_file.exists():
        messages.info(request, _('A backup request is already queued.'))
        return redirect('backup_history')

    trigger_file.write_text(
        f"user={request.user.username or request.user.pk}\nrequested_at={datetime.now(dt_timezone.utc).isoformat()}\n",
        encoding='utf-8',
    )
    messages.success(request, _('Backup request queued successfully.'))
    return redirect('backup_history')


@login_required(login_url='account_login')
def backup_delete(request):
    if not user_can_manage_pricing(request.user):
        raise PermissionDenied(_("You do not have permission to delete backups."))
    if request.method != 'POST':
        return redirect('backup_history')

    requested_name = (request.POST.get('file_name') or '').strip()
    safe_name = Path(requested_name).name
    if not safe_name or safe_name != requested_name or not safe_name.endswith('.tar.gz'):
        messages.error(request, _('Invalid backup file name.'))
        return redirect('backup_history')

    backup_file = Path(settings.BACKUP_HISTORY_ROOT) / safe_name
    if not backup_file.exists():
        messages.error(request, _('Backup file not found.'))
        return redirect('backup_history')

    if os.access(backup_file, os.W_OK) and os.access(backup_file.parent, os.W_OK):
        backup_file.unlink()
        messages.success(request, _('Backup deleted successfully.'))
        return redirect('backup_history')

    delete_request_dir = get_backup_delete_request_dir()
    delete_request_dir.mkdir(parents=True, exist_ok=True)
    queued_request = delete_request_dir / f'{safe_name}.request'
    if queued_request.exists():
        messages.info(request, _('A delete request for this backup is already queued.'))
        return redirect('backup_history')

    queued_request.write_text(safe_name, encoding='utf-8')
    messages.success(request, _('Backup delete request queued successfully.'))
    return redirect('backup_history')


@login_required(login_url='account_login')
def usage_pricing_context(request):
    if not user_can_manage_pricing(request.user):
        raise PermissionDenied(_("You do not have permission to access this page."))

    subscription_id = request.GET.get('subscription')
    month = request.GET.get('month')
    year = request.GET.get('year')
    usage_id = request.GET.get('usage_id')

    if not subscription_id or not month or not year:
        return JsonResponse({'error': 'missing_parameters'}, status=400)

    try:
        subscription = Subscription.objects.select_related('room').get(pk=subscription_id)
        period = date(year=int(year), month=int(month), day=1)
    except (Subscription.DoesNotExist, ValueError):
        return JsonResponse({'error': 'invalid_parameters'}, status=400)

    context = get_previous_usage_context(subscription, period, exclude_usage_id=usage_id)
    context['linked_restroom_usage_context'] = serialize_linked_restroom_usage_context(
        get_linked_restroom_usage_context(subscription, period)
    )
    return JsonResponse(context)


@login_required(login_url='account_login')
def usage_list_redirect(request):
    return redirect('subscription_list')


@login_required(login_url='account_login')
def usage_mark_paid(request, pk):
    if not user_can_manage_pricing(request.user):
        raise PermissionDenied(_("You do not have permission to access this page."))
    if request.method != 'POST':
        return redirect('usage_details', pk=pk)

    usage = get_object_or_404(Usage, pk=pk)
    if usage.status != Usage.Status.PAID:
        usage.status = Usage.Status.PAID
        usage.save(update_fields=['status', 'updated_at'])
        messages.success(request, _('Usage record marked as Paid successfully.'))

    return redirect('usage_details', pk=usage.pk)
