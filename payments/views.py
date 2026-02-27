"""
apps/payments/views.py
Payment initialization, verification, Paystack webhook
"""
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from .models import Payment
from .serializers import PaymentSerializer, InitiatePaymentSerializer
from .services import PaystackService, PaystackError

logger = logging.getLogger('apps.payments')


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=400)

        order_id = serializer.validated_data['order_id']
        channel = serializer.validated_data['channel']

        try:
            order = Order.objects.get(id=order_id, customer=request.user)
        except Order.DoesNotExist:
            return Response({'success': False, 'message': 'Order not found.'}, status=404)

        if order.status not in [Order.Status.PENDING]:
            return Response({
                'success': False,
                'message': f'Cannot process payment for {order.status} order.'
            }, status=400)

        try:
            payment = PaystackService.initialize_payment(order, request.user, channel)
        except PaystackError as e:
            return Response({'success': False, 'message': str(e)}, status=503)

        return Response({
            'success': True,
            'message': 'Payment initialized.',
            'data': {
                'reference': payment.reference,
                'authorization_url': payment.authorization_url,
                'access_code': payment.access_code,
                'amount': str(payment.amount),
                'currency': payment.currency,
                'channel': channel,
            }
        })


class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, reference):
        try:
            payment = PaystackService.verify_payment(reference)
        except PaystackError as e:
            return Response({'success': False, 'message': str(e)}, status=400)

        # Security: ensure user owns this payment
        if payment.customer != request.user and not request.user.is_admin:
            return Response({'success': False, 'message': 'Not authorized.'}, status=403)

        return Response({
            'success': True,
            'data': PaymentSerializer(payment).data
        })


class PaymentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_admin:
            payments = Payment.objects.select_related('order', 'customer').order_by('-created_at')[:50]
        else:
            payments = Payment.objects.filter(customer=request.user).select_related('order').order_by('-created_at')[:50]
        return Response({
            'success': True,
            'data': PaymentSerializer(payments, many=True).data
        })


@method_decorator(csrf_exempt, name='dispatch')
class PaystackWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        signature = request.headers.get('X-Paystack-Signature', '')

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return Response({'message': 'Invalid payload.'}, status=400)

        success = PaystackService.handle_webhook(payload, signature)

        if not success:
            return Response({'message': 'Webhook processing failed.'}, status=400)

        return Response({'message': 'Webhook received.'}, status=200)


class PaystackCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Paystack redirects here after payment attempt."""
        reference = request.query_params.get('reference')
        if not reference:
            return Response({'success': False, 'message': 'No reference provided.'}, status=400)

        try:
            payment = PaystackService.verify_payment(reference)
        except PaystackError as e:
            return Response({'success': False, 'message': str(e)}, status=400)

        return Response({
            'success': True,
            'message': f'Payment {payment.status}.',
            'data': PaymentSerializer(payment).data
        })
