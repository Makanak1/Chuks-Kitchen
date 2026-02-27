"""
config/urls.py - Main URL configuration
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('config.api_urls')),
]

# ─── config/api_urls.py ───────────────────────────────────────────
"""
All API route definitions
"""
# Save this content as config/api_urls.py

