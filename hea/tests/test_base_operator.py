"""Tests for hea.hea.execution.base_operator — BaseOperator ABC."""
import pytest
from typing import Any


class TestBaseOperatorABC:
    """BaseOperator is abstract and cannot be instantiated directly."""

    def test_cannot_instantiate_directly(self):
        from hea.hea.execution.base_operator import BaseOperator
        with pytest.raises(TypeError):
            BaseOperator()

    def test_subclass_must_implement_process(self):
        from hea.hea.execution.base_operator import BaseOperator

        class IncompleteOp(BaseOperator):
            operator_id = "inc"
            operator_type = "Incomplete"

            def get_state(self) -> dict[str, Any]:
                return {}

            def restore_state(self, state: dict[str, Any]) -> None:
                pass

        with pytest.raises(TypeError):
            IncompleteOp()

    def test_subclass_must_implement_get_state(self):
        from hea.hea.execution.base_operator import BaseOperator

        class IncompleteOp(BaseOperator):
            operator_id = "inc"
            operator_type = "Incomplete"

            async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
                return []

            def restore_state(self, state: dict[str, Any]) -> None:
                pass

        with pytest.raises(TypeError):
            IncompleteOp()

    def test_subclass_must_implement_restore_state(self):
        from hea.hea.execution.base_operator import BaseOperator

        class IncompleteOp(BaseOperator):
            operator_id = "inc"
            operator_type = "Incomplete"

            async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
                return []

            def get_state(self) -> dict[str, Any]:
                return {}

        with pytest.raises(TypeError):
            IncompleteOp()


class TestBaseOperatorDefaults:
    """Default method return values on a concrete subclass."""

    @pytest.fixture
    def concrete_op(self):
        from hea.hea.execution.base_operator import BaseOperator

        class ConcreteOp(BaseOperator):
            operator_id = "test_op"
            operator_type = "TestOp"

            async def process(self, record: dict[str, Any]) -> list[dict[str, Any]]:
                return [record]

            def get_state(self) -> dict[str, Any]:
                return {"count": 0}

            def restore_state(self, state: dict[str, Any]) -> None:
                pass

        return ConcreteOp()

    def test_get_slo_ms_returns_none_by_default(self, concrete_op):
        assert concrete_op.get_slo_ms() is None

    def test_get_lambda_class_returns_standard_by_default(self, concrete_op):
        assert concrete_op.get_lambda_class() == "standard"

    def test_on_start_is_callable(self, concrete_op):
        concrete_op.on_start()  # should not raise

    def test_on_stop_is_callable(self, concrete_op):
        concrete_op.on_stop()  # should not raise

    def test_on_start_returns_none(self, concrete_op):
        assert concrete_op.on_start() is None

    def test_on_stop_returns_none(self, concrete_op):
        assert concrete_op.on_stop() is None


class TestBaseOperatorOverrides:
    """Subclasses can override get_slo_ms and get_lambda_class."""

    def test_custom_slo_ms(self):
        from hea.hea.execution.base_operator import BaseOperator

        class CriticalOp(BaseOperator):
            operator_id = "crit"
            operator_type = "Critical"

            async def process(self, record):
                return []

            def get_state(self):
                return {}

            def restore_state(self, state):
                pass

            def get_slo_ms(self):
                return 50.0

            def get_lambda_class(self):
                return "critical"

        op = CriticalOp()
        assert op.get_slo_ms() == 50.0
        assert op.get_lambda_class() == "critical"
