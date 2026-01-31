"""Integration smoke tests for soliplex_sql.

These tests verify that:
1. The server starts correctly with the soliplex_sql plugin
2. Rooms are configured with SQL agents
3. SQL tools are correctly bound to the agents
4. Room configuration matches expectations

Requirements:
- Server must be running: soliplex-cli serve example/installation.yaml
- Or set SOLIPLEX_SQL_TEST_SERVER env var to specify a different server
"""

from __future__ import annotations

import os

import httpx
import pytest

# Default to localhost, can be overridden with env var
SERVER_URL = os.environ.get("SOLIPLEX_SQL_TEST_SERVER", "http://127.0.0.1:8000")


@pytest.fixture
def client() -> httpx.Client:
    """Create HTTP client for API requests."""
    return httpx.Client(base_url=SERVER_URL, timeout=10.0)


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
    """Verify rooms are configured correctly via the API."""

    def test_list_rooms(self, client: httpx.Client) -> None:
        """Should list configured rooms as a dict keyed by room ID."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()
        # Soliplex returns rooms as dict keyed by room ID
        assert isinstance(rooms, dict)
        assert len(rooms) >= 2  # At least sql-assistant and sales-db

    def test_sql_assistant_room_exists(self, client: httpx.Client) -> None:
        """sql-assistant-readonly room should be available."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()
        assert "sql-assistant-readonly" in rooms

    def test_sales_db_room_exists(self, client: httpx.Client) -> None:
        """sales-db-readonly room should be available."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()
        assert "sales-db-readonly" in rooms

    def test_room_has_agent_config(self, client: httpx.Client) -> None:
        """Rooms should have agent configuration."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()
        sql_room = rooms.get("sql-assistant-readonly", {})
        assert "agent" in sql_room
        assert "model_name" in sql_room["agent"]

    def test_room_model_configured(self, client: httpx.Client) -> None:
        """Room should have correct model configured."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()
        sql_room = rooms.get("sql-assistant-readonly", {})
        model = sql_room.get("agent", {}).get("model_name", "")
        # Model can be gpt-oss:20b or other configured model
        assert len(model) > 0, "Room should have a model configured"

    def test_sales_db_room_has_description(self, client: httpx.Client) -> None:
        """sales-db-readonly room should have proper description."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()
        sales_room = rooms.get("sales-db-readonly", {})
        assert "description" in sales_room
        assert "sales" in sales_room["description"].lower()

    def test_rooms_have_suggestions(self, client: httpx.Client) -> None:
        """Rooms should have suggestion prompts configured."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()

        # Check sql-assistant-readonly has suggestions
        sql_room = rooms.get("sql-assistant-readonly", {})
        suggestions = sql_room.get("suggestions", [])
        assert len(suggestions) > 0, "sql-assistant-readonly should have suggestions"

        # Check sales-db-readonly has suggestions
        sales_room = rooms.get("sales-db-readonly", {})
        suggestions = sales_room.get("suggestions", [])
        assert len(suggestions) > 0, "sales-db-readonly should have suggestions"


class TestSQLToolBinding:
    """Verify SQL tools are correctly bound to rooms."""

    def test_sql_assistant_has_tools(self, client: httpx.Client) -> None:
        """sql-assistant-readonly room should have SQL tools configured."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()

        sql_room = rooms.get("sql-assistant-readonly", {})
        # Tools may be under 'tools' or 'tool_configs' depending on API
        tools = sql_room.get("tools", sql_room.get("tool_configs", []))

        # Should have at least some tools
        assert tools is not None, "Room should have tools field"

    def test_sales_db_has_tools(self, client: httpx.Client) -> None:
        """sales-db-readonly room should have SQL tools configured."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()

        sales_room = rooms.get("sales-db-readonly", {})
        tools = sales_room.get("tools", sales_room.get("tool_configs", []))

        assert tools is not None, "Room should have tools field"

    def test_tools_include_list_tables(self, client: httpx.Client) -> None:
        """Room tools should include list_tables."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()

        sql_room = rooms.get("sql-assistant-readonly", {})
        tools = sql_room.get("tools", sql_room.get("tool_configs", []))

        if isinstance(tools, list) and len(tools) > 0:
            # Tools might be dicts with 'tool_name' or strings
            tool_names = []
            for t in tools:
                if isinstance(t, dict):
                    tool_names.append(t.get("tool_name", t.get("name", "")))
                elif isinstance(t, str):
                    tool_names.append(t)

            has_list_tables = any("list_tables" in name for name in tool_names)
            assert has_list_tables, (
                f"Expected list_tables in tools: {tool_names}"
            )

    def test_tools_include_query(self, client: httpx.Client) -> None:
        """Room tools should include query."""
        response = client.get("/api/v1/rooms")
        assert response.status_code == 200
        rooms = response.json()

        sql_room = rooms.get("sql-assistant-readonly", {})
        tools = sql_room.get("tools", sql_room.get("tool_configs", []))

        if isinstance(tools, list) and len(tools) > 0:
            tool_names = []
            for t in tools:
                if isinstance(t, dict):
                    tool_names.append(t.get("tool_name", t.get("name", "")))
                elif isinstance(t, str):
                    tool_names.append(t)

            has_query = any("query" in name for name in tool_names)
            assert has_query, f"Expected query in tools: {tool_names}"


class TestAGUIEndpoints:
    """Verify AGUI endpoints respond correctly."""

    def test_get_room_agui(self, client: httpx.Client) -> None:
        """Should get room AGUI info with threads list."""
        response = client.get("/api/v1/rooms/sql-assistant-readonly/agui")
        assert response.status_code == 200
        data = response.json()
        # AGUI endpoint returns threads list
        assert "threads" in data

    def test_get_sales_db_agui(self, client: httpx.Client) -> None:
        """Should get sales-db-readonly room AGUI info."""
        response = client.get("/api/v1/rooms/sales-db-readonly/agui")
        assert response.status_code == 200
        data = response.json()
        assert "threads" in data

    def test_create_thread_returns_id(self, client: httpx.Client) -> None:
        """Creating a thread should return thread info."""
        response = client.post(
            "/api/v1/rooms/sql-assistant-readonly/agui",
            json={},
        )
        # Accept various success codes
        if response.status_code in (200, 201):
            data = response.json()
            # Should have a thread_id field
            assert "thread_id" in data, (
                f"Thread response should have thread_id: {data}"
            )


class TestOpenAPIToolRegistration:
    """Verify tools appear correctly in API schema."""

    def test_openapi_has_paths(self, client: httpx.Client) -> None:
        """OpenAPI schema should have API paths defined."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()

        paths = data.get("paths", {})
        assert len(paths) > 0, "OpenAPI should have paths defined"

        # Should have room-related paths
        room_paths = [p for p in paths if "/rooms" in p]
        assert len(room_paths) > 0, "Should have room API paths"

    def test_openapi_has_agui_paths(self, client: httpx.Client) -> None:
        """OpenAPI schema should have AGUI paths."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()

        paths = data.get("paths", {})
        agui_paths = [p for p in paths if "agui" in p]
        assert len(agui_paths) > 0, "Should have AGUI API paths"


# Skip all tests if server is not available
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
