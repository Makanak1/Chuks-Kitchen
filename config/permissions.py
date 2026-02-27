"""
config/permissions.py
Role-based access control permissions
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    """Only admin users."""
    message = "Admin access required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsCustomer(BasePermission):
    """Only customer users."""
    message = "Customer access required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_customer)


class IsAdminOrReadOnly(BasePermission):
    """Admins can write; authenticated users can read."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_admin


class IsOrderOwnerOrAdmin(BasePermission):
    """Order owner or admin."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        return obj.customer == request.user
