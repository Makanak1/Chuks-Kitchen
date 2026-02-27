"""
apps/orders/serializers.py
"""
from rest_framework import serializers
from django.utils import timezone
from .models import Order, OrderItem, DeliveryAddress, OrderStatusHistory


class DeliveryAddressSerializer(serializers.ModelSerializer):
    full_address = serializers.ReadOnlyField()

    class Meta:
        model = DeliveryAddress
        fields = [
            'id', 'street_address', 'city', 'state', 'landmark', 'additional_info',
            'recipient_name', 'recipient_phone', 'recipient_email',
            'order_date', 'delivery_date', 'full_address'
        ]

    def validate_order_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Order date cannot be in the past.")
        return value


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = ['id', 'food_item', 'food_item_name', 'quantity', 'unit_price', 'subtotal']


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.full_name', read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = ['from_status', 'to_status', 'changed_by_name', 'note', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    delivery_address = DeliveryAddressSerializer(read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'customer', 'customer_name', 'status',
            'subtotal', 'delivery_fee', 'total_amount',
            'customer_note', 'admin_note',
            'cancellation_reason', 'cancelled_at',
            'estimated_delivery_at', 'created_at', 'updated_at',
            'items', 'delivery_address', 'status_history'
        ]
        read_only_fields = ['id', 'order_number', 'customer', 'status', 'subtotal',
                            'delivery_fee', 'total_amount', 'created_at', 'updated_at']


class PlaceOrderSerializer(serializers.Serializer):
    """Used when a customer places an order from their cart."""
    customer_note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)

    # Delivery address (required)
    street_address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    landmark = serializers.CharField(required=False, allow_blank=True, max_length=255)
    additional_info = serializers.CharField(required=False, allow_blank=True)
    recipient_name = serializers.CharField(max_length=200)
    recipient_phone = serializers.CharField(max_length=20)
    recipient_email = serializers.EmailField(required=False, allow_blank=True)
    order_date = serializers.DateField()
    delivery_date = serializers.DateField(required=False, allow_null=True)

    # Payment channel preference
    payment_channel = serializers.ChoiceField(
        choices=['card', 'bank_transfer', 'ussd', 'mobile_money'],
        default='card'
    )

    def validate_order_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Order date cannot be in the past.")
        return value


class UpdateOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True)

    def validate_status(self, value):
        # Additional per-context validation done in the service layer
        return value


class CancelOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
