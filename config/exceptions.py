"""
config/exceptions.py
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger('apps')


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        return Response({
            'success': False,
            'message': _extract_message(response.data),
            'errors': response.data,
        }, status=response.status_code)

    # Unhandled exceptions
    logger.exception(f"Unhandled exception in {context.get('view')}: {exc}")
    return Response({
        'success': False,
        'message': 'An unexpected error occurred. Please try again.',
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _extract_message(data):
    if isinstance(data, dict):
        for key in ['detail', 'message', 'non_field_errors']:
            if key in data:
                val = data[key]
                if isinstance(val, list):
                    return str(val[0])
                return str(val)
        # Return first field error
        for val in data.values():
            if isinstance(val, list) and val:
                return str(val[0])
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data)


# ──────────────────────────────────────────────
# config/middleware.py
# ──────────────────────────────────────────────
import time
import uuid as uuid_lib


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = str(uuid_lib.uuid4())[:8]
        start = time.time()

        response = self.get_response(request)

        duration_ms = round((time.time() - start) * 1000, 2)
        user = getattr(request, 'user', None)
        user_id = str(user.id) if user and user.is_authenticated else 'anon'

        logger.info(
            f"[{request_id}] {request.method} {request.path} "
            f"-> {response.status_code} ({duration_ms}ms) user={user_id}"
        )
        return response
