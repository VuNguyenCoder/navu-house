import os
from pathlib import Path
from decimal import Decimal, InvalidOperation

from django import forms
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import PRICE_FIELD_NAMES, PriceTemplate, Room, Settings, Subscription, Usage, Vehicle


PRICE_WIDGET = forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'})


def format_subscription_label(subscription):
    description = (subscription.description or '').strip()
    if description:
        return f"{subscription.room.room_name} - {description}"
    return subscription.room.room_name


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            if not data:
                return []
            return [single_file_clean(item, initial) for item in data]
        if not data:
            return []
        return [single_file_clean(data, initial)]


class StyledModelForm(forms.ModelForm):
    enable_grouped_number_formatting = True

    @staticmethod
    def _format_grouped_number(value):
        if value in (None, ''):
            return value
        normalized = str(value).replace(',', '').strip()
        if not normalized:
            return ''
        try:
            decimal_value = Decimal(normalized)
        except (InvalidOperation, ValueError):
            return value

        if decimal_value == decimal_value.to_integral():
            return f"{int(decimal_value):,}"
        return format(decimal_value, ',f').rstrip('0').rstrip('.')

    def _enable_grouped_number_formatting(self):
        for field in self.fields.values():
            if isinstance(field, forms.BooleanField):
                continue
            if not isinstance(field, (forms.IntegerField, forms.DecimalField)):
                continue

            if isinstance(field.widget, (forms.HiddenInput, forms.Select, forms.SelectMultiple)):
                continue

            existing_attrs = field.widget.attrs.copy()
            existing_attrs['class'] = existing_attrs.get('class', 'form-control')
            existing_attrs['data-grouped-number'] = 'true'
            existing_attrs['inputmode'] = 'numeric'
            field.widget = forms.TextInput(attrs=existing_attrs)

            original_to_python = field.to_python
            original_prepare_value = field.prepare_value

            def make_to_python(orig):
                def wrapped(value):
                    if isinstance(value, str):
                        value = value.replace(',', '').strip()
                    return orig(value)
                return wrapped

            def make_prepare_value(orig):
                def wrapped(value):
                    prepared = orig(value)
                    return StyledModelForm._format_grouped_number(prepared)
                return wrapped

            field.to_python = make_to_python(original_to_python)
            field.prepare_value = make_prepare_value(original_prepare_value)

    def apply_bootstrap_classes(self):
        for field in self.fields.values():
            widget = field.widget
            existing_class = widget.attrs.get('class', '')
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = f"{existing_class} form-check-input".strip()
            elif 'form-control' not in existing_class and 'form-select' not in existing_class:
                widget.attrs['class'] = f"{existing_class} form-control".strip()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.enable_grouped_number_formatting:
            self._enable_grouped_number_formatting()
        self.apply_bootstrap_classes()


class PriceTemplateForm(StyledModelForm):
    class Meta:
        model = PriceTemplate
        fields = list(PRICE_FIELD_NAMES)
        labels = {
            'room_price': _('Room price (VND / room)'),
            'electricity_price': _('Electricity price (VND / number)'),
            'water_price': _('Water price (VND / cubic meter)'),
            'internet_price': _('Internet price (VND / room)'),
            'cleaning_price': _('Cleaning price (VND / person)'),
            'laundry_price': _('Laundry price (VND / person)'),
        }
        widgets = {field: PRICE_WIDGET for field in PRICE_FIELD_NAMES}

    def clean(self):
        cleaned_data = super().clean()
        for field_name in PRICE_FIELD_NAMES:
            value = cleaned_data.get(field_name)
            if value is None:
                continue
            if value < 0:
                self.add_error(field_name, _('Please enter a non-negative whole number.'))
        return cleaned_data


class SettingsForm(StyledModelForm):
    class Meta:
        model = Settings
        fields = ['payment_period']
        labels = {
            'payment_period': _('Payment period'),
        }
        widgets = {
            'payment_period': forms.NumberInput(attrs={'min': '1', 'max': '28', 'step': '1'}),
        }
        help_texts = {
            'payment_period': _(
                'If today is before this day, the default billing month will be the previous month. From this day onward, the default billing month will be the current month.'
            ),
        }


class RoomForm(StyledModelForm):
    images = MultipleFileField(
        required=False,
        label=_('Room images'),
        help_text=_('Upload up to 10 images in total. On supported devices, you can also capture from the camera.'),
        widget=MultipleFileInput(attrs={'accept': 'image/*', 'capture': 'environment'}),
    )
    remove_image_paths = forms.MultipleChoiceField(
        required=False,
        label=_('Remove existing images'),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Room
        fields = [
            'room_name',
            'type',
            'linked_restroom',
            'description',
            'latest_electricity_reading',
            'latest_water_reading',
        ]
        labels = {
            'room_name': _('Room name'),
            'type': _('Type'),
            'linked_restroom': _('Linked restroom'),
            'description': _('Description'),
            'latest_electricity_reading': _('Latest electricity reading'),
            'latest_water_reading': _('Latest water reading'),
        }
        widgets = {
            'room_name': forms.TextInput(attrs={'placeholder': 'Phòng 101'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'linked_restroom': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'latest_electricity_reading': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
            'latest_water_reading': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
        }
        help_texts = {
            'linked_restroom': _('For unenclosed rooms, optionally choose a restroom room to use as the shared toilet.'),
            'latest_electricity_reading': _(
                'When you create a new subscription, this value is used as the baseline for calculating electricity charges in the following months. It is also updated automatically after each monthly usage record.'
            ),
            'latest_water_reading': _(
                'When you create a new subscription, this value is used as the baseline for calculating water charges in the following months. It is also updated automatically after each monthly usage record.'
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self._original_latest_electricity_reading = self.instance.latest_electricity_reading if self.instance.pk else None
        self._original_latest_water_reading = self.instance.latest_water_reading if self.instance.pk else None
        self.order_fields([
            'room_name',
            'type',
            'linked_restroom',
            'description',
            'remove_image_paths',
            'latest_electricity_reading',
            'latest_water_reading',
            'images',
        ])
        restroom_queryset = Room.objects.filter(type=Room.RoomType.REST).order_by('room_name')
        if self.instance.pk:
            restroom_queryset = restroom_queryset.exclude(pk=self.instance.pk)
        self.fields['linked_restroom'].queryset = restroom_queryset
        existing_paths = self.instance.image_paths or []
        self.fields['remove_image_paths'].choices = [(path, Path(path).name) for path in existing_paths]

    def clean(self):
        cleaned_data = super().clean()
        removed_paths = cleaned_data.get('remove_image_paths') or []
        existing_paths = [path for path in (self.instance.image_paths or []) if path not in removed_paths]
        uploaded_files = cleaned_data.get('images') or []

        if len(existing_paths) + len(uploaded_files) > 10:
            raise forms.ValidationError(_('A room can store at most 10 images.'))

        cleaned_data['uploaded_images'] = uploaded_files
        cleaned_data['remaining_image_paths'] = existing_paths
        return cleaned_data

    def save(self, commit=True):
        removed_paths = set(self.cleaned_data.get('remove_image_paths') or [])
        remaining_paths = list(self.cleaned_data.get('remaining_image_paths', []))

        for path in removed_paths:
            if default_storage.exists(path):
                default_storage.delete(path)

        room_name = self.cleaned_data.get('room_name') or self.instance.room_name or 'room'
        for uploaded_file in self.cleaned_data.get('uploaded_images', []):
            filename = os.path.basename(uploaded_file.name)
            saved_path = default_storage.save(f'rooms/{room_name}/{filename}', uploaded_file)
            remaining_paths.append(saved_path)

        self.instance.image_paths = remaining_paths
        metadata_updated_at = timezone.now()

        if self._original_latest_electricity_reading != self.cleaned_data.get('latest_electricity_reading'):
            self.instance.latest_electricity_reading_source = Room.ReadingUpdateSource.MANUAL
            self.instance.latest_electricity_reading_usage = None
            self.instance.latest_electricity_reading_updated_at = metadata_updated_at
            self.instance.latest_electricity_reading_updated_by = self.user if getattr(self.user, 'is_authenticated', False) else None

        if self._original_latest_water_reading != self.cleaned_data.get('latest_water_reading'):
            self.instance.latest_water_reading_source = Room.ReadingUpdateSource.MANUAL
            self.instance.latest_water_reading_usage = None
            self.instance.latest_water_reading_updated_at = metadata_updated_at
            self.instance.latest_water_reading_updated_by = self.user if getattr(self.user, 'is_authenticated', False) else None

        return super().save(commit=commit)


class SubscriptionForm(StyledModelForm):
    images = MultipleFileField(
        required=False,
        label=_('Subscription images'),
        help_text=_('Upload up to 10 images in total. On supported devices, you can also capture from the camera.'),
        widget=MultipleFileInput(attrs={'accept': 'image/*', 'capture': 'environment'}),
    )
    remove_image_paths = forms.MultipleChoiceField(
        required=False,
        label=_('Remove existing images'),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Subscription
        fields = [
            'description',
            'room',
            'start_date',
            'tenant_count',
            'start_electricity_reading',
            'start_water_reading',
            'deposit_amount',
            *PRICE_FIELD_NAMES,
            'contact_phonenumber',
            'contact_email',
        ]
        labels = {
            'description': _('Description'),
            'room': _('Room'),
            'start_date': _('Rental start date'),
            'tenant_count': _('Number of tenants'),
            'deposit_amount': _('Deposit amount (VND)'),
            'start_electricity_reading': _('Start electricity reading'),
            'start_water_reading': _('Start water reading'),
            'room_price': _('Room price (VND / room)'),
            'electricity_price': _('Electricity price (VND / number)'),
            'water_price': _('Water price (VND / cubic meter)'),
            'internet_price': _('Internet price (VND / room)'),
            'cleaning_price': _('Cleaning price (VND / person)'),
            'laundry_price': _('Laundry price (VND / person)'),
            'contact_phonenumber': _('Contact phone number'),
            'contact_email': _('Contact email'),
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'room': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'tenant_count': forms.NumberInput(attrs={'min': '1', 'step': '1'}),
            'start_electricity_reading': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
            'start_water_reading': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
            'deposit_amount': PRICE_WIDGET,
            'room_price': PRICE_WIDGET,
            'electricity_price': PRICE_WIDGET,
            'water_price': PRICE_WIDGET,
            'internet_price': PRICE_WIDGET,
            'cleaning_price': PRICE_WIDGET,
            'laundry_price': PRICE_WIDGET,
            'contact_phonenumber': forms.TextInput(attrs={'placeholder': '0901234567'}),
            'contact_email': forms.EmailInput(attrs={'placeholder': 'tenant@example.com'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields([
            'room',
            'start_date',
            'tenant_count',
            'description',
            'remove_image_paths',
            'images',
            'start_electricity_reading',
            'start_water_reading',
            'deposit_amount',
            *PRICE_FIELD_NAMES,
            'contact_phonenumber',
            'contact_email',
        ])
        enabled_room_ids = Subscription.objects.filter(
            status=Subscription.Status.ENABLED,
        ).exclude(
            pk=self.instance.pk,
        ).values_list('room_id', flat=True)
        self.fields['room'].queryset = Room.objects.exclude(pk__in=enabled_room_ids).order_by('room_name')
        existing_paths = self.instance.image_paths or []
        self.fields['remove_image_paths'].choices = [(path, Path(path).name) for path in existing_paths]
        if not self.is_bound and not self.instance.pk:
            template = PriceTemplate.get_solo()
            for field in PRICE_FIELD_NAMES:
                self.fields[field].initial = getattr(template, field)
        if not self.is_bound and self.instance.pk and self.instance.room_id:
            self.fields['start_electricity_reading'].initial = self.instance.start_electricity_reading
            self.fields['start_water_reading'].initial = self.instance.start_water_reading

    def clean(self):
        cleaned_data = super().clean()
        removed_paths = cleaned_data.get('remove_image_paths') or []
        existing_paths = [path for path in (self.instance.image_paths or []) if path not in removed_paths]
        uploaded_files = cleaned_data.get('images') or []

        if len(existing_paths) + len(uploaded_files) > 10:
            raise forms.ValidationError(_('A subscription can store at most 10 images.'))

        cleaned_data['uploaded_images'] = uploaded_files
        cleaned_data['remaining_image_paths'] = existing_paths
        return cleaned_data

    def save(self, commit=True):
        removed_paths = set(self.cleaned_data.get('remove_image_paths') or [])
        remaining_paths = list(self.cleaned_data.get('remaining_image_paths', []))

        for path in removed_paths:
            if default_storage.exists(path):
                default_storage.delete(path)

        instance = super().save(commit=False)
        instance.image_paths = remaining_paths

        if commit:
            instance.save()

        subscription_slug = str(instance.pk) if instance.pk else f"draft-{instance.room_id or 'room'}-{(instance.start_date or timezone.localdate()).isoformat()}"
        for uploaded_file in self.cleaned_data.get('uploaded_images', []):
            filename = os.path.basename(uploaded_file.name)
            saved_path = default_storage.save(f'subscriptions/{subscription_slug}/{filename}', uploaded_file)
            remaining_paths.append(saved_path)

        instance.image_paths = remaining_paths
        if commit:
            instance.save(update_fields=['image_paths', 'updated_at'])
        return instance


class VehicleForm(StyledModelForm):
    class Meta:
        model = Vehicle
        fields = [
            'license_plate',
            'subscription',
            'description',
        ]
        labels = {
            'license_plate': _('License plate'),
            'subscription': _('Subscription'),
            'description': _('Description'),
        }
        widgets = {
            'license_plate': forms.TextInput(attrs={'placeholder': '59A-12345'}),
            'subscription': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Subscription.objects.select_related('room').order_by('room__room_name', '-start_date')
        if not self.instance.pk:
            queryset = queryset.filter(status=Subscription.Status.ENABLED)
        self.fields['subscription'].queryset = queryset
        self.fields['subscription'].label_from_instance = format_subscription_label


class UsageForm(StyledModelForm):
    period = forms.DateField(
        required=False,
        widget=forms.HiddenInput(),
    )
    billing_month = forms.ChoiceField(
        label=_('Month'),
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    billing_year = forms.ChoiceField(
        label=_('Year'),
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    electricity_meter_image = forms.FileField(
        required=False,
        label=_('Electricity meter image'),
        help_text=_('Choose an existing image or capture one from the camera on supported devices.'),
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}),
    )
    water_meter_image = forms.FileField(
        required=False,
        label=_('Water meter image'),
        help_text=_('Choose an existing image or capture one from the camera on supported devices.'),
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}),
    )
    remove_electricity_meter_image = forms.BooleanField(
        required=False,
        label=_('Delete current electricity meter image'),
        widget=forms.CheckboxInput(attrs={'class': 'usage-delete-input'}),
    )
    remove_water_meter_image = forms.BooleanField(
        required=False,
        label=_('Delete current water meter image'),
        widget=forms.CheckboxInput(attrs={'class': 'usage-delete-input'}),
    )

    RESTROOM_OPTIONAL_FIELDS = (
        'tenant_count',
        'room_price',
        'internet_price',
        'cleaning_price',
        'laundry_price',
    )

    class Meta:
        model = Usage
        fields = [
            'subscription',
            'period',
            'tenant_count',
            *PRICE_FIELD_NAMES,
            'surcharge_amount',
            'surcharge_description',
            'latest_electricity_reading',
            'latest_water_reading',
        ]
        labels = {
            'subscription': _('Subscription'),
            'tenant_count': _('Number of tenants'),
            'room_price': _('Room price (VND / room)'),
            'electricity_price': _('Electricity price (VND / number)'),
            'water_price': _('Water price (VND / cubic meter)'),
            'internet_price': _('Internet price (VND / room)'),
            'cleaning_price': _('Cleaning price (VND / person)'),
            'laundry_price': _('Laundry price (VND / person)'),
            'surcharge_amount': _('Surcharge amount (VND)'),
            'surcharge_description': _('Surcharge description'),
            'latest_electricity_reading': _('Latest electricity reading'),
            'latest_water_reading': _('Latest water reading'),
        }
        widgets = {
            'subscription': forms.Select(attrs={'class': 'form-select'}),
            'tenant_count': forms.NumberInput(attrs={'min': '1', 'step': '1'}),
            'room_price': PRICE_WIDGET,
            'electricity_price': PRICE_WIDGET,
            'water_price': PRICE_WIDGET,
            'internet_price': PRICE_WIDGET,
            'cleaning_price': PRICE_WIDGET,
            'laundry_price': PRICE_WIDGET,
            'surcharge_amount': PRICE_WIDGET,
            'surcharge_description': forms.Textarea(attrs={'rows': 3}),
            'latest_electricity_reading': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
            'latest_water_reading': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        subscription_queryset = Subscription.objects.select_related('room').order_by('room__room_name', '-start_date')
        self.fields['subscription'].queryset = subscription_queryset
        self.fields['subscription'].label_from_instance = format_subscription_label
        self.subscription_room_names = {
            str(subscription.pk): subscription.room.room_name
            for subscription in subscription_queryset
        }
        self.order_fields([
            'subscription',
            'billing_month',
            'billing_year',
            'tenant_count',
            'room_price',
            'electricity_price',
            'water_price',
            'internet_price',
            'cleaning_price',
            'laundry_price',
            'surcharge_amount',
            'surcharge_description',
            'latest_electricity_reading',
            'electricity_meter_image',
            'remove_electricity_meter_image',
            'latest_water_reading',
            'water_meter_image',
            'remove_water_meter_image',
        ])
        subscription = self._get_selected_subscription()
        self.rest_room_subscription_ids = list(
            Subscription.objects.select_related('room')
            .filter(room__type=Room.RoomType.REST)
            .values_list('pk', flat=True)
        )
        default_billing_period = Settings.get_solo().get_default_usage_period(timezone.localdate())
        default_period = self.instance.period if self.instance.pk and self.instance.period else default_billing_period
        current_year = timezone.localdate().year
        self.fields['billing_month'].choices = [(f'{month:02d}', f'{month:02d}') for month in range(1, 13)]
        self.fields['billing_year'].choices = [(str(year), str(year)) for year in range(current_year - 2, current_year + 6)]
        if not self.is_bound:
            self.fields['period'].initial = default_period
            self.fields['billing_month'].initial = default_period.strftime('%m')
            self.fields['billing_year'].initial = default_period.strftime('%Y')
        if not self.is_bound and subscription and not self.instance.pk:
            latest_usage = subscription.usages.order_by('-period', '-updated_at', '-id').first()
            self.fields['tenant_count'].initial = (
                latest_usage.tenant_count
                if latest_usage and latest_usage.tenant_count is not None
                else subscription.tenant_count
            )
            for field in PRICE_FIELD_NAMES:
                self.fields[field].initial = getattr(subscription, field)
            if latest_usage:
                self.fields['latest_electricity_reading'].initial = subscription.room.latest_electricity_reading
                self.fields['latest_water_reading'].initial = subscription.room.latest_water_reading
            else:
                self.fields['latest_electricity_reading'].initial = subscription.start_electricity_reading
                self.fields['latest_water_reading'].initial = subscription.start_water_reading
        self._apply_rest_room_rules(subscription)
        self.is_paid_locked = bool(self.instance.pk and self.instance.status == Usage.Status.PAID)
        if self.is_paid_locked:
            for field in self.fields.values():
                field.disabled = True
                field.required = False

    def _get_selected_subscription(self):
        if self.instance.pk:
            return self.instance.subscription
        subscription_id = self.initial.get('subscription') or self.data.get('subscription')
        if subscription_id:
            try:
                return Subscription.objects.select_related('room').get(pk=subscription_id)
            except Subscription.DoesNotExist:
                return None
        return None

    def _apply_rest_room_rules(self, subscription):
        is_rest_room = bool(subscription and subscription.room.type == Room.RoomType.REST)
        for field_name in self.RESTROOM_OPTIONAL_FIELDS:
            self.fields[field_name].required = not is_rest_room
        if is_rest_room and not self.is_bound:
            for field_name in self.RESTROOM_OPTIONAL_FIELDS:
                self.fields[field_name].initial = None

    def clean(self):
        cleaned_data = super().clean()
        month_value = cleaned_data.get('billing_month')
        year_value = cleaned_data.get('billing_year')
        if not month_value or not year_value:
            raise forms.ValidationError(_('Billing month is required.'))
        try:
            month = int(month_value)
            year = int(year_value)
            if month < 1 or month > 12 or year < 1:
                raise ValueError
        except ValueError:
            raise forms.ValidationError(_('Invalid billing month selection.'))
        period = timezone.datetime(year=year, month=month, day=1).date()
        cleaned_data['period'] = period
        subscription = cleaned_data.get('subscription') or self._get_selected_subscription()
        is_rest_room = bool(subscription and subscription.room.type == Room.RoomType.REST)
        if is_rest_room:
            for field_name in self.RESTROOM_OPTIONAL_FIELDS:
                cleaned_data[field_name] = None
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        subscription = self.cleaned_data.get('subscription') or instance.subscription
        if subscription and subscription.room.type == Room.RoomType.REST:
            for field_name in self.RESTROOM_OPTIONAL_FIELDS:
                setattr(instance, field_name, None)
        period = self.cleaned_data.get('period') or instance.period
        period_slug = period.strftime('%Y-%m') if period else 'unknown-period'
        subscription_slug = str(subscription.pk) if subscription and subscription.pk else 'subscription'

        electricity_file = self.cleaned_data.get('electricity_meter_image')
        remove_electricity = self.cleaned_data.get('remove_electricity_meter_image')
        if remove_electricity and instance.electricity_meter_image_path:
            if default_storage.exists(instance.electricity_meter_image_path):
                default_storage.delete(instance.electricity_meter_image_path)
            instance.electricity_meter_image_path = ''
        if electricity_file:
            if instance.electricity_meter_image_path and default_storage.exists(instance.electricity_meter_image_path):
                default_storage.delete(instance.electricity_meter_image_path)
            electricity_name = os.path.basename(electricity_file.name)
            instance.electricity_meter_image_path = default_storage.save(
                f'usages/{subscription_slug}/{period_slug}/electricity-{electricity_name}',
                electricity_file,
            )

        water_file = self.cleaned_data.get('water_meter_image')
        remove_water = self.cleaned_data.get('remove_water_meter_image')
        if remove_water and instance.water_meter_image_path:
            if default_storage.exists(instance.water_meter_image_path):
                default_storage.delete(instance.water_meter_image_path)
            instance.water_meter_image_path = ''
        if water_file:
            if instance.water_meter_image_path and default_storage.exists(instance.water_meter_image_path):
                default_storage.delete(instance.water_meter_image_path)
            water_name = os.path.basename(water_file.name)
            instance.water_meter_image_path = default_storage.save(
                f'usages/{subscription_slug}/{period_slug}/water-{water_name}',
                water_file,
            )

        if commit:
            instance.save()
            self.save_m2m()
        return instance
