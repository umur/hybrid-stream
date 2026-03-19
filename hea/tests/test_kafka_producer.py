"""Tests for hea.hea.kafka.producer — BridgeProducer with mocked aiokafka."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import msgpack


@pytest.fixture
def mock_aiokafka_producer():
    mock_prod = AsyncMock()
    mock_prod.start = AsyncMock()
    mock_prod.stop = AsyncMock()
    mock_prod.send_and_wait = AsyncMock()
    return mock_prod


class TestBridgeProducerSend:

    @pytest.mark.asyncio
    async def test_send_serializes_with_msgpack(self, mock_aiokafka_producer):
        with patch("hea.hea.kafka.producer.AIOKafkaProducer", return_value=mock_aiokafka_producer):
            from hea.hea.kafka.producer import BridgeProducer
            bp = BridgeProducer(bootstrap_servers="localhost:9092")
            await bp.start()

            record = {"key": "value", "count": 42}
            await bp.send("test-topic", record)

            mock_aiokafka_producer.send_and_wait.assert_called_once()
            call_args = mock_aiokafka_producer.send_and_wait.call_args
            assert call_args[0][0] == "test-topic"
            # Verify the payload is valid msgpack
            payload = call_args[0][1]
            unpacked = msgpack.unpackb(payload, raw=False)
            assert unpacked == record

    @pytest.mark.asyncio
    async def test_send_calls_aiokafka_send_and_wait(self, mock_aiokafka_producer):
        with patch("hea.hea.kafka.producer.AIOKafkaProducer", return_value=mock_aiokafka_producer):
            from hea.hea.kafka.producer import BridgeProducer
            bp = BridgeProducer(bootstrap_servers="localhost:9092")
            await bp.start()
            await bp.send("my-topic", {"x": 1})

            assert mock_aiokafka_producer.send_and_wait.call_count == 1


class TestBridgeProducerSendRaw:

    @pytest.mark.asyncio
    async def test_send_raw_passes_bytes_unchanged(self, mock_aiokafka_producer):
        with patch("hea.hea.kafka.producer.AIOKafkaProducer", return_value=mock_aiokafka_producer):
            from hea.hea.kafka.producer import BridgeProducer
            bp = BridgeProducer(bootstrap_servers="localhost:9092")
            await bp.start()

            raw_payload = b"\x00\x01\x02\x03"
            await bp.send_raw("raw-topic", raw_payload)

            mock_aiokafka_producer.send_and_wait.assert_called_once_with("raw-topic", raw_payload)


class TestBridgeProducerLifecycle:

    @pytest.mark.asyncio
    async def test_send_raises_if_not_started(self):
        from hea.hea.kafka.producer import BridgeProducer
        bp = BridgeProducer(bootstrap_servers="localhost:9092")
        with pytest.raises(RuntimeError, match="not started"):
            await bp.send("topic", {"k": "v"})

    @pytest.mark.asyncio
    async def test_send_raw_raises_if_not_started(self):
        from hea.hea.kafka.producer import BridgeProducer
        bp = BridgeProducer(bootstrap_servers="localhost:9092")
        with pytest.raises(RuntimeError, match="not started"):
            await bp.send_raw("topic", b"\x00")

    @pytest.mark.asyncio
    async def test_stop_calls_producer_stop(self, mock_aiokafka_producer):
        with patch("hea.hea.kafka.producer.AIOKafkaProducer", return_value=mock_aiokafka_producer):
            from hea.hea.kafka.producer import BridgeProducer
            bp = BridgeProducer(bootstrap_servers="localhost:9092")
            await bp.start()
            await bp.stop()
            mock_aiokafka_producer.stop.assert_called_once()
