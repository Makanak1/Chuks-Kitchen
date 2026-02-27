"""
apps/orders/views.py
Order placement, tracking, status management
"""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsAdmin, IsCustomer, IsOrderOwnerOrAdmin
from config.pagination import StandardResultsPagination
from .models import Order
from .serializers import (
    OrderSerializer, PlaceOrderSerializer,
    UpdateOrderStatusSerializer, CancelOrderSerializer
)
from .services import OrderService, CartValidationError

logger = logging.getLogger('apps.orders')


class PlaceOrderView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):
        serializer = PlaceOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=400)

        try:
            order, meta = OrderService.place_order(request.user, serializer.validated_data)
        except CartValidationError as e:
            return Response({
                'success': False,
                'message': e.message,
                'unavailable_items': e.unavailable_items
            }, status=400)

        # Initialize payment
        channel = serializer.validated_data.get('payment_channel', 'card')
        try:
            from apps.payments.services import PaystackService
            payment = PaystackService.initialize_payment(order, request.user, channel)
            payment_data = {
                'reference': payment.reference,
                'authorization_url': payment.authorization_url,
                'access_code': payment.access_code,
            }
        except Exception as e:
            logger.error(f"Payment init failed for order {order.order_number}: {e}")
            payment_data = {'error': 'Payment initialization failed. Please retry payment.'}

        response_data = {
            'success': True,
            'message': 'Order placed successfully.',
            'data': {
                'order': OrderSerializer(order).data,
                'payment': payment_data,
            }
        }

        if meta.get('price_mismatches'):
            response_data['warnings'] = {
                'price_updates': meta['price_mismatches'],
                'message': 'Some item prices were updated to current prices.'
            }

        return Response(response_data, status=status.HTTP_201_CREATED)


class CustomerOrderListView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        status_filter = request.query_params.get('status')
        orders = OrderService.get_customer_orders(request.user, status=status_filter)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(orders, request)
        serializer = OrderSerializer(page, many=True)
        return paginator.get_paginated_response({'success': True, 'data': serializer.data})


class CustomerOrderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOrderOwnerOrAdmin]

    def get(self, request, order_id):
        try:
            order = Order.objects.select_related(
                'delivery_address', 'customer', 'cancelled_by'
            ).prefetch_related('items', 'status_history__changed_by').get(id=order_id)
        except Order.DoesNotExist:
            return Response({'success': False, 'message': 'Order not found.'}, status=404)

        self.check_object_permissions(request, order)
        return Response({'success': True, 'data': OrderSerializer(order).data})


class CancelOrderView(APIView):
    permission_classes = [IsAuthenticated, IsOrderOwnerOrAdmin]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({'success': False, 'message': 'Order not found.'}, status=404)

        self.check_object_permissions(request, order)

        serializer = CancelOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = OrderService.update_order_status(
                order_id=order.id,
                new_status=Order.Status.CANCELLED,
                actor=request.user,
                note=serializer.validated_data.get('reason', '')
            )
        except ValueError as e:
            return Response({'success': False, 'message': str(e)}, status=400)

        return Response({
            'success': True,
            'message': 'Order cancelled.',
            'data': OrderSerializer(order).data
        })


# ─── Admin Views ────────────────────────────────────────────

class AdminOrderListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        status_filter = request.query_params.get('status')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        orders = OrderService.get_all_orders(status=status_filter, date_from=date_from, date_to=date_to)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(orders, request)
        return paginator.get_paginated_response({
            'success': True,
            'data': OrderSerializer(page, many=True).data
        })


class AdminUpdateOrderStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, order_id):
        serializer = UpdateOrderStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=400)

        try:
            order = OrderService.update_order_status(
                order_id=order_id,
                new_status=serializer.validated_data['status'],
                actor=request.user,
                note=serializer.validated_data.get('note', '')
            )
        except ValueError as e:
            return Response({'success': False, 'message': str(e)}, status=400)

        return Response({
            'success': True,
            'message': f'Order status updated to {order.status}.',
            'data': OrderSerializer(order).data
        })
