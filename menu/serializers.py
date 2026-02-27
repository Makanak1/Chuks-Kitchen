"""
apps/menu/serializers.py
"""
from rest_framework import serializers
from .models import Category, FoodItem, Cart, CartItem


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'image', 'is_active', 'display_order']


class FoodItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = FoodItem
        fields = [
            'id', 'name', 'description', 'price', 'image', 'category', 'category_name',
            'is_available', 'preparation_time_minutes', 'calories', 'is_featured',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FoodItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodItem
        fields = ['name', 'description', 'price', 'image', 'category', 'is_available',
                  'preparation_time_minutes', 'calories', 'is_featured']

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value


class CartItemSerializer(serializers.ModelSerializer):
    food_item_name = serializers.CharField(source='food_item.name', read_only=True)
    food_item_price = serializers.DecimalField(source='food_item.price', max_digits=10, decimal_places=2, read_only=True)
    food_item_available = serializers.BooleanField(source='food_item.is_available', read_only=True)
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = [
            'id', 'food_item', 'food_item_name', 'food_item_price',
            'food_item_available', 'quantity', 'unit_price', 'subtotal'
        ]
        read_only_fields = ['id', 'unit_price', 'subtotal']


class AddToCartSerializer(serializers.Serializer):
    food_item_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=50)

    def validate_food_item_id(self, value):
        try:
            item = FoodItem.objects.get(id=value)
            if not item.is_available:
                raise serializers.ValidationError("This item is currently not available.")
            self._food_item = item
            return value
        except FoodItem.DoesNotExist:
            raise serializers.ValidationError("Food item not found.")


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.ReadOnlyField()
    item_count = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_price', 'item_count', 'updated_at']
