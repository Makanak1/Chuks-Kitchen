"""
apps/users/serializers.py
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import OTP, UserProfile

User = get_user_model()


class UserRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    password = serializers.CharField(min_length=8, write_only=True)
    referral_code = serializers.CharField(required=False, allow_blank=True, max_length=20)

    def validate(self, attrs):
        email = attrs.get('email', '').strip()
        phone = attrs.get('phone_number', '').strip()

        if not email and not phone:
            raise serializers.ValidationError("Provide either email or phone number.")

        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})

        if phone and User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError({"phone_number": "This phone number is already registered."})

        # Validate referral code
        referral_code = attrs.get('referral_code', '').strip()
        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
                attrs['_referrer'] = referrer
            except User.DoesNotExist:
                raise serializers.ValidationError({"referral_code": "Invalid referral code."})

        attrs['email'] = email or None
        attrs['phone_number'] = phone or None
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        referrer = validated_data.pop('_referrer', None)
        validated_data.pop('referral_code', None)

        user = User.objects.create_user(
            email=validated_data.get('email'),
            phone_number=validated_data.get('phone_number'),
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password'],
            referred_by=referrer,
        )
        UserProfile.objects.create(user=user)
        return user


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    otp_code = serializers.CharField(max_length=10)

    def validate(self, attrs):
        if not attrs.get('email') and not attrs.get('phone_number'):
            raise serializers.ValidationError("Provide email or phone number.")
        return attrs


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        # Support login via email or phone
        identifier = attrs.get('email') or attrs.get(self.username_field)
        password = attrs.get('password')

        # Try phone if not email
        user = None
        from django.contrib.auth import authenticate
        if '@' in str(identifier):
            user = authenticate(request=self.context.get('request'), email=identifier, password=password)
        else:
            try:
                u = User.objects.get(phone_number=identifier)
                if u.check_password(password):
                    user = u
            except User.DoesNotExist:
                pass

        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        if not user.is_verified:
            raise serializers.ValidationError("Account not verified. Please verify your OTP.")
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled.")

        data = super().validate(attrs)
        data['user'] = UserDetailSerializer(user).data
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['email'] = user.email or ''
        return token


class UserDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'first_name', 'last_name',
            'full_name', 'role', 'is_verified', 'referral_code', 'created_at'
        ]
        read_only_fields = ['id', 'role', 'is_verified', 'referral_code', 'created_at']


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['avatar', 'default_delivery_address', 'default_phone']
