"""
apps/payments/services.py
Paystack payment gateway integration - full implementation
"""
import hashlib
import hmac
import json
import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from .models import Payment

logger = logging.getLogger('apps.payments')


class PaystackError(Exception):
    pass


class PaystackService:
    BASE_URL = settings.PAYSTACK_BASE_URL
    SECRET_KEY = settings.PAYSTACK_SECRET_KEY

    @classmethod
    def _headers(cls):
        return {
            'Authorization': f'Bearer {cls.SECRET_KEY}',
            'Content-Type': 'application/json',
        }

    @classmethod
    def _post(cls, endpoint, data):
        url = f"{cls.BASE_URL}{endpoint}"
        try:
            response = requests.post(url, json=data, headers=cls._headers(), timeout=30)
            result = response.json()
            if not result.get('status'):
                raise PaystackError(result.get('message', 'Paystack request failed.'))
            return result['data']
        except requests.RequestException as e:
            logger.error(f"Paystack API error: {e}")
            raise PaystackError("Payment gateway unavailable. Please try again.")

    @classmethod
    def _get(cls, endpoint):
        url = f"{cls.BASE_URL}{endpoint}"
        try:
            response = requests.get(url, headers=cls._headers(), timeout=30)
            result = response.json()
            if not result.get('status'):
                raise PaystackError(result.get('message', 'Paystack request failed.'))
            return result['data']
        except requests.RequestException as e:
            logger.error(f"Paystack API error: {e}")
            raise PaystackError("Payment gateway unavailable. Please try again.")

    @classmethod
    @transaction.atomic
    def initialize_payment(cls, order: Order, customer, channel: str = 'card') -> Payment:
        """
        Initialize payment with Paystack.
        Returns a Payment object with authorization_url for redirect/inline.
        """
        # Prevent duplicate pending payment for same order
        existing = Payment.objects.filter(
            order=order, status=Payment.Status.PENDING
        ).first()
        if existing:
            return existing

        reference = Payment.generate_reference(order.order_number)
        amount_kobo = int(order.total_amount * 100)

        payload = {
            'email': customer.email or f"{customer.phone_number}@chukskitchen.com",
            'amount': amount_kobo,
            'reference': reference,
            'currency': 'NGN',
            'channels': cls._get_channels(channel),
            'metadata': {
                'order_id': str(order.id),
                'order_number': order.order_number,
                'customer_id': str(customer.id),
                'cancel_action': f"{settings.FRONTEND_URL}/orders/{order.id}/payment-cancelled",
            },
            'callback_url': f"{settings.BACKEND_URL}/api/v1/payments/paystack/callback/",
        }

        try:
            data = cls._post('/transaction/initialize', payload)
        except PaystackError:
            raise

        payment = Payment.objects.create(
            order=order,
            customer=customer,
            reference=reference,
            access_code=data.get('access_code', ''),
            authorization_url=data.get('authorization_url', ''),
            amount=order.total_amount,
            currency='NGN',
            channel=channel,
            status=Payment.Status.PENDING,
        )

        logger.info(f"Payment initialized: {reference} for order {order.order_number}")
        return payment

    @classmethod
    @transaction.atomic
    def verify_payment(cls, reference: str) -> Payment:
        """Verify a payment by reference from Paystack."""
        try:
            payment = Payment.objects.select_for_update().get(reference=reference)
        except Payment.DoesNotExist:
            raise PaystackError("Payment record not found.")

        if payment.status == Payment.Status.SUCCESS:
            return payment  # Already verified

        try:
            data = cls._get(f'/transaction/verify/{reference}')
        except PaystackError:
            raise

        gateway_status = data.get('status')
        channel = data.get('channel', '')
        paid_at_str = data.get('paid_at')

        update_fields = ['status', 'channel', 'gateway_response', 'updated_at']

        if gateway_status == 'success':
            payment.status = Payment.Status.SUCCESS
            payment.channel = channel
            payment.gateway_response = data.get('gateway_response', '')

            # Extract card details
            authorization = data.get('authorization', {})
            if authorization:
                payment.card_last4 = authorization.get('last4', '')
                payment.card_brand = authorization.get('card_type', '')
                payment.card_bank = authorization.get('bank', '')
                update_fields += ['card_last4', 'card_brand', 'card_bank']

            # Extract bank transfer details
            if channel == 'bank_transfer':
                payment.bank_name = data.get('bank', '')
                update_fields += ['bank_name']

            if paid_at_str:
                from django.utils.dateparse import parse_datetime
                payment.paid_at = parse_datetime(paid_at_str)
                update_fields.append('paid_at')

            # Confirm the order
            from apps.orders.services import OrderService
            try:
                OrderService.update_order_status(
                    payment.order_id,
                    Order.Status.CONFIRMED,
                    actor=payment.customer,  # System confirms after payment
                    note='Payment confirmed via Paystack.'
                )
            except Exception as e:
                logger.warning(f"Could not auto-confirm order after payment: {e}")

        elif gateway_status == 'failed':
            payment.status = Payment.Status.FAILED
            payment.gateway_response = data.get('gateway_response', 'Payment failed.')
        elif gateway_status == 'abandoned':
            payment.status = Payment.Status.ABANDONED

        payment.webhook_data = data
        update_fields.append('webhook_data')
        payment.save(update_fields=update_fields)

        logger.info(f"Payment {reference} verified: {payment.status}")
        return payment

    @classmethod
    def handle_webhook(cls, payload: dict, signature: str) -> bool:
        """Process Paystack webhook event."""
        # Verify signature
        if not cls._verify_webhook_signature(json.dumps(payload, separators=(',', ':')), signature):
            logger.warning("Invalid Paystack webhook signature")
            return False

        event = payload.get('event')
        data = payload.get('data', {})
        reference = data.get('reference')

        logger.info(f"Paystack webhook: {event} for ref {reference}")

        if event == 'charge.success':
            try:
                cls.verify_payment(reference)
            except Exception as e:
                logger.error(f"Webhook payment verification failed: {e}")
                return False

        elif event == 'charge.dispute.create':
            logger.warning(f"Payment dispute for ref {reference}")

        elif event == 'refund.processed':
            try:
                payment = Payment.objects.get(reference=reference)
                payment.status = Payment.Status.REFUNDED
                payment.save(update_fields=['status'])
            except Payment.DoesNotExist:
                pass

        return True

    @classmethod
    def _verify_webhook_signature(cls, payload_str: str, signature: str) -> bool:
        secret = settings.PAYSTACK_WEBHOOK_SECRET.encode('utf-8')
        computed = hmac.new(secret, payload_str.encode('utf-8'), hashlib.sha512).hexdigest()
        return hmac.compare_digest(computed, signature)

    @staticmethod
    def _get_channels(channel: str) -> list:
        channel_map = {
            'card': ['card'],
            'bank_transfer': ['bank_transfer'],
            'ussd': ['ussd'],
            'mobile_money': ['mobile_money'],
            'all': ['card', 'bank_transfer', 'ussd', 'mobile_money'],
        }
        return channel_map.get(channel, ['card'])
