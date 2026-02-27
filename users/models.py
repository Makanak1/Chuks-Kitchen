"""
apps/users/models.py
Custom User Model + OTP + Referral
"""
import uuid
import random
import string
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.conf import settings


class UserManager(BaseUserManager):
    def create_user(self, email=None, phone_number=None, password=None, **extra_fields):
        if not email and not phone_number:
            raise ValueError("User must have email or phone number")
        if email:
            email = self.normalize_email(email)
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        extra_fields.setdefault('is_verified', True)
        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        ADMIN = 'admin', 'Admin'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, null=True, blank=True, db_index=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    referral_code = models.CharField(max_length=20, unique=True, blank=True, db_index=True)
    referred_by = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='referrals'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['email', 'is_verified']),
            models.Index(fields=['phone_number', 'is_verified']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return self.email or self.phone_number

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self._generate_referral_code()
        super().save(*args, **kwargs)

    def _generate_referral_code(self):
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not User.objects.filter(referral_code=code).exists():
                return code


class OTP(models.Model):
    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = 'email_verification', 'Email Verification'
        PHONE_VERIFICATION = 'phone_verification', 'Phone Verification'
        PASSWORD_RESET = 'password_reset', 'Password Reset'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=10)
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'otps'
        indexes = [
            models.Index(fields=['user', 'purpose', 'is_used']),
            models.Index(fields=['code', 'purpose']),
        ]

    def __str__(self):
        return f"OTP({self.user}, {self.purpose})"

    @classmethod
    def generate(cls, user, purpose):
        """Invalidate old OTPs and create a new one."""
        cls.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
        code = ''.join(random.choices(string.digits, k=settings.OTP_LENGTH))
        expiry = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        return cls.objects.create(user=user, code=code, purpose=purpose, expires_at=expiry)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired and self.attempts < settings.OTP_MAX_ATTEMPTS

    def verify(self, code):
        if not self.is_valid:
            return False, self._get_invalid_reason()
        self.attempts += 1
        if self.code != code:
            self.save(update_fields=['attempts'])
            remaining = settings.OTP_MAX_ATTEMPTS - self.attempts
            return False, f"Invalid OTP. {remaining} attempts remaining."
        self.is_used = True
        self.save(update_fields=['is_used', 'attempts'])
        return True, "OTP verified successfully."

    def _get_invalid_reason(self):
        if self.is_used:
            return "OTP has already been used."
        if self.is_expired:
            return "OTP has expired. Please request a new one."
        if self.attempts >= settings.OTP_MAX_ATTEMPTS:
            return "Maximum OTP attempts exceeded. Please request a new one."
        return "Invalid OTP."


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    default_delivery_address = models.TextField(blank=True)
    default_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'
