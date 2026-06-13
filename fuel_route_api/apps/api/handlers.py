from rest_framework.response import Response
from rest_framework.views import exception_handler

from core.exceptions import DomainError


def custom_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
            status=exc.status_code,
        )
    return exception_handler(exc, context)
