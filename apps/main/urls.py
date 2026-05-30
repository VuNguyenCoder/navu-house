from django.urls import path

from . import views


urlpatterns = [
    path('price-template/', views.price_template, name='price_template'),
    path('usage-pricing-context/', views.usage_pricing_context, name='usage_pricing_context'),
    path('vehicles/', views.VehicleListView.as_view(), name='vehicle_list'),
    path('vehicles/create/', views.VehicleCreateView.as_view(), name='vehicle_create'),
    path('vehicles/<int:pk>/details/', views.VehicleUpdateView.as_view(), name='vehicle_details'),
    path('vehicles/<int:pk>/delete/', views.VehicleDeleteView.as_view(), name='vehicle_delete'),
    path('rooms/', views.RoomListView.as_view(), name='room_list'),
    path('rooms/create/', views.RoomCreateView.as_view(), name='room_create'),
    path('rooms/<int:pk>/details/', views.RoomUpdateView.as_view(), name='room_details'),
    path('rooms/<int:pk>/delete/', views.RoomDeleteView.as_view(), name='room_delete'),
    path('subscriptions/', views.SubscriptionListView.as_view(), name='subscription_list'),
    path('subscriptions/create/', views.SubscriptionCreateView.as_view(), name='subscription_create'),
    path('subscriptions/<int:pk>/details/', views.SubscriptionUpdateView.as_view(), name='subscription_details'),
    path('subscriptions/<int:pk>/deactivate/', views.subscription_deactivate, name='subscription_deactivate'),
    path('subscriptions/<int:pk>/delete/', views.SubscriptionDeleteView.as_view(), name='subscription_delete'),
    path('usages/', views.usage_list_redirect, name='usage_list'),
    path('usages/create/', views.UsageCreateView.as_view(), name='usage_create'),
    path('usages/<int:pk>/details/', views.UsageUpdateView.as_view(), name='usage_details'),
    path('usages/<int:pk>/delete/', views.UsageDeleteView.as_view(), name='usage_delete'),
]
