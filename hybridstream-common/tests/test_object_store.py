import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from hybridstream.common.object_store import ObjectStore


def _make_store() -> ObjectStore:
    return ObjectStore(
        endpoint_url="http://localhost:9000",
        access_key="test_key",
        secret_key="test_secret",
        bucket="test-bucket",
    )


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client context manager."""
    mock_client = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_client, mock_cm


@pytest.mark.asyncio
async def test_upload_returns_byte_size(mock_s3_client):
    mock_client, mock_cm = mock_s3_client
    mock_client.put_object = AsyncMock()

    store = _make_store()
    with patch.object(store._session, "client", return_value=mock_cm):
        data = b"\x48\x53\x4d\x50\x00\x01test_payload_bytes"
        size = await store.upload("op1/1/snapshot.msgpack", data)

    assert size == len(data)
    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="op1/1/snapshot.msgpack",
        Body=data,
    )


@pytest.mark.asyncio
async def test_download_returns_bytes(mock_s3_client):
    mock_client, mock_cm = mock_s3_client
    expected_data = b"\x48\x53\x4d\x50\x00\x01snapshot_data"

    mock_body = AsyncMock()
    mock_body.read = AsyncMock(return_value=expected_data)
    mock_client.get_object = AsyncMock(return_value={"Body": mock_body})

    store = _make_store()
    with patch.object(store._session, "client", return_value=mock_cm):
        result = await store.download("op1/1/snapshot.msgpack")

    assert result == expected_data
    mock_client.get_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="op1/1/snapshot.msgpack",
    )


@pytest.mark.asyncio
async def test_upload_download_roundtrip(mock_s3_client):
    """Simulated roundtrip: upload then download returns same bytes."""
    mock_client, mock_cm = mock_s3_client
    stored = {}

    async def fake_put(Bucket, Key, Body):
        stored[Key] = Body

    async def fake_get(Bucket, Key):
        mock_body = AsyncMock()
        mock_body.read = AsyncMock(return_value=stored[Key])
        return {"Body": mock_body}

    mock_client.put_object = AsyncMock(side_effect=fake_put)
    mock_client.get_object = AsyncMock(side_effect=fake_get)

    store = _make_store()
    data = b"roundtrip_test_data_12345"
    key = "test_op/42/snapshot.msgpack"

    with patch.object(store._session, "client", return_value=mock_cm):
        size = await store.upload(key, data)
        result = await store.download(key)

    assert size == len(data)
    assert result == data


@pytest.mark.asyncio
async def test_exists_returns_true(mock_s3_client):
    mock_client, mock_cm = mock_s3_client
    mock_client.head_object = AsyncMock(return_value={})

    store = _make_store()
    with patch.object(store._session, "client", return_value=mock_cm):
        result = await store.exists("op1/1/snapshot.msgpack")

    assert result is True
    mock_client.head_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="op1/1/snapshot.msgpack",
    )


@pytest.mark.asyncio
async def test_exists_returns_false(mock_s3_client):
    mock_client, mock_cm = mock_s3_client

    # Simulate ClientError for missing key
    from botocore.exceptions import ClientError
    mock_client.head_object = AsyncMock(
        side_effect=ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadObject",
        )
    )
    # The ObjectStore.exists catches s3.exceptions.ClientError,
    # but with mocks we need to catch botocore's ClientError directly.
    # Patch the exists method to use botocore exception.
    mock_client.exceptions = MagicMock()
    mock_client.exceptions.ClientError = ClientError

    store = _make_store()
    with patch.object(store._session, "client", return_value=mock_cm):
        result = await store.exists("nonexistent/key")

    assert result is False
