"""
apps/payments/models.py
Payment records for Paystack integration
"""
import uuid
from django.db import models
from decimal import Decimal


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'
        ABANDONED = 'abandoned', 'Abandoned'

    class Channel(models.TextChoices):
        CARD = 'card', 'Debit/Credit Card'
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
        USSD = 'ussd', 'USSD'
        MOBILE_MONEY = 'mobile_money', 'Mobile Money'
        QR = 'qr', 'QR Code'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('orders.Order', on_delete=models.PROTECT, related_name='payments')
    customer = models.ForeignKey('users.User', on_delete=models.PROTECT, related_name='payments')

    # Paystack fields
    reference = models.CharField(max_length=100, unique=True, db_index=True)
    paystack_id = models.CharField(max_length=100, blank=True)
    access_code = models.CharField(max_length=100, blank=True)  # For Paystack inline/redirect
    authorization_url = models.URLField(blank=True)  # Paystack redirect URL

    # Financial
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default='NGN')
    channel = models.CharField(max_length=20, choices=Channel.choices, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Card details snapshot (masked)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=20, blank=True)
    card_bank = models.CharField(max_length=100, blank=True)

    # Bank transfer details
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=20, blank=True)

    # Timestamps
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Webhook
    gateway_response = models.TextField(blank=True)
    webhook_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'payments'
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['order', 'status']),
            models.Index(fields=['customer', 'status']),
        ]

    def __str__(self):
        return f"Payment({self.reference}, {self.status})"

    @property
    def amount_kobo(self):
        """Convert Naira to kobo for Paystack."""
        return int(self.amount * 100)

    @classmethod
    def generate_reference(cls, order_number):
        import time
        ts = int(time.time())
        ref = f"CK-{order_number}-{ts}"
        if cls.objects.filter(reference=ref).exists():
            return cls.generate_reference(order_number)
        return ref
