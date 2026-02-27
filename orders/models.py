"""
apps/orders/models.py
Orders, Order Items, Delivery Address
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        PREPARING = 'preparing', 'Preparing'
        OUT_FOR_DELIVERY = 'out_for_delivery', 'Out for Delivery'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    # Valid transitions map
    VALID_TRANSITIONS = {
        Status.PENDING: [Status.CONFIRMED, Status.CANCELLED],
        Status.CONFIRMED: [Status.PREPARING, Status.CANCELLED],
        Status.PREPARING: [Status.OUT_FOR_DELIVERY, Status.CANCELLED],
        Status.OUT_FOR_DELIVERY: [Status.COMPLETED, Status.CANCELLED],
        Status.COMPLETED: [],
        Status.CANCELLED: [],
    }

    # Admin-only transitions (customer can only cancel from PENDING)
    ADMIN_ONLY_TRANSITIONS = {
        Status.PENDING: [Status.CONFIRMED],
        Status.CONFIRMED: [Status.PREPARING, Status.CANCELLED],
        Status.PREPARING: [Status.OUT_FOR_DELIVERY, Status.CANCELLED],
        Status.OUT_FOR_DELIVERY: [Status.COMPLETED, Status.CANCELLED],
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    customer = models.ForeignKey('users.User', on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Notes
    customer_note = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)

    # Cancellation
    cancelled_by = models.ForeignKey(
        'users.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='cancelled_orders'
    )
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    estimated_delivery_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'orders'
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['order_number']),
        ]

    def __str__(self):
        return f"Order#{self.order_number}"

    def can_transition_to(self, new_status, actor):
        """Check if status transition is valid for the given actor."""
        if self.status == new_status:
            return False, "Order is already in this status."
        if self.status == self.Status.COMPLETED:
            return False, "Completed orders cannot be changed."
        if self.status == self.Status.CANCELLED:
            return False, "Cancelled orders cannot be changed."

        valid_next = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in valid_next:
            return False, f"Cannot move from {self.status} to {new_status}."

        # Customer can only cancel from PENDING
        if not actor.is_admin:
            if new_status == self.Status.CANCELLED and self.status != self.Status.PENDING:
                return False, "You can only cancel orders that are still pending."
            if new_status != self.Status.CANCELLED:
                return False, "Customers can only cancel orders."

        return True, "Transition allowed."

    @classmethod
    def generate_order_number(cls):
        import random
        import string
        prefix = 'CK'
        suffix = ''.join(random.choices(string.digits, k=8))
        number = f"{prefix}{suffix}"
        if cls.objects.filter(order_number=number).exists():
            return cls.generate_order_number()
        return number


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    food_item = models.ForeignKey('menu.FoodItem', on_delete=models.PROTECT)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # Snapshot price
    food_item_name = models.CharField(max_length=200)  # Snapshot name (in case item is deleted)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_items'
        indexes = [models.Index(fields=['order', 'food_item'])]

    def __str__(self):
        return f"{self.food_item_name} x{self.quantity}"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


class DeliveryAddress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_address')

    # Address fields
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    landmark = models.CharField(max_length=255, blank=True)
    additional_info = models.TextField(blank=True)

    # Contact details
    recipient_name = models.CharField(max_length=200)
    recipient_phone = models.CharField(max_length=20)
    recipient_email = models.EmailField(blank=True)

    # Metadata
    order_date = models.DateField()
    delivery_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'delivery_addresses'

    def __str__(self):
        return f"{self.recipient_name} - {self.street_address}, {self.city}"

    @property
    def full_address(self):
        parts = [self.street_address, self.city, self.state]
        if self.landmark:
            parts.append(f"Landmark: {self.landmark}")
        return ', '.join(parts)


class OrderStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_status_history'
        ordering = ['-created_at']
