"""Tests for aode.aode.etcd.client — EtcdClient wrapper over etcd3."""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# TestEtcdClientPutGet
# ---------------------------------------------------------------------------

class TestEtcdClientPutGet:
    """Verify put/get roundtrip through the etcd3 backend."""

    @patch("aode.aode.etcd.client.etcd3")
    def test_put_get_roundtrip(self, mock_etcd3):
        """put then get must return the stored value decoded from bytes."""
        from aode.aode.etcd.client import EtcdClient

        mock_client = MagicMock()
        mock_client.get.return_value = (b"edge-node-1", MagicMock())

        client = EtcdClient(endpoints=["localhost:2379"], key_prefix="/aode/")
        client._client = mock_client

        client.put("placement/OpA", "edge-node-1")
        result = client.get("placement/OpA")

        assert result == "edge-node-1"
        mock_client.put.assert_called_once()

    @patch("aode.aode.etcd.client.etcd3")
    def test_get_returns_none_for_missing_key(self, mock_etcd3):
        """get must return None when the key does not exist in etcd."""
        from aode.aode.etcd.client import EtcdClient

        mock_client = MagicMock()
        mock_client.get.return_value = (None, None)

        client = EtcdClient(endpoints=["localhost:2379"], key_prefix="/aode/")
        client._client = mock_client

        result = client.get("nonexistent-key")

        assert result is None

    @patch("aode.aode.etcd.client.etcd3")
    def test_put_uses_full_prefix_key(self, mock_etcd3):
        """put must prepend the configured key_prefix to the user-supplied key."""
        from aode.aode.etcd.client import EtcdClient

        mock_client = MagicMock()

        client = EtcdClient(endpoints=["localhost:2379"], key_prefix="/aode/")
        client._client = mock_client

        client.put("placement/OpA", "cloud")

        call_args = mock_client.put.call_args
        full_key = call_args[0][0] if call_args[0] else call_args[1].get("key", "")
        assert "/aode/" in str(full_key)
        assert "placement/OpA" in str(full_key)


# ---------------------------------------------------------------------------
# TestEtcdClientGetDict
# ---------------------------------------------------------------------------

class TestEtcdClientGetDict:
    """Verify get_dict returns prefix-filtered key-value pairs."""

    @patch("aode.aode.etcd.client.etcd3")
    def test_get_dict_returns_suffix_keys(self, mock_etcd3):
        """get_dict must strip the base prefix and return suffix -> value mapping."""
        from aode.aode.etcd.client import EtcdClient

        mock_client = MagicMock()

        meta_a = MagicMock()
        meta_a.key = b"/aode/placement/OpA"
        meta_b = MagicMock()
        meta_b.key = b"/aode/placement/OpB"

        mock_client.get_prefix.return_value = [
            (b"edge-node-1", meta_a),
            (b"cloud", meta_b),
        ]

        client = EtcdClient(endpoints=["localhost:2379"], key_prefix="/aode/")
        client._client = mock_client

        result = client.get_dict("placement/")

        assert isinstance(result, dict)
        assert len(result) == 2

    @patch("aode.aode.etcd.client.etcd3")
    def test_get_dict_empty_result_returns_empty_dict(self, mock_etcd3):
        """get_dict with no matching keys must return an empty dict."""
        from aode.aode.etcd.client import EtcdClient

        mock_client = MagicMock()
        mock_client.get_prefix.return_value = []

        client = EtcdClient(endpoints=["localhost:2379"], key_prefix="/aode/")
        client._client = mock_client

        result = client.get_dict("nonexistent/")

        assert result == {}

    @patch("aode.aode.etcd.client.etcd3")
    def test_get_dict_calls_get_prefix_with_full_prefix(self, mock_etcd3):
        """get_dict must call get_prefix with the full composed prefix path."""
        from aode.aode.etcd.client import EtcdClient

        mock_client = MagicMock()
        mock_client.get_prefix.return_value = []

        client = EtcdClient(endpoints=["localhost:2379"], key_prefix="/aode/")
        client._client = mock_client

        client.get_dict("placement/")

        call_args = mock_client.get_prefix.call_args
        prefix_arg = call_args[0][0] if call_args[0] else ""
        assert "/aode/" in str(prefix_arg)
        assert "placement/" in str(prefix_arg)


# ---------------------------------------------------------------------------
# TestEtcdClientDelete
# ---------------------------------------------------------------------------

class TestEtcdClientDelete:
    """Verify delete removes a key from the store."""

    @patch("aode.aode.etcd.client.etcd3")
    def test_delete_calls_client_delete_with_full_key(self, mock_etcd3):
        """delete must invoke the underlying client.delete with the full prefixed key."""
        from aode.aode.etcd.client import EtcdClient

        mock_client = MagicMock()

        client = EtcdClient(endpoints=["localhost:2379"], key_prefix="/aode/")
        client._client = mock_client

        client.delete("placement/OpA")

        mock_client.delete.assert_called_once()
        call_args = mock_client.delete.call_args
        full_key = call_args[0][0] if call_args[0] else ""
        assert "placement/OpA" in str(full_key)

    @patch("aode.aode.etcd.client.etcd3")
    def test_get_returns_none_after_delete(self, mock_etcd3):
        """After deleting a key, get must return None."""
        from aode.aode.etcd.client import EtcdClient

        mock_client = MagicMock()
        mock_client.get.return_value = (None, None)

        client = EtcdClient(endpoints=["localhost:2379"], key_prefix="/aode/")
        client._client = mock_client

        client.delete("placement/OpA")
        result = client.get("placement/OpA")

        assert result is None


# ---------------------------------------------------------------------------
# TestEtcdClientPrefix
# ---------------------------------------------------------------------------

class TestEtcdClientPrefix:
    """Verify key_prefix is applied consistently across all operations."""

    @patch("aode.aode.etcd.client.etcd3")
    def test_put_uses_configured_prefix(self, mock_etcd3):
        """put must compose the key as '{prefix}{key}'."""
        from aode.aode.etcd.client import EtcdClient

        mock_client = MagicMock()

        client = EtcdClient(endpoints=["localhost:2379"], key_prefix="/custom/ns/")
        client._client = mock_client

        client.put("mykey", "myvalue")

        call_args = mock_client.put.call_args
        full_key = str(call_args[0][0]) if call_args[0] else ""
        assert full_key.startswith("/custom/ns")
        assert "mykey" in full_key

    @patch("aode.aode.etcd.client.etcd3")
    def test_get_uses_configured_prefix(self, mock_etcd3):
        """get must compose the key as '{prefix}{key}'."""
        from aode.aode.etcd.client import EtcdClient

        mock_client = MagicMock()
        mock_client.get.return_value = (b"val", MagicMock())

        client = EtcdClient(endpoints=["localhost:2379"], key_prefix="/custom/ns/")
        client._client = mock_client

        client.get("mykey")

        call_args = mock_client.get.call_args
        full_key = str(call_args[0][0]) if call_args[0] else ""
        assert full_key.startswith("/custom/ns")
        assert "mykey" in full_key
