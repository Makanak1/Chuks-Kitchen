"""
apps/users/services.py
Business logic for user registration, OTP, verification
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import OTP, User

logger = logging.getLogger('apps.users')


class OTPThrottleError(Exception):
    pass


class UserService:

    @staticmethod
    def get_otp_cooldown_key(user_id, purpose):
        return f"otp_cooldown:{user_id}:{purpose}"

    @staticmethod
    def get_otp_attempts_key(user_id, purpose):
        return f"otp_attempts:{user_id}:{purpose}"

    @classmethod
    def send_otp(cls, user, purpose=OTP.Purpose.EMAIL_VERIFICATION):
        """Generate and send OTP with cooldown and throttle checks."""
        cooldown_key = cls.get_otp_cooldown_key(user.id, purpose)

        # Check cooldown
        ttl = cache.ttl(cooldown_key)
        if ttl and ttl > 0:
            raise OTPThrottleError(
                f"Please wait {ttl} seconds before requesting another OTP."
            )

        # Check hourly attempts
        attempts_key = cls.get_otp_attempts_key(user.id, purpose)
        attempts = cache.get(attempts_key, 0)
        if attempts >= 5:
            raise OTPThrottleError("OTP request limit exceeded. Please try again in an hour.")

        # Generate OTP
        otp = OTP.generate(user, purpose)

        # Set cooldown
        cache.set(cooldown_key, True, timeout=settings.OTP_RESEND_COOLDOWN_SECONDS)
        cache.set(attempts_key, attempts + 1, timeout=3600)

        # Send async via Celery
        from apps.notifications.tasks import send_otp_email_task
        if user.email:
            send_otp_email_task.delay(user.id, otp.code, purpose)
            logger.info(f"OTP sent to {user.email} for {purpose}")

        return otp

    @classmethod
    @transaction.atomic
    def verify_otp(cls, identifier, otp_code, purpose=OTP.Purpose.EMAIL_VERIFICATION):
        """Verify OTP and activate account if email verification."""
        user = cls._get_user_by_identifier(identifier)
        if not user:
            raise ValueError("User not found.")

        # Get the latest valid OTP
        otp = OTP.objects.filter(
            user=user, purpose=purpose, is_used=False
        ).order_by('-created_at').first()

        if not otp:
            raise ValueError("No active OTP found. Please request a new one.")

        success, message = otp.verify(otp_code)
        if not success:
            raise ValueError(message)

        # Mark user as verified
        if purpose == OTP.Purpose.EMAIL_VERIFICATION:
            user.is_verified = True
            user.save(update_fields=['is_verified'])

        logger.info(f"OTP verified for user {user.id}, purpose={purpose}")
        return user

    @staticmethod
    def _get_user_by_identifier(identifier):
        """Find user by email or phone."""
        if not identifier:
            return None
        if '@' in str(identifier):
            return User.objects.filter(email=identifier).first()
        return User.objects.filter(phone_number=identifier).first()
