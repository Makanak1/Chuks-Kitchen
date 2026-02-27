"""
config/api_urls.py
Full API URL structure for Chuks Kitchen
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from users.views import (
    RegisterView, VerifyOTPView, ResendOTPView,
    LoginView, LogoutView, MeView
)
from menu.views import (
    CategoryViewSet, FoodItemViewSet,
    CartView, CartItemView, CartItemQuantityView
)
from orders.views import (
    PlaceOrderView, CustomerOrderListView, CustomerOrderDetailView,
    CancelOrderView, AdminOrderListView, AdminUpdateOrderStatusView
)
from payments.views import (
    InitiatePaymentView, VerifyPaymentView, PaymentHistoryView,
    PaystackWebhookView, PaystackCallbackView
)

router = DefaultRouter()
router.register(r'menu/categories', CategoryViewSet, basename='category')
router.register(r'menu/items', FoodItemViewSet, basename='food-item')

urlpatterns = [

    # ── Auth ──────────────────────────────────────────────────────
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('auth/resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # ── User Profile ──────────────────────────────────────────────
    path('users/me/', MeView.as_view(), name='me'),

    # ── Menu (ViewSets via Router) ────────────────────────────────
    path('', include(router.urls)),

    # ── Cart ──────────────────────────────────────────────────────
    path('cart/', CartView.as_view(), name='cart'),
    path('cart/items/', CartItemView.as_view(), name='cart-items'),
    path('cart/items/<uuid:item_id>/', CartItemView.as_view(), name='cart-item-delete'),
    path('cart/items/<uuid:item_id>/quantity/', CartItemQuantityView.as_view(), name='cart-item-quantity'),

    # ── Customer Orders ───────────────────────────────────────────
    path('orders/', CustomerOrderListView.as_view(), name='customer-orders'),
    path('orders/place/', PlaceOrderView.as_view(), name='place-order'),
    path('orders/<uuid:order_id>/', CustomerOrderDetailView.as_view(), name='order-detail'),
    path('orders/<uuid:order_id>/cancel/', CancelOrderView.as_view(), name='cancel-order'),

    # ── Admin Orders ──────────────────────────────────────────────
    path('admin/orders/', AdminOrderListView.as_view(), name='admin-orders'),
    path('admin/orders/<uuid:order_id>/status/', AdminUpdateOrderStatusView.as_view(), name='admin-order-status'),

    # ── Payments ──────────────────────────────────────────────────
    path('payments/initiate/', InitiatePaymentView.as_view(), name='payment-initiate'),
    path('payments/verify/<str:reference>/', VerifyPaymentView.as_view(), name='payment-verify'),
    path('payments/history/', PaymentHistoryView.as_view(), name='payment-history'),
    path('payments/paystack/webhook/', PaystackWebhookView.as_view(), name='paystack-webhook'),
    path('payments/paystack/callback/', PaystackCallbackView.as_view(), name='paystack-callback'),
]
