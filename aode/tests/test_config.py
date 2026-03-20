"""Tests for aode.aode.config — AODEConfig pydantic-settings validation.

All tests are TDD — the source module aode.aode.config does not exist yet.
Each test has a docstring. Env overrides use monkeypatch.setenv() and
instantiate AODEConfig inside the test body so the patched env is visible.
"""
import pytest


# ---------------------------------------------------------------------------
# TestAODEConfigDefaults — one test per field (24 tests)
# ---------------------------------------------------------------------------
class TestAODEConfigDefaults:
    """Verify every field returns its documented default value."""

    def test_instance_id_default(self, aode_config):
        """instance_id defaults to 'aode-1'."""
        assert aode_config.instance_id == "aode-1"

    def test_cluster_id_default(self, aode_config):
        """cluster_id defaults to 'default'."""
        assert aode_config.cluster_id == "default"

    def test_grpc_port_default(self, aode_config):
        """grpc_port defaults to 50052."""
        assert aode_config.grpc_port == 50052

    def test_etcd_endpoints_default(self, aode_config):
        """etcd_endpoints defaults to ['localhost:2379']."""
        assert aode_config.etcd_endpoints == ["localhost:2379"]

    def test_etcd_key_prefix_default(self, aode_config):
        """etcd_key_prefix defaults to '/aode/'."""
        assert aode_config.etcd_key_prefix == "/aode/"

    def test_leader_election_ttl_default(self, aode_config):
        """leader_election_ttl defaults to 30."""
        assert aode_config.leader_election_ttl == 30

    def test_telemetry_interval_s_default(self, aode_config):
        """telemetry_interval_s defaults to 5."""
        assert aode_config.telemetry_interval_s == 5

    def test_telemetry_timeout_s_default(self, aode_config):
        """telemetry_timeout_s defaults to 2."""
        assert aode_config.telemetry_timeout_s == 2

    def test_recalibration_interval_s_default(self, aode_config):
        """recalibration_interval_s defaults to 5."""
        assert aode_config.recalibration_interval_s == 5

    def test_recalibration_enabled_default(self, aode_config):
        """recalibration_enabled defaults to True."""
        assert aode_config.recalibration_enabled is True

    def test_kappa_default(self, aode_config):
        """kappa defaults to 2.0."""
        assert aode_config.kappa == 2.0

    def test_delta_h_default(self, aode_config):
        """delta_h defaults to 0.15."""
        assert aode_config.delta_h == 0.15

    def test_lookahead_horizon_s_default(self, aode_config):
        """lookahead_horizon_s defaults to 30."""
        assert aode_config.lookahead_horizon_s == 30

    def test_slo_penalty_factor_default(self, aode_config):
        """slo_penalty_factor defaults to 10."""
        assert aode_config.slo_penalty_factor == 10

    def test_default_weight_preset_default(self, aode_config):
        """default_weight_preset defaults to 'balanced'."""
        assert aode_config.default_weight_preset == "balanced"

    def test_hea_discovery_method_default(self, aode_config):
        """hea_discovery_method defaults to 'static'."""
        assert aode_config.hea_discovery_method == "static"

    def test_hea_endpoints_default(self, aode_config):
        """hea_endpoints defaults to four edge-node endpoints."""
        expected = [
            "edge-node-1:50051",
            "edge-node-2:50051",
            "edge-node-3:50051",
            "edge-node-4:50051",
        ]
        assert aode_config.hea_endpoints == expected

    def test_flink_connector_endpoint_default(self, aode_config):
        """flink_connector_endpoint defaults to 'localhost:50053'."""
        assert aode_config.flink_connector_endpoint == "localhost:50053"

    def test_migration_timeout_s_default(self, aode_config):
        """migration_timeout_s defaults to 300."""
        assert aode_config.migration_timeout_s == 300

    def test_drain_timeout_s_default(self, aode_config):
        """drain_timeout_s defaults to 60."""
        assert aode_config.drain_timeout_s == 60

    def test_minio_endpoint_default(self, aode_config):
        """minio_endpoint defaults to 'http://localhost:9000'."""
        assert aode_config.minio_endpoint == "http://localhost:9000"

    def test_minio_access_key_default(self, aode_config):
        """minio_access_key defaults to 'hybridstream'."""
        assert aode_config.minio_access_key == "hybridstream"

    def test_minio_secret_key_default(self, aode_config):
        """minio_secret_key defaults to 'hybridstream123'."""
        assert aode_config.minio_secret_key == "hybridstream123"

    def test_minio_bucket_default(self, aode_config):
        """minio_bucket defaults to 'hybridstream-snapshots'."""
        assert aode_config.minio_bucket == "hybridstream-snapshots"


# ---------------------------------------------------------------------------
# TestAODEConfigEnvOverride — 9 tests
# ---------------------------------------------------------------------------
class TestAODEConfigEnvOverride:
    """Verify that AODE_ prefixed environment variables override defaults."""

    def test_override_instance_id(self, monkeypatch):
        """AODE_INSTANCE_ID overrides instance_id."""
        monkeypatch.setenv("AODE_INSTANCE_ID", "my-aode")
        from aode.aode.config import AODEConfig

        cfg = AODEConfig()
        assert cfg.instance_id == "my-aode"

    def test_override_grpc_port(self, monkeypatch):
        """AODE_GRPC_PORT overrides grpc_port to an integer."""
        monkeypatch.setenv("AODE_GRPC_PORT", "9999")
        from aode.aode.config import AODEConfig

        cfg = AODEConfig()
        assert cfg.grpc_port == 9999

    def test_override_kappa(self, monkeypatch):
        """AODE_KAPPA overrides kappa to a float."""
        monkeypatch.setenv("AODE_KAPPA", "3.5")
        from aode.aode.config import AODEConfig

        cfg = AODEConfig()
        assert cfg.kappa == 3.5

    def test_override_delta_h(self, monkeypatch):
        """AODE_DELTA_H overrides delta_h to a float."""
        monkeypatch.setenv("AODE_DELTA_H", "0.25")
        from aode.aode.config import AODEConfig

        cfg = AODEConfig()
        assert cfg.delta_h == 0.25

    def test_override_recalibration_enabled_false(self, monkeypatch):
        """AODE_RECALIBRATION_ENABLED='false' sets recalibration_enabled to False."""
        monkeypatch.setenv("AODE_RECALIBRATION_ENABLED", "false")
        from aode.aode.config import AODEConfig

        cfg = AODEConfig()
        assert cfg.recalibration_enabled is False

    def test_override_recalibration_enabled_zero(self, monkeypatch):
        """AODE_RECALIBRATION_ENABLED='0' sets recalibration_enabled to False."""
        monkeypatch.setenv("AODE_RECALIBRATION_ENABLED", "0")
        from aode.aode.config import AODEConfig

        cfg = AODEConfig()
        assert cfg.recalibration_enabled is False

    def test_override_slo_penalty_factor(self, monkeypatch):
        """AODE_SLO_PENALTY overrides slo_penalty_factor to an integer."""
        monkeypatch.setenv("AODE_SLO_PENALTY", "50")
        from aode.aode.config import AODEConfig

        cfg = AODEConfig()
        assert cfg.slo_penalty_factor == 50

    def test_override_lookahead_horizon_s(self, monkeypatch):
        """AODE_LOOKAHEAD_HORIZON overrides lookahead_horizon_s to an integer."""
        monkeypatch.setenv("AODE_LOOKAHEAD_HORIZON", "120")
        from aode.aode.config import AODEConfig

        cfg = AODEConfig()
        assert cfg.lookahead_horizon_s == 120

    def test_override_default_weight_preset(self, monkeypatch):
        """AODE_DEFAULT_WEIGHTS overrides default_weight_preset."""
        monkeypatch.setenv("AODE_DEFAULT_WEIGHTS", "latency-first")
        from aode.aode.config import AODEConfig

        cfg = AODEConfig()
        assert cfg.default_weight_preset == "latency-first"


# ---------------------------------------------------------------------------
# TestAODEConfigScoringConstants — group validation (5 tests)
# ---------------------------------------------------------------------------
class TestAODEConfigScoringConstants:
    """Verify scoring-related constants carry the expected values as a group."""

    def test_kappa_scoring_constant(self, aode_config):
        """kappa is 2.0 in default config."""
        assert aode_config.kappa == 2.0

    def test_delta_h_scoring_constant(self, aode_config):
        """delta_h is 0.15 in default config."""
        assert aode_config.delta_h == 0.15

    def test_lookahead_horizon_scoring_constant(self, aode_config):
        """lookahead_horizon_s is 30 in default config."""
        assert aode_config.lookahead_horizon_s == 30

    def test_slo_penalty_factor_scoring_constant(self, aode_config):
        """slo_penalty_factor is 10 in default config."""
        assert aode_config.slo_penalty_factor == 10

    def test_all_scoring_constants_together(self, aode_config):
        """All scoring constants match their documented values simultaneously."""
        assert aode_config.kappa == 2.0
        assert aode_config.delta_h == 0.15
        assert aode_config.lookahead_horizon_s == 30
        assert aode_config.slo_penalty_factor == 10


# ---------------------------------------------------------------------------
# TestAODEConfigFieldTypes — type checking (4 tests)
# ---------------------------------------------------------------------------
class TestAODEConfigFieldTypes:
    """Verify Python types of config fields."""

    def test_kappa_is_float(self, aode_config):
        """kappa should be a float."""
        assert isinstance(aode_config.kappa, float)

    def test_grpc_port_is_int(self, aode_config):
        """grpc_port should be an int."""
        assert isinstance(aode_config.grpc_port, int)

    def test_recalibration_enabled_is_bool(self, aode_config):
        """recalibration_enabled should be a bool."""
        assert isinstance(aode_config.recalibration_enabled, bool)

    def test_etcd_endpoints_is_list(self, aode_config):
        """etcd_endpoints should be a list."""
        assert isinstance(aode_config.etcd_endpoints, list)
