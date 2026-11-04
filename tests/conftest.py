import pytest
from app.deps import authorize
from app.main import app

@pytest.fixture(autouse=True)
def open_api_for_old_tests(request):
    if "security" in request.node.fspath.basename or "api_reports" in request.node.fspath.basename:
        yield
        return
    app.dependency_overrides[authorize] = lambda: None
    yield
    app.dependency_overrides.pop(authorize, None)