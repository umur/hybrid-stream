"""Tests for hea.hea.state.store — OperatorStateStore with mocked RocksDB."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_rdict():
    """Mock rocksdict.Rdict so we don't need real RocksDB."""
    store_data = {}

    mock_db = MagicMock()
    mock_db.get = MagicMock(side_effect=lambda k: store_data.get(k))
    mock_db.__setitem__ = MagicMock(side_effect=lambda k, v: store_data.__setitem__(k, v))
    mock_db.__delitem__ = MagicMock(side_effect=lambda k: store_data.__delitem__(k))
    mock_db.items = MagicMock(side_effect=lambda: list(store_data.items()))
    mock_db.flush = MagicMock()
    mock_db.close = MagicMock()
    mock_db.create_checkpoint = MagicMock()

    mock_db._store_data = store_data  # expose for assertions

    return mock_db


@pytest.fixture
def state_store(mock_rdict):
    """Create an OperatorStateStore with mocked RocksDB."""
    with patch("hea.hea.state.store.Rdict", return_value=mock_rdict), \
         patch("hea.hea.state.store.Options"), \
         patch("hea.hea.state.store.WriteOptions"):
        from hea.hea.state.store import OperatorStateStore
        store = OperatorStateStore("test_op", "/tmp/fake")
        store._db = mock_rdict
        return store


class TestStateStorePutGet:

    def test_put_get_roundtrip(self, state_store, mock_rdict):
        state_store.put("key1", b"value1")
        mock_rdict._store_data[b"key1"] = b"value1"  # simulate actual storage
        result = state_store.get("key1")
        assert result == b"value1"

    def test_get_returns_none_for_missing_key(self, state_store):
        result = state_store.get("nonexistent")
        assert result is None


class TestStateStoreDelete:

    def test_delete_removes_key(self, state_store, mock_rdict):
        mock_rdict._store_data[b"mykey"] = b"myval"
        state_store.delete("mykey")
        mock_rdict.__delitem__.assert_called_once_with(b"mykey")


class TestStateStoreItems:

    def test_items_returns_all_pairs(self, state_store, mock_rdict):
        mock_rdict._store_data[b"k1"] = b"v1"
        mock_rdict._store_data[b"k2"] = b"v2"
        result = state_store.items()
        assert ("k1", b"v1") in result
        assert ("k2", b"v2") in result
        assert len(result) == 2

    def test_items_empty_store(self, state_store):
        result = state_store.items()
        assert result == []
