from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.serializers.request_serializers import RouteOptimizeRequestSerializer
from apps.api.serializers.response_serializers import serialize_optimize_result
from services.dependencies import get_route_orchestrator


class RouteOptimizeView(APIView):
    def post(self, request: Request) -> Response:
        serializer = RouteOptimizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        orchestrator = get_route_orchestrator()
        result = orchestrator.optimize_route(
            start_address=serializer.validated_data["start"],
            destination_address=serializer.validated_data["destination"],
            include_geometry=serializer.validated_data.get("include_geometry", True),
        )
        return Response(
            serialize_optimize_result(
                result,
                include_geometry=serializer.validated_data.get("include_geometry", True),
            ),
            status=status.HTTP_200_OK,
        )
