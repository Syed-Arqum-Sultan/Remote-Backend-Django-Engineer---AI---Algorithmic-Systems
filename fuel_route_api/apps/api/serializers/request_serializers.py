from rest_framework import serializers


class RouteOptimizeRequestSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=512, trim_whitespace=True)
    destination = serializers.CharField(max_length=512, trim_whitespace=True)
    include_geometry = serializers.BooleanField(required=False, default=True)
