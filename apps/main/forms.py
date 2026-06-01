import os
from pathlib import Path
from decimal import Decimal, InvalidOperation

from django import forms
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import PRICE_FIELD_NAMES, PriceTemplate, Room, Subscription, Usage, Vehicle


PRICE_WIDGET = forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'})


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


class RoomForm(StyledModelForm):
    images = MultipleFileField(
        required=False,
        label=_('Room images'),
        help_text=_('Upload up to 5 images in total. On supported devices, you can also capture from the camera.'),
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
            'description',
            'latest_electricity_reading',
            'latest_water_reading',
        ]
        labels = {
            'room_name': _('Room name'),
            'description': _('Description'),
            'latest_electricity_reading': _('Latest electricity reading'),
            'latest_water_reading': _('Latest water reading'),
        }
        widgets = {
            'room_name': forms.TextInput(attrs={'placeholder': 'Phòng 101'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'latest_electricity_reading': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
            'latest_water_reading': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
        }
        help_texts = {
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
            'description',
            'remove_image_paths',
            'latest_electricity_reading',
            'latest_water_reading',
            'images',
        ])
        existing_paths = self.instance.image_paths or []
        self.fields['remove_image_paths'].choices = [(path, Path(path).name) for path in existing_paths]

    def clean(self):
        cleaned_data = super().clean()
        removed_paths = cleaned_data.get('remove_image_paths') or []
        existing_paths = [path for path in (self.instance.image_paths or []) if path not in removed_paths]
        uploaded_files = cleaned_data.get('images') or []

        if len(existing_paths) + len(uploaded_files) > 5:
            raise forms.ValidationError(_('A room can store at most 5 images.'))

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
    class Meta:
        model = Subscription
        fields = [
            'description',
            'room',
            'start_date',
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
        enabled_room_ids = Subscription.objects.filter(
            status=Subscription.Status.ENABLED,
        ).exclude(
            pk=self.instance.pk,
        ).values_list('room_id', flat=True)
        self.fields['room'].queryset = Room.objects.exclude(pk__in=enabled_room_ids).order_by('room_name')
        if not self.is_bound and not self.instance.pk:
            template = PriceTemplate.get_solo()
            for field in PRICE_FIELD_NAMES:
                self.fields[field].initial = getattr(template, field)
        if not self.is_bound and self.instance.pk and self.instance.room_id:
            self.fields['start_electricity_reading'].initial = self.instance.start_electricity_reading
            self.fields['start_water_reading'].initial = self.instance.start_water_reading


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
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*', 'capture': 'environment'}),
    )
    water_meter_image = forms.FileField(
        required=False,
        label=_('Water meter image'),
        help_text=_('Choose an existing image or capture one from the camera on supported devices.'),
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*', 'capture': 'environment'}),
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

    class Meta:
        model = Usage
        fields = [
            'subscription',
            'period',
            'tenant_count',
            *PRICE_FIELD_NAMES,
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
            'latest_electricity_reading': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
            'latest_water_reading': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
            'latest_electricity_reading',
            'electricity_meter_image',
            'remove_electricity_meter_image',
            'latest_water_reading',
            'water_meter_image',
            'remove_water_meter_image',
        ])
        subscription = self._get_selected_subscription()
        default_period = self.instance.period if self.instance.pk and self.instance.period else timezone.localdate().replace(day=1)
        current_year = timezone.localdate().year
        self.fields['billing_month'].choices = [(f'{month:02d}', f'{month:02d}') for month in range(1, 13)]
        self.fields['billing_year'].choices = [(str(year), str(year)) for year in range(current_year - 2, current_year + 6)]
        if not self.is_bound:
            self.fields['period'].initial = default_period
            self.fields['billing_month'].initial = default_period.strftime('%m')
            self.fields['billing_year'].initial = default_period.strftime('%Y')
        if not self.is_bound and subscription and not self.instance.pk:
            latest_usage = subscription.usages.order_by('-period', '-updated_at', '-id').first()
            self.fields['tenant_count'].initial = latest_usage.tenant_count if latest_usage else 1
            for field in PRICE_FIELD_NAMES:
                self.fields[field].initial = getattr(subscription, field)
            if latest_usage:
                self.fields['latest_electricity_reading'].initial = subscription.room.latest_electricity_reading
                self.fields['latest_water_reading'].initial = subscription.room.latest_water_reading
            else:
                self.fields['latest_electricity_reading'].initial = subscription.start_electricity_reading
                self.fields['latest_water_reading'].initial = subscription.start_water_reading

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
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        subscription = self.cleaned_data.get('subscription') or instance.subscription
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
