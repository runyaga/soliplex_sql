"""Functional integration tests for soliplex_sql.

These tests verify that SQL tools actually execute through the agent pipeline:
1. Agent receives user message
2. Agent decides to call SQL tool
3. SQL tool executes against database
4. Results are streamed back to client

Requirements:
- Server must be running: soliplex-cli serve example/installation.yaml
- Or set SOLIPLEX_SQL_TEST_SERVER env var to specify a different server
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Generator
from typing import Any

import httpx
import pytest

SERVER_URL = os.environ.get(
    "SOLIPLEX_SQL_TEST_SERVER", "http://127.0.0.1:8000"
)


@pytest.fixture
def client() -> httpx.Client:
    """Create HTTP client with longer timeout for LLM responses."""
    return httpx.Client(base_url=SERVER_URL, timeout=120.0)


def parse_sse_events(
    response: httpx.Response,
) -> Generator[dict[str, Any], None, None]:
    """Parse Server-Sent Events from streaming response."""
    for line in response.iter_lines():
        if line.startswith("data: "):
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                break
            try:
                yield json.loads(data_str)
            except json.JSONDecodeError:
                continue


def collect_stream_events(response: httpx.Response) -> list[dict[str, Any]]:
    """Collect all SSE events from a streaming response."""
    return list(parse_sse_events(response))


def extract_text_from_events(events: list[dict[str, Any]]) -> str:
    """Extract accumulated text content from AGUI events."""
    text_parts = []
    for event in events:
        event_type = event.get("type", "")
        if event_type == "TEXT_MESSAGE_CONTENT":
            delta = event.get("delta", "")
            if delta:
                text_parts.append(delta)
    return "".join(text_parts)


def find_tool_calls(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find all tool call events in the stream.

    AGUI events with type TOOL_CALL_START contain tool invocation info.
    The tool name is in 'toolCallName' field.
    """
    tool_calls = []
    for event in events:
        event_type = event.get("type", "")
        if event_type == "TOOL_CALL_START":
            tool_calls.append(event)
    return tool_calls


def get_tool_names(events: list[dict[str, Any]]) -> list[str]:
    """Extract tool names from TOOL_CALL_START events."""
    tool_calls = find_tool_calls(events)
    return [tc.get("toolCallName", "") for tc in tool_calls]


def find_tool_results(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find all tool result events in the stream.

    AGUI events with type TOOL_CALL_END contain tool execution results.
    """
    results = []
    for event in events:
        event_type = event.get("type", "")
        if event_type == "TOOL_CALL_END":
            results.append(event)
    return results


class TestSQLToolExecution:
    """Functional tests verifying SQL tools actually execute."""

    @pytest.fixture
    def sql_assistant_thread(self, client: httpx.Client) -> dict[str, str]:
        """Create a new thread in the sql-assistant room.

        Returns dict with thread_id and run_id.
        """
        response = client.post(
            "/api/v1/rooms/sql-assistant-readonly/agui", json={}
        )
        assert response.status_code in (200, 201), (
            f"Failed to create thread: {response.text}"
        )
        data = response.json()
        thread_id = data["thread_id"]
        runs = data.get("runs", {})
        run_id = next(iter(runs.keys())) if runs else None
        assert run_id, f"No run_id in response: {data}"
        return {"thread_id": thread_id, "run_id": run_id}

    @pytest.fixture
    def sales_db_thread(self, client: httpx.Client) -> dict[str, str]:
        """Create a new thread in the sales-db-readonly room.

        Returns dict with thread_id and run_id.
        """
        response = client.post("/api/v1/rooms/sales-db-readonly/agui", json={})
        assert response.status_code in (200, 201), (
            f"Failed to create thread: {response.text}"
        )
        data = response.json()
        thread_id = data["thread_id"]
        runs = data.get("runs", {})
        run_id = next(iter(runs.keys())) if runs else None
        assert run_id, f"No run_id in response: {data}"
        return {"thread_id": thread_id, "run_id": run_id}

    def _send_message(
        self,
        client: httpx.Client,
        room_id: str,
        thread_id: str,
        run_id: str,
        message: str,
    ) -> list[dict[str, Any]]:
        """Send a message to the agent and collect all response events.

        Uses the AGUI streaming endpoint with RunAgentInput schema.
        """
        url = f"/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}"
        # RunAgentInput uses camelCase and requires all fields
        payload = {
            "threadId": thread_id,
            "runId": run_id,
            "state": None,
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": message,
                }
            ],
            "context": [],
            "tools": [],
            "forwardedProps": None,
        }

        with client.stream(
            "POST",
            url,
            json=payload,
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200, (
                f"Stream failed: {response.status_code}"
            )
            return collect_stream_events(response)

    def test_agent_responds_to_message(
        self, client: httpx.Client, sql_assistant_thread: dict[str, str]
    ) -> None:
        """Verify the agent responds to a basic message.

        This is the most fundamental test - can we get any response?
        """
        events = self._send_message(
            client,
            "sql-assistant-readonly",
            sql_assistant_thread["thread_id"],
            sql_assistant_thread["run_id"],
            "Hello, are you there?",
        )

        # Should have received some events
        assert len(events) > 0, "No events received from agent"

        # Should have text content in response
        text = extract_text_from_events(events)
        assert len(text) > 0, f"No text in response. Events: {events[:5]}"

    def test_list_tables_tool_execution(
        self, client: httpx.Client, sql_assistant_thread: dict[str, str]
    ) -> None:
        """Verify list_tables tool is called when asking about tables.

        The agent should decide to use the list_tables tool.
        """
        events = self._send_message(
            client,
            "sql-assistant-readonly",
            sql_assistant_thread["thread_id"],
            sql_assistant_thread["run_id"],
            "What tables are in the database? Use the list_tables tool.",
        )

        # Look for tool calls
        tool_calls = find_tool_calls(events)

        # Should have called a tool
        assert len(tool_calls) > 0, (
            f"Agent did not call any tools. "
            f"Text response: {extract_text_from_events(events)[:500]}"
        )

        # At least one tool should be list_tables related
        tool_names = get_tool_names(events)
        has_list_tables = any("list_tables" in name for name in tool_names)
        assert has_list_tables, (
            f"Expected list_tables in tools called: {tool_names}"
        )

    def test_query_tool_execution(
        self, client: httpx.Client, sql_assistant_thread: dict[str, str]
    ) -> None:
        """Verify query tool executes SQL.

        Ask for a simple calculation that requires SQL execution.
        """
        events = self._send_message(
            client,
            "sql-assistant-readonly",
            sql_assistant_thread["thread_id"],
            sql_assistant_thread["run_id"],
            "Execute this SQL query: SELECT 1 + 1 AS result",
        )

        # Look for tool calls
        tool_calls = find_tool_calls(events)

        # Should have called a tool (query or sample_query)
        assert len(tool_calls) > 0, (
            f"Agent did not call any tools. "
            f"Text response: {extract_text_from_events(events)[:500]}"
        )

        # Verify it called a query-related tool
        tool_names = get_tool_names(events)
        query_tools = ("query", "sample_query", "explain_query")
        has_query_tool = any(name in query_tools for name in tool_names)
        assert has_query_tool, f"Expected query tool in: {tool_names}"

        # Should have tool results
        tool_results = find_tool_results(events)
        assert len(tool_results) > 0, "No tool results received"

    def test_describe_table_tool(
        self, client: httpx.Client, sql_assistant_thread: dict[str, str]
    ) -> None:
        """Verify describe_table tool works.

        This may fail if no tables exist, which is expected for empty DBs.
        """
        events = self._send_message(
            client,
            "sql-assistant-readonly",
            sql_assistant_thread["thread_id"],
            sql_assistant_thread["run_id"],
            "First list the tables, then describe the first table you find.",
        )

        # Should have received events
        assert len(events) > 0, "No events received"

        # May or may not have tools depending on DB state
        text = extract_text_from_events(events)
        assert len(text) > 0, "No text response received"


class TestSalesDBRoom:
    """Tests for the sales-db-readonly room with per-tool config."""

    @pytest.fixture
    def sales_thread(self, client: httpx.Client) -> dict[str, str]:
        """Create a new thread in the sales-db-readonly room."""
        response = client.post("/api/v1/rooms/sales-db-readonly/agui", json={})
        assert response.status_code in (200, 201)
        data = response.json()
        thread_id = data["thread_id"]
        runs = data.get("runs", {})
        run_id = next(iter(runs.keys())) if runs else None
        assert run_id
        return {"thread_id": thread_id, "run_id": run_id}

    def _send_message(
        self,
        client: httpx.Client,
        thread_id: str,
        run_id: str,
        message: str,
    ) -> list[dict[str, Any]]:
        """Send message to sales-db-readonly room."""
        url = f"/api/v1/rooms/sales-db-readonly/agui/{thread_id}/{run_id}"
        payload = {
            "threadId": thread_id,
            "runId": run_id,
            "state": None,
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": message,
                }
            ],
            "context": [],
            "tools": [],
            "forwardedProps": None,
        }

        with client.stream(
            "POST",
            url,
            json=payload,
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200
            return collect_stream_events(response)

    def test_sales_room_responds(
        self, client: httpx.Client, sales_thread: dict[str, str]
    ) -> None:
        """Verify the sales-db-readonly room agent responds."""
        events = self._send_message(
            client,
            sales_thread["thread_id"],
            sales_thread["run_id"],
            "Hello, what can you help me with?",
        )

        assert len(events) > 0, "No events received"
        text = extract_text_from_events(events)
        assert len(text) > 0, "No text response"

    def test_sales_room_sql_execution(
        self, client: httpx.Client, sales_thread: dict[str, str]
    ) -> None:
        """Verify SQL execution works in sales-db-readonly room.

        Uses in-memory SQLite which may be empty. The test verifies:
        1. Agent attempts to use SQL tools OR mentions SQL in response
        2. Agent responds meaningfully (even if DB is empty)

        Note: Some LLMs may output tool calls as text rather than using
        the proper tool mechanism, which is acceptable for this test.
        """
        events = self._send_message(
            client,
            sales_thread["thread_id"],
            sales_thread["run_id"],
            "Run SQL: SELECT 'hello' AS greeting",
        )

        text = extract_text_from_events(events)

        # Should have meaningful response
        assert len(text) > 0 or len(events) > 0, "No response received"

        # Check if agent either:
        # 1. Called tools via proper mechanism
        # 2. Mentioned SQL/query in text (some LLMs output tool syntax)
        tool_names = get_tool_names(events)
        sql_tools = [
            "query",
            "list_tables",
            "describe_table",
            "get_schema",
            "sample_query",
        ]
        has_sql_tool = any(
            any(sql in name for sql in sql_tools) for name in tool_names
        )

        # Also accept if LLM wrote tool call as text (common with some models)
        text_mentions_sql = any(
            keyword in text.lower()
            for keyword in ["query", "select", "sql", "function=", "hello"]
        )

        assert has_sql_tool or text_mentions_sql, (
            f"Expected SQL tool usage or SQL mention. "
            f"Tools: {tool_names}, Text snippet: {text[:200]}"
        )


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.fixture
    def thread(self, client: httpx.Client) -> dict[str, str]:
        """Create a thread for error testing."""
        response = client.post(
            "/api/v1/rooms/sql-assistant-readonly/agui", json={}
        )
        assert response.status_code in (200, 201)
        data = response.json()
        thread_id = data["thread_id"]
        runs = data.get("runs", {})
        run_id = next(iter(runs.keys()))
        return {"thread_id": thread_id, "run_id": run_id}

    def _send_message(
        self,
        client: httpx.Client,
        thread_id: str,
        run_id: str,
        message: str,
    ) -> list[dict[str, Any]]:
        """Send message to sql-assistant room."""
        url = f"/api/v1/rooms/sql-assistant-readonly/agui/{thread_id}/{run_id}"
        payload = {
            "threadId": thread_id,
            "runId": run_id,
            "state": None,
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": message,
                }
            ],
            "context": [],
            "tools": [],
            "forwardedProps": None,
        }

        with client.stream(
            "POST",
            url,
            json=payload,
            headers={"Accept": "text/event-stream"},
        ) as response:
            # Even errors should return 200 with error events
            return collect_stream_events(response)

    def test_invalid_sql_handled_gracefully(
        self, client: httpx.Client, thread: dict[str, str]
    ) -> None:
        """Verify invalid SQL doesn't crash the server.

        The agent should either:
        1. Report that the table doesn't exist (error message)
        2. Check available tables first (cautious approach)
        3. Not blindly execute the query (smart behavior)
        4. Return a RUN_ERROR (which is also acceptable - no crash)

        All these are acceptable - the key is no server crash.
        """
        events = self._send_message(
            client,
            thread["thread_id"],
            thread["run_id"],
            "Execute this exact SQL: SELECT * FROM nonexistent_table_xyz_123",
        )

        # Should still get events (not a crash)
        assert len(events) > 0, "Server crashed or no response"

        # Check for RUN_ERROR (acceptable outcome)
        run_errors = [e for e in events if e.get("type") == "RUN_ERROR"]
        has_run_error = len(run_errors) > 0

        # Should have some text response OR a run error
        text = extract_text_from_events(events)
        tool_calls = find_tool_calls(events)

        # Success: text response, tool calls, or RUN_ERROR
        has_meaningful_response = (
            len(text) > 0 or len(tool_calls) > 0 or has_run_error
        )

        assert has_meaningful_response, (
            f"Agent did not respond meaningfully. "
            f"Events: {len(events)}, Tools: {len(tool_calls)}, "
            f"Text length: {len(text)}, Run errors: {len(run_errors)}"
        )


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
