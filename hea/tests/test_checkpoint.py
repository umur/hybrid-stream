"""Tests for hea.hea.state.checkpoint — PeriodicCheckpointer."""
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestPeriodicCheckpointer:

    def test_register_adds_store(self):
        from hea.hea.state.checkpoint import PeriodicCheckpointer
        cp = PeriodicCheckpointer(interval_s=30, checkpoint_base_dir="/tmp/cp")
        mock_store = MagicMock()
        cp.register("op1", mock_store)
        assert "op1" in cp._stores
        assert cp._stores["op1"] is mock_store

    def test_deregister_removes_store(self):
        from hea.hea.state.checkpoint import PeriodicCheckpointer
        cp = PeriodicCheckpointer(interval_s=30, checkpoint_base_dir="/tmp/cp")
        mock_store = MagicMock()
        cp.register("op1", mock_store)
        cp.deregister("op1")
        assert "op1" not in cp._stores

    def test_deregister_nonexistent_is_noop(self):
        from hea.hea.state.checkpoint import PeriodicCheckpointer
        cp = PeriodicCheckpointer(interval_s=30, checkpoint_base_dir="/tmp/cp")
        cp.deregister("nonexistent")  # should not raise

    def test_register_multiple_stores(self):
        from hea.hea.state.checkpoint import PeriodicCheckpointer
        cp = PeriodicCheckpointer(interval_s=30, checkpoint_base_dir="/tmp/cp")
        for i in range(5):
            cp.register(f"op{i}", MagicMock())
        assert len(cp._stores) == 5

    @pytest.mark.asyncio
    async def test_checkpoint_called_on_interval(self):
        from hea.hea.state.checkpoint import PeriodicCheckpointer
        cp = PeriodicCheckpointer(interval_s=0, checkpoint_base_dir="/tmp/cp")

        mock_store = MagicMock()
        mock_store.checkpoint = MagicMock(return_value="/tmp/cp/checkpoints/op1")
        cp.register("op1", mock_store)

        # Patch asyncio.sleep to avoid real delay and break after one iteration
        call_count = 0

        async def fake_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise asyncio.CancelledError()

        with patch("hea.hea.state.checkpoint.asyncio.sleep", side_effect=fake_sleep):
            with pytest.raises(asyncio.CancelledError):
                await cp._loop()

        mock_store.checkpoint.assert_called_once()

    @pytest.mark.asyncio
    async def test_checkpoint_exception_does_not_crash_loop(self):
        from hea.hea.state.checkpoint import PeriodicCheckpointer
        cp = PeriodicCheckpointer(interval_s=0, checkpoint_base_dir="/tmp/cp")

        mock_store = MagicMock()
        mock_store.checkpoint = MagicMock(side_effect=RuntimeError("disk full"))
        cp.register("op1", mock_store)

        call_count = 0

        async def fake_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                raise asyncio.CancelledError()

        with patch("hea.hea.state.checkpoint.asyncio.sleep", side_effect=fake_sleep):
            with pytest.raises(asyncio.CancelledError):
                await cp._loop()

        # Store.checkpoint was called despite the error
        assert mock_store.checkpoint.call_count >= 2

    def test_interval_stored(self):
        from hea.hea.state.checkpoint import PeriodicCheckpointer
        cp = PeriodicCheckpointer(interval_s=45, checkpoint_base_dir="/data")
        assert cp._interval == 45
