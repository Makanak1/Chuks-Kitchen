"""
apps/users/views.py
Registration, OTP verification, login
"""
import logging

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import OTP
from .serializers import (
    CustomTokenObtainPairSerializer,
    OTPVerifySerializer,
    ResendOTPSerializer,
    UserDetailSerializer,
    UserRegistrationSerializer,
)
from .services import OTPThrottleError, UserService

User = get_user_model()
logger = logging.getLogger('apps.users')


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        user = serializer.save()
        # Send OTP
        try:
            UserService.send_otp(user, OTP.Purpose.EMAIL_VERIFICATION)
        except OTPThrottleError as e:
            logger.warning(f"OTP throttle on registration for {user.id}: {e}")

        return Response({
            'success': True,
            'message': 'Registration successful. Please verify your account with the OTP sent to your email.',
            'data': {'user_id': str(user.id), 'email': user.email}
        }, status=status.HTTP_201_CREATED)


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp'

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=400)

        identifier = serializer.validated_data.get('email') or serializer.validated_data.get('phone_number')
        otp_code = serializer.validated_data['otp_code']

        try:
            user = UserService.verify_otp(identifier, otp_code)
        except ValueError as e:
            return Response({'success': False, 'message': str(e)}, status=400)

        # Issue tokens immediately after verification
        refresh = RefreshToken.for_user(user)
        return Response({
            'success': True,
            'message': 'Account verified successfully.',
            'data': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserDetailSerializer(user).data,
            }
        }, status=200)


class ResendOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp'

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=400)

        identifier = serializer.validated_data.get('email') or serializer.validated_data.get('phone_number')
        user = UserService._get_user_by_identifier(identifier)

        if not user:
            # Don't reveal if user exists or not
            return Response({'success': True, 'message': 'If an account exists, OTP has been sent.'})

        if user.is_verified:
            return Response({'success': False, 'message': 'Account is already verified.'}, status=400)

        try:
            UserService.send_otp(user, OTP.Purpose.EMAIL_VERIFICATION)
        except OTPThrottleError as e:
            return Response({'success': False, 'message': str(e)}, status=429)

        return Response({'success': True, 'message': 'OTP has been resent.'})


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            response.data = {'success': True, 'data': response.data}
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'success': True, 'message': 'Logged out successfully.'})
        except Exception:
            return Response({'success': False, 'message': 'Invalid token.'}, status=400)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'success': True,
            'data': UserDetailSerializer(request.user).data
        })

    def patch(self, request):
        serializer = UserDetailSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'success': True, 'data': serializer.data})
        return Response({'success': False, 'errors': serializer.errors}, status=400)
