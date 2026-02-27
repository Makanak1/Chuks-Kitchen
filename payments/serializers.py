"""
apps/payments/serializers.py
"""
from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'reference', 'amount', 'currency', 'channel',
            'status', 'card_last4', 'card_brand', 'card_bank',
            'authorization_url', 'paid_at', 'created_at'
        ]
        read_only_fields = fields


class InitiatePaymentSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    channel = serializers.ChoiceField(
        choices=Payment.Channel.choices,
        default=Payment.Channel.CARD
    )
    # For card payments (optional, Paystack handles via inline)
    card_number = serializers.CharField(required=False, max_length=19)
    card_expiry = serializers.CharField(required=False, max_length=7)  # MM/YY
    card_cvv = serializers.CharField(required=False, max_length=4)

    def validate(self, attrs):
        channel = attrs.get('channel')
        if channel == Payment.Channel.CARD:
            # Card details are optional — Paystack popup handles it client-side
            # But if provided, validate format
            card_number = attrs.get('card_number', '')
            if card_number:
                digits = card_number.replace(' ', '').replace('-', '')
                if not digits.isdigit() or len(digits) < 13:
                    raise serializers.ValidationError({"card_number": "Invalid card number."})
                attrs['card_number_clean'] = digits
        return attrs


class PaystackWebhookSerializer(serializers.Serializer):
    event = serializers.CharField()
    data = serializers.DictField()
