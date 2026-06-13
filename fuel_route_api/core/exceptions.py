class DomainError(Exception):
    code: str = "DOMAIN_ERROR"
    status_code: int = 400

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"
    status_code = 400


class GeocodeNotFoundError(DomainError):
    code = "GEOCODE_NOT_FOUND"
    status_code = 400


class RouteNotFoundError(DomainError):
    code = "ROUTE_NOT_FOUND"
    status_code = 422


class NoFeasibleFuelPlanError(DomainError):
    code = "NO_FEASIBLE_FUEL_PLAN"
    status_code = 422


class UpstreamUnavailableError(DomainError):
    code = "UPSTREAM_UNAVAILABLE"
    status_code = 503
