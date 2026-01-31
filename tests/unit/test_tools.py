"""Tests for tools module."""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from soliplex_sql.config import SQLToolConfig
from soliplex_sql.tools import _adapter_cache
from soliplex_sql.tools import _get_adapter
from soliplex_sql.tools import _get_config_from_context
from soliplex_sql.tools import close_all


class TestGetConfigFromContext:
    """Tests for _get_config_from_context."""

    def test_returns_none_without_deps(self) -> None:
        """Should return None if ctx has no deps."""
        ctx = MagicMock(spec=[])  # No deps attribute
        assert _get_config_from_context(ctx) is None

    def test_returns_none_without_tool_configs(self) -> None:
        """Should return None if deps has no tool_configs."""
        ctx = MagicMock()
        ctx.deps = MagicMock(spec=[])  # No tool_configs
        assert _get_config_from_context(ctx) is None

    def test_returns_none_with_empty_tool_configs(self) -> None:
        """Should return None if tool_configs is empty."""
        ctx = MagicMock()
        ctx.deps.tool_configs = {}
        assert _get_config_from_context(ctx) is None

    def test_returns_config_with_sql_kind(self) -> None:
        """Should return config matching SQL kind."""
        config = SQLToolConfig(tool_name="soliplex_sql.tools.list_tables")
        ctx = MagicMock()
        # Use the kind 'sql' (now all SQL tools have kind='sql')
        ctx.deps.tool_configs = {"sql": config}

        result = _get_config_from_context(ctx)

        assert result is config


class TestGetAdapter:
    """Tests for _get_adapter."""

    def setup_method(self) -> None:
        """Clear adapter cache before each test."""
        _adapter_cache.clear()

    def teardown_method(self) -> None:
        """Clear adapter cache after each test."""
        _adapter_cache.clear()

    def test_creates_adapter_from_env_settings(self) -> None:
        """Should create adapter from environment when no config."""
        ctx = MagicMock()
        ctx.deps.tool_configs = {}

        with patch(
            "soliplex_sql.tools.SQLToolConfig.create_deps"
        ) as mock_create:
            mock_deps = MagicMock()
            mock_deps.database = MagicMock()
            mock_deps.read_only = True
            mock_deps.max_rows = 100
            mock_create.return_value = mock_deps

            adapter = _get_adapter(ctx)

            assert adapter is not None

    def test_caches_adapter(self) -> None:
        """Should cache and reuse adapter."""
        ctx = MagicMock()
        ctx.deps.tool_configs = {}

        with patch(
            "soliplex_sql.tools.SQLToolConfig.create_deps"
        ) as mock_create:
            mock_deps = MagicMock()
            mock_deps.database = MagicMock()
            mock_deps.read_only = True
            mock_deps.max_rows = 100
            mock_create.return_value = mock_deps

            adapter1 = _get_adapter(ctx)
            adapter2 = _get_adapter(ctx)

            # Should reuse cached adapter
            assert adapter1 is adapter2
            # create_deps called only once
            assert mock_create.call_count == 1

    def test_different_configs_different_adapters(self) -> None:
        """Should create different adapters for different configs."""
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

        with patch.object(SQLToolConfig, "create_deps") as mock_create:
            mock_deps = MagicMock()
            mock_deps.database = MagicMock()
            mock_deps.read_only = True
            mock_deps.max_rows = 100
            mock_create.return_value = mock_deps

            _get_adapter(ctx1)
            _get_adapter(ctx2)

            # Different database URLs = different adapters
            assert mock_create.call_count == 2


class TestCloseAll:
    """Tests for close_all."""

    def setup_method(self) -> None:
        """Clear adapter cache before each test."""
        _adapter_cache.clear()

    def teardown_method(self) -> None:
        """Clear adapter cache after each test."""
        _adapter_cache.clear()

    async def test_closes_all_cached_adapters(self) -> None:
        """Should close all adapters in cache."""
        mock_adapter1 = MagicMock()
        mock_adapter1.close = AsyncMock()
        mock_adapter2 = MagicMock()
        mock_adapter2.close = AsyncMock()

        _adapter_cache[1] = mock_adapter1
        _adapter_cache[2] = mock_adapter2

        await close_all()

        mock_adapter1.close.assert_called_once()
        mock_adapter2.close.assert_called_once()

    async def test_clears_cache(self) -> None:
        """Should clear the cache after closing."""
        mock_adapter = MagicMock()
        mock_adapter.close = AsyncMock()
        _adapter_cache[1] = mock_adapter

        await close_all()

        assert len(_adapter_cache) == 0

    async def test_handles_empty_cache(self) -> None:
        """Should handle empty cache gracefully."""
        await close_all()  # Should not raise
        assert len(_adapter_cache) == 0
