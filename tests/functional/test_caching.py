"""Tests for adapter caching and connection reuse."""

from __future__ import annotations

from typing import TYPE_CHECKING

from soliplex_sql.config import SQLToolConfig
from soliplex_sql.tools import _adapter_cache
from soliplex_sql.tools import _get_adapter

if TYPE_CHECKING:
    pass


class TestAdapterCaching:
    """Tests for adapter caching behavior."""

    async def test_same_config_returns_cached_adapter(self) -> None:
        """Same config should return the same cached adapter."""
        config = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///test1.db",
            read_only=True,
            max_rows=100,
        )

        adapter1 = await _get_adapter(config)
        adapter2 = await _get_adapter(config)

        assert adapter1 is adapter2

    async def test_different_database_url_creates_new_adapter(self) -> None:
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

        adapter1 = await _get_adapter(config1)
        adapter2 = await _get_adapter(config2)

        assert adapter1 is not adapter2
        assert len(_adapter_cache) == 2

    async def test_different_read_only_creates_new_adapter(self) -> None:
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

        adapter1 = await _get_adapter(config1)
        adapter2 = await _get_adapter(config2)

        assert adapter1 is not adapter2

    async def test_different_max_rows_creates_new_adapter(self) -> None:
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

        adapter1 = await _get_adapter(config1)
        adapter2 = await _get_adapter(config2)

        assert adapter1 is not adapter2

    async def test_cache_key_uses_tuple_not_hash(self) -> None:
        """Cache should use tuple as key, not hash."""
        config = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///test.db",
            read_only=True,
            max_rows=100,
        )

        await _get_adapter(config)

        # Cache key should be a tuple
        cache_keys = list(_adapter_cache.keys())
        assert len(cache_keys) == 1
        assert isinstance(cache_keys[0], tuple)
        assert cache_keys[0] == ("sqlite:///test.db", True, 100)


class TestConcurrentRoomSupport:
    """Tests for concurrent room database support."""

    async def test_multiple_rooms_multiple_databases(self) -> None:
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

        # Get adapters for each room
        adapter_sales = await _get_adapter(sales_config)
        adapter_hr = await _get_adapter(hr_config)
        adapter_finance = await _get_adapter(finance_config)

        # Each room should have its own adapter
        assert adapter_sales is not adapter_hr
        assert adapter_hr is not adapter_finance
        assert adapter_sales is not adapter_finance

        # All should be cached
        assert len(_adapter_cache) == 3

        # Re-accessing should return cached adapters
        assert await _get_adapter(sales_config) is adapter_sales
        assert await _get_adapter(hr_config) is adapter_hr
        assert await _get_adapter(finance_config) is adapter_finance
