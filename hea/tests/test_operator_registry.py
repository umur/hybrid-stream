"""Tests for hea.hea.operator_registry — register, get, dynamic loading."""
import pytest
import types
from typing import Any


def _make_concrete_operator(op_type: str):
    """Helper to create a concrete BaseOperator subclass for testing."""
    from hea.hea.execution.base_operator import BaseOperator

    class TestOp(BaseOperator):
        operator_id = f"test_{op_type}"
        operator_type = op_type

        async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
            return []

        def get_state(self) -> dict[str, Any]:
            return {}

        def restore_state(self, state: dict[str, Any]) -> None:
            pass

    TestOp.__name__ = f"TestOp_{op_type}"
    TestOp.__qualname__ = f"TestOp_{op_type}"
    return TestOp


class TestRegisterGet:

    def setup_method(self):
        """Clear registry before each test."""
        from hea.hea import operator_registry
        operator_registry._registry.clear()

    def test_register_and_get_roundtrip(self):
        from hea.hea import operator_registry
        cls = _make_concrete_operator("FilterOp")
        operator_registry.register("FilterOp", cls)
        assert operator_registry.get("FilterOp") is cls

    def test_get_raises_key_error_on_unknown(self):
        from hea.hea import operator_registry
        with pytest.raises(KeyError, match="not registered"):
            operator_registry.get("NonExistentOp")

    def test_duplicate_registration_overwrites(self):
        from hea.hea import operator_registry
        cls1 = _make_concrete_operator("DupOp")
        cls2 = _make_concrete_operator("DupOp")
        operator_registry.register("DupOp", cls1)
        operator_registry.register("DupOp", cls2)
        assert operator_registry.get("DupOp") is cls2

    def test_multiple_types_coexist(self):
        from hea.hea import operator_registry
        cls_a = _make_concrete_operator("TypeA")
        cls_b = _make_concrete_operator("TypeB")
        operator_registry.register("TypeA", cls_a)
        operator_registry.register("TypeB", cls_b)
        assert operator_registry.get("TypeA") is cls_a
        assert operator_registry.get("TypeB") is cls_b


class TestRegisterAllFromWorkload:

    def setup_method(self):
        from hea.hea import operator_registry
        operator_registry._registry.clear()

    def test_loads_classes_dynamically(self):
        """Create a synthetic module with a BaseOperator subclass and register from it."""
        from hea.hea.execution.base_operator import BaseOperator
        from hea.hea import operator_registry
        import sys

        # Create a fake workload module
        mod = types.ModuleType("fake_workload")

        class FakeOp(BaseOperator):
            operator_id = "fake"
            operator_type = "FakeOperator"

            async def process(self, record):
                return []

            def get_state(self):
                return {}

            def restore_state(self, state):
                pass

        mod.FakeOp = FakeOp
        sys.modules["fake_workload"] = mod

        try:
            operator_registry.register_all_from_workload("fake_workload")
            assert operator_registry.get("FakeOperator") is FakeOp
        finally:
            del sys.modules["fake_workload"]

    def test_skips_base_operator_itself(self):
        """BaseOperator in the module should not be registered."""
        from hea.hea.execution.base_operator import BaseOperator
        from hea.hea import operator_registry
        import sys

        mod = types.ModuleType("fake_workload2")
        mod.BaseOperator = BaseOperator  # should be skipped
        sys.modules["fake_workload2"] = mod

        try:
            operator_registry.register_all_from_workload("fake_workload2")
            assert len(operator_registry._registry) == 0
        finally:
            del sys.modules["fake_workload2"]
