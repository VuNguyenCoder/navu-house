from datetime import date
from decimal import Decimal

from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Now
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


class Settings(models.Model):
    payment_period = models.PositiveSmallIntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text=_('If today is before this day, the default billing month will be the previous month.'),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Settings')
        verbose_name_plural = _('Settings')

    def __str__(self):
        return _('Settings')

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1, defaults={'payment_period': 15})[0]

    def get_default_usage_period(self, today=None):
        if today is None:
            from django.utils import timezone
            today = timezone.localdate()
        if today.day < self.payment_period:
            if today.month == 1:
                return date(year=today.year - 1, month=12, day=1)
            return date(year=today.year, month=today.month - 1, day=1)
        return today.replace(day=1)


class Room(models.Model):
    class RoomType(models.TextChoices):
        ENCLOSED = 'enclosed', _('Enclosed')
        UNENCLOSED = 'unenclosed', _('Unenclosed')
        REST = 'rest', _('Rest')

    class ReadingUpdateSource(models.TextChoices):
        MANUAL = 'manual', _('Manual update on Room details')
        USAGE = 'usage', _('Automatic update from subscription usage')

    room_name = models.CharField(max_length=50, unique=True)
    type = models.CharField(max_length=20, choices=RoomType.choices, default=RoomType.ENCLOSED)
    linked_restroom = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='dependent_rooms',
    )
    description = models.TextField(blank=True)
    image_paths = models.JSONField(default=list, blank=True)
    latest_electricity_reading = models.PositiveIntegerField(default=0)
    latest_water_reading = models.PositiveIntegerField(default=0)
    latest_electricity_reading_updated_at = models.DateTimeField(null=True, blank=True)
    latest_water_reading_updated_at = models.DateTimeField(null=True, blank=True)
    latest_electricity_reading_source = models.CharField(
        max_length=20,
        choices=ReadingUpdateSource.choices,
        blank=True,
    )
    latest_water_reading_source = models.CharField(
        max_length=20,
        choices=ReadingUpdateSource.choices,
        blank=True,
    )
    latest_electricity_reading_usage = models.ForeignKey(
        'Usage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    latest_water_reading_usage = models.ForeignKey(
        'Usage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    latest_electricity_reading_updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    latest_water_reading_updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
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
        if len(self.image_paths) > 10:
            raise ValidationError({'image_paths': _('A room can store at most 10 images.')})
        if any(not isinstance(path, str) or not path.strip() for path in self.image_paths):
            raise ValidationError({'image_paths': _('Each image path must be a non-empty string.')})
        if self.type != self.RoomType.UNENCLOSED and self.linked_restroom_id:
            raise ValidationError({
                'linked_restroom': _('Only unenclosed rooms can be linked to a shared restroom.'),
            })
        if self.type == self.RoomType.UNENCLOSED and self.linked_restroom_id:
            if self.pk and self.linked_restroom_id == self.pk:
                raise ValidationError({
                    'linked_restroom': _('A room cannot be linked to itself as a shared restroom.'),
                })
            if self.linked_restroom and self.linked_restroom.type != self.RoomType.REST:
                raise ValidationError({
                    'linked_restroom': _('The linked room must be of type Rest.'),
                })
        if self.type == self.RoomType.REST and self.linked_restroom_id:
            raise ValidationError({
                'linked_restroom': _('A restroom room cannot link to another shared restroom.'),
            })

    @property
    def image_count(self):
        return len(self.image_paths or [])

    def _build_reading_source_summary(self, reading_type):
        source = getattr(self, f'latest_{reading_type}_reading_source', '')
        updated_by = getattr(self, f'latest_{reading_type}_reading_updated_by', None)
        usage = getattr(self, f'latest_{reading_type}_reading_usage', None)

        if source == self.ReadingUpdateSource.MANUAL:
            if updated_by:
                return _('Manual update on Room details by %(username)s') % {
                    'username': updated_by.get_username(),
                }
            return _('Manual update on Room details')

        if source == self.ReadingUpdateSource.USAGE:
            if usage:
                return _('Automatic update from subscription %(subscription_id)s (%(period)s)') % {
                    'subscription_id': usage.subscription_id,
                    'period': usage.period.strftime('%m/%Y'),
                }
            return _('Automatic update from subscription usage')

        return _('Not updated yet')

    @property
    def latest_electricity_reading_source_summary(self):
        return self._build_reading_source_summary('electricity')

    @property
    def latest_water_reading_source_summary(self):
        return self._build_reading_source_summary('water')

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
    image_paths = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ENABLED)
    start_date = models.DateField()
    tenant_count = models.PositiveIntegerField(default=1)
    start_electricity_reading = models.PositiveIntegerField(default=0)
    start_water_reading = models.PositiveIntegerField(default=0)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    room_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    electricity_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    water_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    use_internet = models.BooleanField(default=True)
    internet_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    cleaning_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    use_laundry = models.BooleanField(default=True)
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
        if not isinstance(self.image_paths, list):
            raise ValidationError({'image_paths': _('Image paths must be stored as a list.')})
        if len(self.image_paths) > 10:
            raise ValidationError({'image_paths': _('A subscription can store at most 10 images.')})
        if any(not isinstance(path, str) or not path.strip() for path in self.image_paths):
            raise ValidationError({'image_paths': _('Each image path must be a non-empty string.')})
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

    @classmethod
    def get_room_subscription_for_period(cls, room, period):
        usage_subscription_id = (
            Usage.objects.filter(subscription__room=room, period=period)
            .order_by('-updated_at', '-id')
            .values_list('subscription_id', flat=True)
            .first()
        )
        if usage_subscription_id:
            return cls.objects.select_related('room').filter(pk=usage_subscription_id).first()

        started_queryset = room.subscriptions.filter(start_date__lte=period).order_by('-start_date', '-updated_at', '-id')
        enabled_started = started_queryset.filter(status=cls.Status.ENABLED).first()
        if enabled_started:
            return enabled_started

        fallback_enabled = room.subscriptions.filter(status=cls.Status.ENABLED).order_by('-start_date', '-updated_at', '-id').first()
        if fallback_enabled:
            return fallback_enabled

        return room.subscriptions.order_by('-start_date', '-updated_at', '-id').first()

    @classmethod
    def get_restroom_linked_tenant_count(cls, restroom):
        if not restroom or not restroom.pk:
            return 0
        return (
            cls.objects.filter(
                status=cls.Status.ENABLED,
                room__type=Room.RoomType.UNENCLOSED,
                room__linked_restroom=restroom,
            )
            .aggregate(total=Sum('tenant_count'))
            .get('total')
            or 0
        )

    @classmethod
    def sync_restroom_subscription_tenant_count(cls, restroom):
        if not restroom or not restroom.pk or restroom.type != Room.RoomType.REST:
            return
        cls.objects.filter(
            room=restroom,
            status=cls.Status.ENABLED,
        ).update(
            tenant_count=cls.get_restroom_linked_tenant_count(restroom),
            updated_at=Now(),
        )

    def _normalize_restroom_subscription_fields(self):
        if not self.room_id or self.room.type != Room.RoomType.REST:
            return []

        normalized_values = {
            'tenant_count': self.get_restroom_linked_tenant_count(self.room),
            'deposit_amount': Decimal('0'),
            'room_price': Decimal('0'),
            'use_internet': False,
            'internet_price': Decimal('0'),
            'cleaning_price': Decimal('0'),
            'use_laundry': False,
            'laundry_price': Decimal('0'),
        }
        changed_fields = []
        for field_name, value in normalized_values.items():
            if getattr(self, field_name) != value:
                setattr(self, field_name, value)
                changed_fields.append(field_name)
        return changed_fields

    def save(self, *args, **kwargs):
        previous_linked_restroom_id = None
        if self.pk:
            previous_subscription = (
                Subscription.objects
                .select_related('room__linked_restroom')
                .filter(pk=self.pk)
                .first()
            )
            if previous_subscription and previous_subscription.room.type == Room.RoomType.UNENCLOSED:
                previous_linked_restroom_id = previous_subscription.room.linked_restroom_id

        if self._state.adding and all(getattr(self, field) in (None, 0, Decimal('0')) for field in PRICE_FIELD_NAMES):
            template = PriceTemplate.get_solo()
            for field in PRICE_FIELD_NAMES:
                setattr(self, field, getattr(template, field))

        normalized_fields = self._normalize_restroom_subscription_fields()
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and normalized_fields:
            kwargs['update_fields'] = set(update_fields) | set(normalized_fields) | {'updated_at'}

        super().save(*args, **kwargs)

        restroom_ids_to_sync = set()
        if previous_linked_restroom_id:
            restroom_ids_to_sync.add(previous_linked_restroom_id)
        if self.room.type == Room.RoomType.UNENCLOSED and self.room.linked_restroom_id:
            restroom_ids_to_sync.add(self.room.linked_restroom_id)
        for restroom in Room.objects.filter(pk__in=restroom_ids_to_sync, type=Room.RoomType.REST):
            self.sync_restroom_subscription_tenant_count(restroom)

    @property
    def image_count(self):
        return len(self.image_paths or [])

    def delete(self, *args, **kwargs):
        for path in self.image_paths or []:
            if default_storage.exists(path):
                default_storage.delete(path)
        super().delete(*args, **kwargs)


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
    class Status(models.TextChoices):
        UNPAID = 'unpaid', _('Unpaid')
        PAID = 'paid', _('Paid')

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='usages')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID)
    period = models.DateField()
    tenant_count = models.PositiveIntegerField(default=1, null=True, blank=True)
    room_price = models.DecimalField(max_digits=12, decimal_places=0, default=0, null=True, blank=True)
    electricity_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    water_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    use_internet = models.BooleanField(default=True)
    internet_price = models.DecimalField(max_digits=12, decimal_places=0, default=0, null=True, blank=True)
    cleaning_price = models.DecimalField(max_digits=12, decimal_places=0, default=0, null=True, blank=True)
    use_laundry = models.BooleanField(default=True)
    laundry_price = models.DecimalField(max_digits=12, decimal_places=0, default=0, null=True, blank=True)
    surcharge_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0, null=True, blank=True)
    surcharge_description = models.TextField(blank=True)
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

    LOCKED_FIELDS = (
        'subscription_id',
        'period',
        'tenant_count',
        'room_price',
        'electricity_price',
        'water_price',
        'use_internet',
        'internet_price',
        'cleaning_price',
        'use_laundry',
        'laundry_price',
        'surcharge_amount',
        'surcharge_description',
        'latest_electricity_reading',
        'electricity_meter_image_path',
        'latest_water_reading',
        'water_meter_image_path',
    )

    RESTROOM_LINKED_INVOICE_LOCKED_FIELDS = (
        'electricity_price',
        'water_price',
        'latest_electricity_reading',
        'electricity_meter_image_path',
        'latest_water_reading',
        'water_meter_image_path',
    )

    def __str__(self):
        return f"{self.subscription.room.room_name} - {self.period:%m/%Y}"

    def get_restroom_linked_invoice_status(self):
        if (
            not self.subscription_id
            or not self.period
            or self.subscription.room.type != Room.RoomType.REST
        ):
            return {
                'is_applicable': False,
                'is_locked': False,
                'paid_linked_usages': 0,
                'total_linked_subscriptions': 0,
                'linked_items': [],
            }

        linked_items = []
        linked_rooms = Room.objects.filter(
            type=Room.RoomType.UNENCLOSED,
            linked_restroom=self.subscription.room,
        ).order_by('room_name')
        for linked_room in linked_rooms:
            linked_subscription = Subscription.get_room_subscription_for_period(linked_room, self.period)
            if not linked_subscription:
                continue
            linked_usage = (
                Usage.objects.filter(subscription=linked_subscription, period=self.period)
                .order_by('-updated_at', '-id')
                .first()
            )
            linked_items.append({
                'room_name': linked_room.room_name,
                'subscription_id': linked_subscription.pk,
                'subscription_description': linked_subscription.description or '',
                'has_usage': bool(linked_usage),
                'is_paid': bool(linked_usage and linked_usage.status == self.Status.PAID),
            })

        paid_linked_usages = sum(1 for item in linked_items if item['is_paid'])
        return {
            'is_applicable': True,
            'is_locked': paid_linked_usages > 0,
            'paid_linked_usages': paid_linked_usages,
            'total_linked_subscriptions': len(linked_items),
            'linked_items': linked_items,
        }

    def clean(self):
        super().clean()
        if self.period and self.period.day != 1:
            raise ValidationError({'period': _('Please select month and year only.')})
        if self.pk:
            previous = Usage.objects.filter(pk=self.pk).first()
            if previous and previous.status == self.Status.PAID:
                if self.status != self.Status.PAID:
                    raise ValidationError({'status': _('A paid usage record cannot be changed back to a different status.')})
                changed_fields = [
                    field_name for field_name in self.LOCKED_FIELDS
                    if getattr(previous, field_name) != getattr(self, field_name)
                ]
                if changed_fields:
                    raise ValidationError(_('A paid usage record cannot be edited.'))
            if previous and previous.get_restroom_linked_invoice_status()['is_locked']:
                changed_fields = [
                    field_name for field_name in self.RESTROOM_LINKED_INVOICE_LOCKED_FIELDS
                    if getattr(previous, field_name) != getattr(self, field_name)
                ]
                if changed_fields:
                    raise ValidationError(_('A restroom usage record cannot be edited after linked invoices are paid.'))

    def save(self, *args, **kwargs):
        if self.period:
            self.period = self.period.replace(day=1)
        if self._state.adding and self.tenant_count in (None, ''):
            latest_usage = self.subscription.usages.order_by('-period', '-updated_at', '-id').first()
            if latest_usage and latest_usage.tenant_count is not None:
                self.tenant_count = latest_usage.tenant_count
            else:
                self.tenant_count = self.subscription.tenant_count
        if self._state.adding and all(getattr(self, field) in (None, 0, Decimal('0')) for field in PRICE_FIELD_NAMES):
            for field in PRICE_FIELD_NAMES:
                setattr(self, field, getattr(self.subscription, field))
        self.full_clean()
        super().save(*args, **kwargs)
        if self.tenant_count is not None and self.subscription.tenant_count != self.tenant_count:
            self.subscription.tenant_count = self.tenant_count
            self.subscription.save(update_fields=['tenant_count', 'updated_at'])
        self._sync_room_readings_for_room(self.subscription.room)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.PAID:
            raise ValidationError(_('A paid usage record cannot be deleted.'))
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
            or room.latest_electricity_reading_source != Room.ReadingUpdateSource.USAGE
            or room.latest_water_reading_source != Room.ReadingUpdateSource.USAGE
            or room.latest_electricity_reading_usage_id != latest_usage.pk
            or room.latest_water_reading_usage_id != latest_usage.pk
            or room.latest_electricity_reading_updated_at != latest_usage.updated_at
            or room.latest_water_reading_updated_at != latest_usage.updated_at
            or room.latest_electricity_reading_updated_by_id is not None
            or room.latest_water_reading_updated_by_id is not None
        ):
            room.latest_electricity_reading = latest_usage.latest_electricity_reading
            room.latest_water_reading = latest_usage.latest_water_reading
            room.latest_electricity_reading_source = Room.ReadingUpdateSource.USAGE
            room.latest_water_reading_source = Room.ReadingUpdateSource.USAGE
            room.latest_electricity_reading_usage = latest_usage
            room.latest_water_reading_usage = latest_usage
            room.latest_electricity_reading_updated_at = latest_usage.updated_at
            room.latest_water_reading_updated_at = latest_usage.updated_at
            room.latest_electricity_reading_updated_by = None
            room.latest_water_reading_updated_by = None
            room.save(update_fields=[
                'latest_electricity_reading',
                'latest_water_reading',
                'latest_electricity_reading_source',
                'latest_water_reading_source',
                'latest_electricity_reading_usage',
                'latest_water_reading_usage',
                'latest_electricity_reading_updated_at',
                'latest_water_reading_updated_at',
                'latest_electricity_reading_updated_by',
                'latest_water_reading_updated_by',
                'updated_at',
            ])
