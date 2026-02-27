"""
apps/notifications/tasks.py
Celery async tasks for OTP emails and order notifications
"""
import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

User = get_user_model()
logger = logging.getLogger('apps.notifications')


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_otp_email_task(self, user_id, otp_code, purpose):
    """Send OTP email asynchronously."""
    try:
        user = User.objects.get(id=user_id)
        subject = "Chuks Kitchen - Your Verification Code"
        purpose_label = {
            'email_verification': 'account verification',
            'password_reset': 'password reset',
        }.get(purpose, 'verification')

        body = f"""
Hello {user.first_name},

Your Chuks Kitchen OTP for {purpose_label} is:

    {otp_code}

This code expires in {settings.OTP_EXPIRY_MINUTES} minutes.

If you didn't request this, please ignore this email.

- The Chuks Kitchen Team
        """.strip()

        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"OTP email sent to {user.email}")
    except User.DoesNotExist:
        logger.error(f"OTP email failed: User {user_id} not found")
    except Exception as exc:
        logger.error(f"OTP email failed for {user_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_status_notification_task(self, order_id, new_status):
    """Notify customer about order status change."""
    try:
        from apps.orders.models import Order
        order = Order.objects.select_related('customer').get(id=order_id)
        customer = order.customer
        if not customer.email:
            return

        status_messages = {
            'confirmed': '✅ Your order has been confirmed! We\'re getting it ready.',
            'preparing': '👨‍🍳 Your order is now being prepared.',
            'out_for_delivery': '🛵 Your order is on its way!',
            'completed': '🎉 Your order has been delivered. Enjoy your meal!',
            'cancelled': '❌ Your order has been cancelled.',
        }

        message = status_messages.get(new_status, f'Your order status is now: {new_status}')

        send_mail(
            subject=f"Chuks Kitchen - Order #{order.order_number} Update",
            message=f"Hello {customer.first_name},\n\n{message}\n\nOrder: #{order.order_number}\n\n- Chuks Kitchen",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer.email],
            fail_silently=True,
        )
        logger.info(f"Order notification sent for {order.order_number}, status={new_status}")
    except Exception as exc:
        logger.error(f"Order notification failed: {exc}")
        raise self.retry(exc=exc)


@shared_task
def send_payment_receipt_task(payment_id):
    """Send payment receipt email."""
    try:
        from apps.payments.models import Payment
        payment = Payment.objects.select_related('customer', 'order').get(id=payment_id)
        if not payment.customer.email:
            return

        send_mail(
            subject=f"Chuks Kitchen - Payment Receipt #{payment.reference}",
            message=f"""
Hello {payment.customer.first_name},

Your payment of ₦{payment.amount} for Order #{payment.order.order_number} was successful.

Reference: {payment.reference}
Channel: {payment.channel}
Date: {payment.paid_at.strftime('%d %B %Y, %I:%M %p') if payment.paid_at else 'N/A'}

Thank you for ordering from Chuks Kitchen!

- The Chuks Kitchen Team
            """.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payment.customer.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f"Payment receipt email failed: {e}")
