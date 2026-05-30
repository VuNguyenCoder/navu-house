from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


PRICE_FIELD_NAMES = (
    'room_price',
    'electricity_price',
    'water_price',
    'internet_price',
    'cleaning_price',
    'laundry_price',
)


class PriceTemplate(models.Model):
    name = models.CharField(max_length=100, default='Bang gia chung', unique=True)
    room_price = models.DecimalField(max_digits=12, decimal_places=0, default=2000000)
    electricity_price = models.DecimalField(max_digits=12, decimal_places=0, default=4500)
    water_price = models.DecimalField(max_digits=12, decimal_places=0, default=40000)
    internet_price = models.DecimalField(max_digits=12, decimal_places=0, default=60000)
    cleaning_price = models.DecimalField(max_digits=12, decimal_places=0, default=30000)
    laundry_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(
            name='Bang gia chung',
            defaults={
                'room_price': 2000000,
                'electricity_price': 4500,
                'water_price': 40000,
                'internet_price': 60000,
                'cleaning_price': 30000,
                'laundry_price': 0,
            },
        )[0]


class Room(models.Model):
    room_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    image_paths = models.JSONField(default=list, blank=True)
    latest_electricity_reading = models.PositiveIntegerField(default=0)
    latest_water_reading = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['room_name']

    def __str__(self):
        return self.room_name

    def clean(self):
        super().clean()
        if not isinstance(self.image_paths, list):
            raise ValidationError({'image_paths': _('Image paths must be stored as a list.')})
        if len(self.image_paths) > 5:
            raise ValidationError({'image_paths': _('A room can store at most 5 images.')})
        if any(not isinstance(path, str) or not path.strip() for path in self.image_paths):
            raise ValidationError({'image_paths': _('Each image path must be a non-empty string.')})

    @property
    def image_count(self):
        return len(self.image_paths or [])

    def delete(self, *args, **kwargs):
        for path in self.image_paths or []:
            if default_storage.exists(path):
                default_storage.delete(path)
        super().delete(*args, **kwargs)


class Subscription(models.Model):
    class Status(models.TextChoices):
        ENABLED = 'enabled', _('Enabled')
        DISABLED = 'disabled', _('Disabled')

    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='subscriptions')
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ENABLED)
    start_date = models.DateField()
    start_electricity_reading = models.PositiveIntegerField(default=0)
    start_water_reading = models.PositiveIntegerField(default=0)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    room_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    electricity_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    water_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    internet_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    cleaning_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    laundry_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    contact_phonenumber = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date', 'room__room_name']
        constraints = [
            models.UniqueConstraint(
                fields=['room'],
                condition=Q(status='enabled'),
                name='unique_enabled_subscription_per_room',
            ),
        ]

    def __str__(self):
        return f"{self.room.room_name} - {self.contact_email or '-'}"

    def clean(self):
        super().clean()
        if self.pk:
            previous_status = Subscription.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if previous_status == self.Status.DISABLED and self.status == self.Status.ENABLED:
                raise ValidationError({
                    'status': _('A deactivated subscription cannot be activated again.'),
                })

        if self.status != self.Status.ENABLED or not self.room_id:
            return

        existing_enabled_subscription = Subscription.objects.filter(
            room=self.room,
            status=self.Status.ENABLED,
        )
        if self.pk:
            existing_enabled_subscription = existing_enabled_subscription.exclude(pk=self.pk)

        if existing_enabled_subscription.exists():
            raise ValidationError({
                'room': _('This room already has an active subscription. Disable the current one first.'),
            })

    def save(self, *args, **kwargs):
        if self._state.adding and all(getattr(self, field) in (None, 0, Decimal('0')) for field in PRICE_FIELD_NAMES):
            template = PriceTemplate.get_solo()
            for field in PRICE_FIELD_NAMES:
                setattr(self, field, getattr(template, field))
        super().save(*args, **kwargs)


class Vehicle(models.Model):
    license_plate = models.CharField(max_length=30, unique=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='vehicles')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['license_plate']

    def __str__(self):
        return self.license_plate


class Usage(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='usages')
    period = models.DateField()
    tenant_count = models.PositiveIntegerField(default=1)
    room_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    electricity_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    water_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    internet_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    cleaning_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    laundry_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    latest_electricity_reading = models.PositiveIntegerField(default=0)
    electricity_meter_image_path = models.CharField(max_length=500, blank=True)
    latest_water_reading = models.PositiveIntegerField(default=0)
    water_meter_image_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-period', 'subscription__room__room_name']
        constraints = [
            models.UniqueConstraint(fields=['subscription', 'period'], name='unique_subscription_usage_period'),
        ]

    def __str__(self):
        return f"{self.subscription.room.room_name} - {self.period:%m/%Y}"

    def clean(self):
        super().clean()
        if self.period and self.period.day != 1:
            raise ValidationError({'period': _('Please select month and year only.')})

    def save(self, *args, **kwargs):
        if self.period:
            self.period = self.period.replace(day=1)
        if self._state.adding and all(getattr(self, field) in (None, 0, Decimal('0')) for field in PRICE_FIELD_NAMES):
            for field in PRICE_FIELD_NAMES:
                setattr(self, field, getattr(self.subscription, field))
        super().save(*args, **kwargs)
        self._sync_room_readings_for_room(self.subscription.room)

    def delete(self, *args, **kwargs):
        room = self.subscription.room
        super().delete(*args, **kwargs)
        self._sync_room_readings_for_room(room)

    @staticmethod
    def _sync_room_readings_for_room(room):
        latest_usage = Usage.objects.filter(subscription__room=room).order_by('-period', '-updated_at', '-id').first()
        if not latest_usage:
            return
        if (
            room.latest_electricity_reading != latest_usage.latest_electricity_reading
            or room.latest_water_reading != latest_usage.latest_water_reading
        ):
            room.latest_electricity_reading = latest_usage.latest_electricity_reading
            room.latest_water_reading = latest_usage.latest_water_reading
            room.save(update_fields=['latest_electricity_reading', 'latest_water_reading', 'updated_at'])
