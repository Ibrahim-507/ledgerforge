"""Task 16: every API route lives under /api/v1. One line in main.py does it for ALL routers, including old ones:
    prefix_all(app)           # right after  app = FastAPI(...)
Routers that must stay at the root (the login page) set  router._unversioned = True.
The permission table keeps using the short paths (/employees ...): normalize() removes the prefix before the lookup."""
API_PREFIX = "/api/v1"


def normalize(route_path: str) -> str:
    """'/api/v1/employees/{employee_id}' -> '/employees/{employee_id}'. Anything else is returned unchanged."""
    if route_path == API_PREFIX:
        return "/"
    if route_path.startswith(API_PREFIX + "/"):
        return route_path[len(API_PREFIX):]
    return route_path


def prefix_all(app, prefix: str = API_PREFIX):
    """From now on app.include_router(router) adds the version prefix, unless the router is marked _unversioned."""
    original = app.include_router

    def include_router(router, *args, **kwargs):
        if getattr(router, "_unversioned", False) or kwargs.get("prefix", "").startswith(prefix):
            return original(router, *args, **kwargs)
        kwargs["prefix"] = prefix + kwargs.get("prefix", "")
        return original(router, *args, **kwargs)

    app.include_router = include_router
    return app
