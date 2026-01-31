"""Tests for adapter caching and connection reuse."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from soliplex_sql.config import SQLToolConfig
from soliplex_sql.tools import _adapter_cache
from soliplex_sql.tools import _get_adapter

if TYPE_CHECKING:
    pass


class TestAdapterCaching:
    """Tests for adapter caching behavior."""

    def test_same_config_returns_cached_adapter(self) -> None:
        """Same config should return the same cached adapter."""
        config = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///test1.db",
            read_only=True,
            max_rows=100,
        )

        ctx1 = MagicMock()
        ctx1.deps.tool_configs = {"query": config}

        ctx2 = MagicMock()
        ctx2.deps.tool_configs = {"query": config}

        adapter1 = _get_adapter(ctx1)
        adapter2 = _get_adapter(ctx2)

        assert adapter1 is adapter2

    def test_different_database_url_creates_new_adapter(self) -> None:
        """Different database URL should create new adapter."""
        config1 = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///db1.db",
            read_only=True,
            max_rows=100,
        )
        config2 = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///db2.db",
            read_only=True,
            max_rows=100,
        )

        ctx1 = MagicMock()
        ctx1.deps.tool_configs = {"query": config1}

        ctx2 = MagicMock()
        ctx2.deps.tool_configs = {"query": config2}

        adapter1 = _get_adapter(ctx1)
        adapter2 = _get_adapter(ctx2)

        assert adapter1 is not adapter2
        assert len(_adapter_cache) == 2

    def test_different_read_only_creates_new_adapter(self) -> None:
        """Different read_only setting should create new adapter."""
        config1 = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///same.db",
            read_only=True,
            max_rows=100,
        )
        config2 = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///same.db",
            read_only=False,
            max_rows=100,
        )

        ctx1 = MagicMock()
        ctx1.deps.tool_configs = {"query": config1}

        ctx2 = MagicMock()
        ctx2.deps.tool_configs = {"query": config2}

        adapter1 = _get_adapter(ctx1)
        adapter2 = _get_adapter(ctx2)

        assert adapter1 is not adapter2

    def test_different_max_rows_creates_new_adapter(self) -> None:
        """Different max_rows should create new adapter."""
        config1 = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///same.db",
            read_only=True,
            max_rows=100,
        )
        config2 = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///same.db",
            read_only=True,
            max_rows=500,
        )

        ctx1 = MagicMock()
        ctx1.deps.tool_configs = {"query": config1}

        ctx2 = MagicMock()
        ctx2.deps.tool_configs = {"query": config2}

        adapter1 = _get_adapter(ctx1)
        adapter2 = _get_adapter(ctx2)

        assert adapter1 is not adapter2

    def test_cache_key_uses_tuple_not_hash(self) -> None:
        """Cache should use tuple as key, not hash."""
        config = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///test.db",
            read_only=True,
            max_rows=100,
        )

        ctx = MagicMock()
        ctx.deps.tool_configs = {"query": config}

        _get_adapter(ctx)

        # Cache key should be a tuple
        cache_keys = list(_adapter_cache.keys())
        assert len(cache_keys) == 1
        assert isinstance(cache_keys[0], tuple)
        assert cache_keys[0] == ("sqlite:///test.db", True, 100)


class TestFallbackToEnvironment:
    """Tests for fallback to environment config."""

    def test_no_config_uses_env_settings(self) -> None:
        """Should use environment settings when no config in context."""
        ctx = MagicMock()
        ctx.deps.tool_configs = {}

        # Should not raise, uses env defaults
        adapter = _get_adapter(ctx)
        assert adapter is not None

    def test_no_deps_uses_env_settings(self) -> None:
        """Should use environment settings when no deps attribute."""
        ctx = MagicMock(spec=[])  # No deps attribute

        adapter = _get_adapter(ctx)
        assert adapter is not None


class TestConcurrentRoomSupport:
    """Tests for concurrent room database support."""

    def test_multiple_rooms_multiple_databases(self) -> None:
        """Should support multiple concurrent databases for rooms."""
        # Room A: Sales database
        sales_config = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///sales.db",
            read_only=True,
            max_rows=100,
        )

        # Room B: HR database
        hr_config = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///hr.db",
            read_only=True,
            max_rows=100,
        )

        # Room C: Finance database
        finance_config = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///finance.db",
            read_only=True,
            max_rows=100,
        )

        ctx_sales = MagicMock()
        ctx_sales.deps.tool_configs = {"query": sales_config}

        ctx_hr = MagicMock()
        ctx_hr.deps.tool_configs = {"query": hr_config}

        ctx_finance = MagicMock()
        ctx_finance.deps.tool_configs = {"query": finance_config}

        # Get adapters for each room
        adapter_sales = _get_adapter(ctx_sales)
        adapter_hr = _get_adapter(ctx_hr)
        adapter_finance = _get_adapter(ctx_finance)

        # Each room should have its own adapter
        assert adapter_sales is not adapter_hr
        assert adapter_hr is not adapter_finance
        assert adapter_sales is not adapter_finance

        # All should be cached
        assert len(_adapter_cache) == 3

        # Re-accessing should return cached adapters
        assert _get_adapter(ctx_sales) is adapter_sales
        assert _get_adapter(ctx_hr) is adapter_hr
        assert _get_adapter(ctx_finance) is adapter_finance
