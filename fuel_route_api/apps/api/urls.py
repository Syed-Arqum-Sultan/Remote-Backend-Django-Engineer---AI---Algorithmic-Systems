from django.urls import path

from apps.api.views.health_view import HealthView
from apps.api.views.route_optimize_view import RouteOptimizeView

urlpatterns = [
    path("routes/optimize/", RouteOptimizeView.as_view(), name="route-optimize"),
    path("health/", HealthView.as_view(), name="health"),
]
