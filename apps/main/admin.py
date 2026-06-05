from django.contrib import admin

from .models import PriceTemplate, Room, Subscription, Usage, Vehicle


@admin.register(PriceTemplate)
class PriceTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'room_price',
        'electricity_price',
        'water_price',
        'internet_price',
        'cleaning_price',
        'updated_at',
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        'room_name',
        'type',
        'linked_restroom',
        'image_count',
        'latest_electricity_reading',
        'latest_water_reading',
        'updated_at',
    )
    search_fields = ('room_name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'room',
        'status',
        'start_date',
        'contact_email',
        'updated_at',
    )
    list_filter = ('status', 'start_date')
    search_fields = ('room__room_name', 'contact_email', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Usage)
class UsageAdmin(admin.ModelAdmin):
    list_display = (
        'subscription',
        'period',
        'tenant_count',
        'latest_electricity_reading',
        'latest_water_reading',
        'updated_at',
    )
    list_filter = ('period',)
    search_fields = ('subscription__room__room_name', 'subscription__contact_email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        'license_plate',
        'subscription',
        'created_at',
    )
    search_fields = ('license_plate', 'subscription__room__room_name', 'subscription__contact_email')
    readonly_fields = ('created_at', 'updated_at')
