"""
apps/orders/services.py
Core order placement, status management, cart validation
Race condition handling with SELECT FOR UPDATE
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from menu.models import Cart, CartItem, FoodItem
from .models import Order, OrderItem, DeliveryAddress, OrderStatusHistory

logger = logging.getLogger('apps.orders')


class CartValidationError(Exception):
    def __init__(self, message, unavailable_items=None):
        self.message = message
        self.unavailable_items = unavailable_items or []
        super().__init__(message)


class OrderService:

    @staticmethod
    @transaction.atomic
    def place_order(customer, order_data: dict) -> tuple:
        """
        Place order from customer cart.
        Uses SELECT FOR UPDATE to prevent race conditions.
        Returns (order, payment_data).
        """
        # 1. Fetch and lock cart + items to prevent concurrent modifications
        try:
            cart = Cart.objects.select_for_update().get(user=customer)
        except Cart.DoesNotExist:
            raise CartValidationError("You don't have an active cart.")

        cart_items = CartItem.objects.select_for_update().filter(
            cart=cart
        ).select_related('food_item')

        if not cart_items.exists():
            raise CartValidationError("Your cart is empty.")

        # 2. Lock food items to prevent availability race condition
        food_item_ids = [ci.food_item_id for ci in cart_items]
        food_items = {
            fi.id: fi for fi in
            FoodItem.objects.select_for_update().filter(id__in=food_item_ids)
        }

        # 3. Validate all items
        unavailable = []
        price_mismatches = []
        subtotal = Decimal('0.00')

        for cart_item in cart_items:
            food = food_items.get(cart_item.food_item_id)

            if not food or not food.is_available:
                unavailable.append({
                    'item': cart_item.food_item.name,
                    'reason': 'Item is no longer available'
                })
                continue

            # Check price mismatch (price changed since adding to cart)
            if food.price != cart_item.unit_price:
                price_mismatches.append({
                    'item': food.name,
                    'cart_price': str(cart_item.unit_price),
                    'current_price': str(food.price)
                })
                # Update cart item price to current price
                cart_item.unit_price = food.price
                cart_item.save(update_fields=['unit_price'])

            subtotal += food.price * cart_item.quantity

        if unavailable:
            raise CartValidationError(
                "Some items in your cart are no longer available.",
                unavailable_items=unavailable
            )

        delivery_fee = Decimal(str(order_data.get('delivery_fee', '0')))
        total_amount = subtotal + delivery_fee

        # 4. Create order
        order = Order.objects.create(
            order_number=Order.generate_order_number(),
            customer=customer,
            status=Order.Status.PENDING,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total_amount=total_amount,
            customer_note=order_data.get('customer_note', ''),
        )

        # 5. Create order items (snapshot prices and names)
        order_items = []
        for cart_item in cart_items:
            food = food_items[cart_item.food_item_id]
            order_items.append(OrderItem(
                order=order,
                food_item=food,
                quantity=cart_item.quantity,
                unit_price=food.price,
                food_item_name=food.name,
            ))
        OrderItem.objects.bulk_create(order_items)

        # 6. Create delivery address
        DeliveryAddress.objects.create(
            order=order,
            street_address=order_data['street_address'],
            city=order_data['city'],
            state=order_data['state'],
            landmark=order_data.get('landmark', ''),
            additional_info=order_data.get('additional_info', ''),
            recipient_name=order_data['recipient_name'],
            recipient_phone=order_data['recipient_phone'],
            recipient_email=order_data.get('recipient_email', ''),
            order_date=order_data['order_date'],
            delivery_date=order_data.get('delivery_date'),
        )

        # 7. Record initial status history
        OrderStatusHistory.objects.create(
            order=order,
            from_status='',
            to_status=Order.Status.PENDING,
            changed_by=customer,
            note='Order placed by customer.'
        )

        # 8. Clear cart
        cart_items.delete()

        logger.info(f"Order {order.order_number} placed by customer {customer.id}")

        return order, {'price_mismatches': price_mismatches}

    @staticmethod
    @transaction.atomic
    def update_order_status(order_id, new_status, actor, note=''):
        """Update order status with full validation."""
        try:
            order = Order.objects.select_for_update().get(id=order_id)
        except Order.DoesNotExist:
            raise ValueError("Order not found.")

        can_transition, reason = order.can_transition_to(new_status, actor)
        if not can_transition:
            raise ValueError(reason)

        old_status = order.status
        order.status = new_status

        if new_status == Order.Status.CANCELLED:
            order.cancelled_by = actor
            order.cancelled_at = timezone.now()
            order.cancellation_reason = note

        order.save(update_fields=['status', 'cancelled_by', 'cancelled_at',
                                   'cancellation_reason', 'updated_at'])

        OrderStatusHistory.objects.create(
            order=order,
            from_status=old_status,
            to_status=new_status,
            changed_by=actor,
            note=note
        )

        logger.info(f"Order {order.order_number} status: {old_status} -> {new_status} by {actor.id}")

        # Trigger async notification
        from apps.notifications.tasks import send_order_status_notification_task
        send_order_status_notification_task.delay(str(order.id), new_status)

        return order

    @staticmethod
    def get_customer_orders(customer, status=None):
        qs = Order.objects.filter(customer=customer).select_related(
            'delivery_address'
        ).prefetch_related('items', 'status_history').order_by('-created_at')
        if status:
            qs = qs.filter(status=status)
        return qs

    @staticmethod
    def get_all_orders(status=None, date_from=None, date_to=None):
        qs = Order.objects.select_related(
            'customer', 'delivery_address', 'cancelled_by'
        ).prefetch_related('items').order_by('-created_at')
        if status:
            qs = qs.filter(status=status)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs
