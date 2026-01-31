"""Tests for tools module."""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from soliplex_sql.config import SQLToolConfig
from soliplex_sql.tools import _adapter_cache
from soliplex_sql.tools import _get_adapter
from soliplex_sql.tools import close_all


class TestGetAdapter:
    """Tests for _get_adapter."""

    def setup_method(self) -> None:
        """Clear adapter cache before each test."""
        _adapter_cache.clear()

    def teardown_method(self) -> None:
        """Clear adapter cache after each test."""
        _adapter_cache.clear()

    async def test_creates_adapter_from_config(self) -> None:
        """Should create adapter from config."""
        config = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///test.db",
            read_only=True,
            max_rows=100,
        )

        with patch.object(SQLToolConfig, "create_deps") as mock_create:
            mock_deps = MagicMock()
            mock_deps.database = MagicMock()
            mock_deps.read_only = True
            mock_deps.max_rows = 100
            mock_create.return_value = mock_deps

            adapter = await _get_adapter(config)

            assert adapter is not None

    async def test_caches_adapter(self) -> None:
        """Should cache and reuse adapter."""
        config = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="sqlite:///test.db",
            read_only=True,
            max_rows=100,
        )

        with patch.object(SQLToolConfig, "create_deps") as mock_create:
            mock_deps = MagicMock()
            mock_deps.database = MagicMock()
            mock_deps.read_only = True
            mock_deps.max_rows = 100
            mock_create.return_value = mock_deps

            adapter1 = await _get_adapter(config)
            adapter2 = await _get_adapter(config)

            # Should reuse cached adapter
            assert adapter1 is adapter2
            # create_deps called only once
            assert mock_create.call_count == 1

    async def test_different_configs_different_adapters(self) -> None:
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

        with patch.object(SQLToolConfig, "create_deps") as mock_create:
            mock_deps = MagicMock()
            mock_deps.database = MagicMock()
            mock_deps.read_only = True
            mock_deps.max_rows = 100
            mock_create.return_value = mock_deps

            await _get_adapter(config1)
            await _get_adapter(config2)

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

        _adapter_cache[("db1", True, 100)] = mock_adapter1
        _adapter_cache[("db2", True, 100)] = mock_adapter2

        await close_all()

        mock_adapter1.close.assert_called_once()
        mock_adapter2.close.assert_called_once()

    async def test_clears_cache(self) -> None:
        """Should clear the cache after closing."""
        mock_adapter = MagicMock()
        mock_adapter.close = AsyncMock()
        _adapter_cache[("db", True, 100)] = mock_adapter

        await close_all()

        assert len(_adapter_cache) == 0

    async def test_handles_empty_cache(self) -> None:
        """Should handle empty cache gracefully."""
        await close_all()  # Should not raise
        assert len(_adapter_cache) == 0
