"""
config/urls.py - Main URL configuration
"""
from django.contrib import admin
# from django.http import HttpResponse
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('config.api_urls')),
    # path('', lambda request: HttpResponse("ChuksKitchen API Running 🚀")),
]

# ─── config/api_urls.py ───────────────────────────────────────────
"""
All API route definitions
"""
# Save this content as config/api_urls.py

