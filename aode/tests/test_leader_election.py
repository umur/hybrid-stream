"""Tests for aode.aode.etcd.client — LeaderElection acquire / release / stop."""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_etcd_client():
    """Return a mock EtcdClient with async leadership methods."""
    client = MagicMock()
    client.acquire_leader_lock = AsyncMock(return_value=True)
    client.release_leader_lock = AsyncMock()
    client.maintain_leadership = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# TestLeaderElectionInit
# ---------------------------------------------------------------------------


class TestLeaderElectionInit:
    """Verify default state before any election attempt."""

    def test_is_leader_false_before_election(self, mock_etcd_client):
        """is_leader() must return False on a freshly constructed instance."""
        from aode.aode.etcd.client import LeaderElection

        election = LeaderElection(mock_etcd_client, instance_id="aode-1")
        assert election.is_leader() is False

    def test_internal_flag_false_initially(self, mock_etcd_client):
        """The private _is_leader flag must default to False."""
        from aode.aode.etcd.client import LeaderElection

        election = LeaderElection(mock_etcd_client, instance_id="aode-1")
        assert election._is_leader is False


# ---------------------------------------------------------------------------
# TestLeaderElectionAcquire
# ---------------------------------------------------------------------------


class TestLeaderElectionAcquire:
    """Verify is_leader() reflects lock acquisition outcome."""

    @pytest.mark.asyncio
    async def test_is_leader_true_after_successful_acquire(self, mock_etcd_client):
        """is_leader() returns True when the lock is successfully acquired."""
        from aode.aode.etcd.client import LeaderElection

        mock_etcd_client.acquire_leader_lock.return_value = True

        election = LeaderElection(mock_etcd_client, instance_id="aode-1")
        await election.start_election()

        assert election.is_leader() is True

    @pytest.mark.asyncio
    async def test_is_leader_false_when_lock_held_by_another(self, mock_etcd_client):
        """is_leader() returns False when another instance holds the lock."""
        from aode.aode.etcd.client import LeaderElection

        mock_etcd_client.acquire_leader_lock.return_value = False

        election = LeaderElection(mock_etcd_client, instance_id="aode-2")
        await election.start_election()

        assert election.is_leader() is False

    @pytest.mark.asyncio
    async def test_start_election_returns_true_when_acquired(self, mock_etcd_client):
        """start_election() must return True when the lock is acquired."""
        from aode.aode.etcd.client import LeaderElection

        mock_etcd_client.acquire_leader_lock.return_value = True

        election = LeaderElection(mock_etcd_client, instance_id="aode-1")
        result = await election.start_election()

        assert result is True
        mock_etcd_client.acquire_leader_lock.assert_awaited_once_with(
            "aode", ttl_seconds=30
        )


# ---------------------------------------------------------------------------
# TestLeaderElectionStop
# ---------------------------------------------------------------------------


class TestLeaderElectionStop:
    """Verify stop_election releases the lock and cleans up."""

    @pytest.mark.asyncio
    async def test_stop_election_sets_is_leader_false(self, mock_etcd_client):
        """After stop_election, is_leader() must return False."""
        from aode.aode.etcd.client import LeaderElection

        mock_etcd_client.acquire_leader_lock.return_value = True

        election = LeaderElection(mock_etcd_client, instance_id="aode-1")
        await election.start_election()
        await election.stop_election()

        assert election.is_leader() is False

    @pytest.mark.asyncio
    async def test_stop_election_calls_release_leader_lock(self, mock_etcd_client):
        """stop_election must call release_leader_lock on the etcd client."""
        from aode.aode.etcd.client import LeaderElection

        mock_etcd_client.acquire_leader_lock.return_value = True

        election = LeaderElection(mock_etcd_client, instance_id="aode-1")
        await election.start_election()
        await election.stop_election()

        mock_etcd_client.release_leader_lock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_election_cancels_leadership_task(self, mock_etcd_client):
        """stop_election must cancel the background leadership maintenance task."""
        from aode.aode.etcd.client import LeaderElection

        # maintain_leadership should behave like a long-running coroutine
        never_ending = asyncio.Future()
        mock_etcd_client.maintain_leadership.return_value = never_ending
        mock_etcd_client.acquire_leader_lock.return_value = True

        election = LeaderElection(mock_etcd_client, instance_id="aode-1")
        await election.start_election()

        # The election should have created a leadership task
        task = election._leadership_task
        assert task is not None

        await election.stop_election()

        # After stop the task should be cancelled (or _is_leader should be False)
        assert election._is_leader is False
        assert task.cancelled() or task.done()
