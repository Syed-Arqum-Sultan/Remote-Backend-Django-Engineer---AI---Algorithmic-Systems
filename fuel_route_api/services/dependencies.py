from services.fuel_optimizer import FuelOptimizer
from services.geocoding_service import GeocodingService
from services.route_orchestrator import RouteOrchestrator
from services.route_service import RouteService


def get_route_orchestrator() -> RouteOrchestrator:
    return RouteOrchestrator(
        geocoding_service=GeocodingService(),
        route_service=RouteService(),
        fuel_optimizer=FuelOptimizer(),
    )
