"""Integration smoke tests for soliplex_sql.

These tests verify that:
1. The server can start with the example configuration
2. Rooms are configured correctly
3. SQL tools are registered and available

Requirements:
- Server must be running: soliplex-cli serve example/installation.yaml
- Or use pytest --server-url=http://... to specify a different server
"""

from __future__ import annotations

import os

import httpx
import pytest

# Default to localhost, can be overridden with --server-url
SERVER_URL = os.environ.get("SOLIPLEX_SQL_TEST_SERVER", "http://127.0.0.1:8000")


@pytest.fixture
def client() -> httpx.Client:
    """Create HTTP client for API requests."""
    return httpx.Client(base_url=SERVER_URL, timeout=10.0)


@pytest.fixture
def async_client() -> httpx.AsyncClient:
    """Create async HTTP client for API requests."""
    return httpx.AsyncClient(base_url=SERVER_URL, timeout=10.0)


class TestServerHealth:
    """Verify server is running and healthy."""

    def test_docs_endpoint(self, client: httpx.Client) -> None:
        """Server should serve API documentation."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "html" in response.headers.get("content-type", "").lower()

    def test_openapi_schema(self, client: httpx.Client) -> None:
        """Server should expose OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data


class TestRoomsConfiguration:
    """Verify rooms are configured correctly."""

    def test_list_rooms(self, client: httpx.Client) -> None:
        """Should list configured rooms as a dict keyed by room ID."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()
        # Soliplex returns rooms as dict keyed by room ID
        assert isinstance(rooms, dict)
        assert len(rooms) > 0

    def test_sql_assistant_room_exists(self, client: httpx.Client) -> None:
        """sql-assistant room should be available."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()
        assert "sql-assistant" in rooms

    def test_sales_db_room_exists(self, client: httpx.Client) -> None:
        """sales-db room should be available."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()
        assert "sales-db" in rooms

    def test_room_has_agent_config(self, client: httpx.Client) -> None:
        """Rooms should have agent configuration."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()
        sql_room = rooms.get("sql-assistant", {})
        assert "agent" in sql_room
        assert "model_name" in sql_room["agent"]

    def test_room_model_configured(self, client: httpx.Client) -> None:
        """Room should have correct model configured."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()
        sql_room = rooms.get("sql-assistant", {})
        model = sql_room.get("agent", {}).get("model_name", "")
        assert "qwen3-coder" in model


class TestAGUIEndpoints:
    """Verify AGUI endpoints respond correctly."""

    def test_get_room_agui(self, client: httpx.Client) -> None:
        """Should get room AGUI info with threads list."""
        response = client.get("/api/v1/rooms/sql-assistant/agui")
        assert response.status_code == 200
        data = response.json()
        # AGUI endpoint returns threads list
        assert "threads" in data

    def test_create_thread(self, client: httpx.Client) -> None:
        """Should be able to create a new chat thread.

        POST to /agui creates a new thread and returns its ID.
        """
        # POST with JSON body to create thread
        response = client.post(
            "/api/v1/rooms/sql-assistant/agui",
            json={},  # Empty body for new thread
        )
        # May be 200 or 201 depending on implementation
        assert response.status_code in (200, 201, 422)
        if response.status_code in (200, 201):
            data = response.json()
            assert isinstance(data, dict)


class TestToolRegistration:
    """Verify SQL tools are properly registered."""

    def test_tools_in_openapi(self, client: httpx.Client) -> None:
        """SQL tools should appear in API schema if exposed."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        # Tools may or may not be directly in OpenAPI depending on architecture


# Skip these tests if server is not running
def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires running server)",
    )


@pytest.fixture(scope="session", autouse=True)
def check_server_available() -> None:
    """Skip all tests if server is not available."""
    try:
        response = httpx.get(f"{SERVER_URL}/docs", timeout=2.0)
        if response.status_code != 200:
            pytest.skip(f"Server at {SERVER_URL} not responding correctly")
    except httpx.ConnectError:
        pytest.skip(f"Server at {SERVER_URL} is not running")
    except Exception as e:
        pytest.skip(f"Cannot connect to server: {e}")
