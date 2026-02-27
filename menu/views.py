"""
apps/menu/views.py
Food items, categories, cart management
"""
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet, ModelViewSet

from config.permissions import IsAdmin, IsCustomer, IsAdminOrReadOnly
from .models import Category, FoodItem, Cart, CartItem
from .serializers import (
    CategorySerializer, FoodItemSerializer, FoodItemWriteSerializer,
    CartSerializer, AddToCartSerializer, CartItemSerializer
)

logger = logging.getLogger('apps.menu')


class CategoryViewSet(ModelViewSet):
    queryset = Category.objects.filter(is_active=True).order_by('display_order')
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name']


class FoodItemViewSet(ModelViewSet):
    queryset = FoodItem.objects.select_related('category').order_by('-is_featured', 'name')
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name', 'description']
    filterset_fields = ['category', 'is_available', 'is_featured']
    ordering_fields = ['price', 'name', 'created_at']

    def get_serializer_class(self):
        if self.request.method in ['POST', 'PUT', 'PATCH']:
            return FoodItemWriteSerializer
        return FoodItemSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Non-admins only see available items
        if not self.request.user.is_authenticated or not self.request.user.is_admin:
            qs = qs.filter(is_available=True)
        return qs


class CartView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response({'success': True, 'data': serializer.data})

    def delete(self, request):
        """Clear cart."""
        Cart.objects.filter(user=request.user).delete()
        return Response({'success': True, 'message': 'Cart cleared.'})


class CartItemView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):
        """Add or update item in cart."""
        serializer = AddToCartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=400)

        food_item = serializer._food_item
        quantity = serializer.validated_data['quantity']

        with transaction.atomic():
            cart, _ = Cart.objects.get_or_create(user=request.user)
            cart_item, created = CartItem.objects.update_or_create(
                cart=cart,
                food_item=food_item,
                defaults={
                    'quantity': quantity,
                    'unit_price': food_item.price,
                }
            )

        action = 'added to' if created else 'updated in'
        return Response({
            'success': True,
            'message': f'{food_item.name} {action} cart.',
            'data': CartItemSerializer(cart_item).data
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, item_id):
        """Remove item from cart."""
        deleted, _ = CartItem.objects.filter(
            cart__user=request.user, id=item_id
        ).delete()
        if deleted:
            return Response({'success': True, 'message': 'Item removed from cart.'})
        return Response({'success': False, 'message': 'Item not found in cart.'}, status=404)


class CartItemQuantityView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def patch(self, request, item_id):
        """Update quantity of a specific cart item."""
        quantity = request.data.get('quantity')
        if not quantity or int(quantity) < 1:
            return Response({'success': False, 'message': 'Invalid quantity.'}, status=400)

        updated = CartItem.objects.filter(
            cart__user=request.user, id=item_id
        ).update(quantity=quantity)

        if updated:
            return Response({'success': True, 'message': 'Cart updated.'})
        return Response({'success': False, 'message': 'Item not found.'}, status=404)
