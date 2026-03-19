"""Tests for hea.hea.execution.decorators — @cpu_bound, @io_bound, is_cpu_bound."""
import pytest
from typing import Any


class TestCpuBoundDecorator:

    def test_sets_cpu_bound_true(self):
        from hea.hea.execution.decorators import cpu_bound
        from hea.hea.execution.base_operator import BaseOperator

        @cpu_bound
        class MyOp(BaseOperator):
            operator_id = "cpu_op"
            operator_type = "CpuOp"

            async def process(self, record):
                return []

            def get_state(self):
                return {}

            def restore_state(self, state):
                pass

        assert MyOp._cpu_bound is True

    def test_decorated_class_still_instantiable(self):
        from hea.hea.execution.decorators import cpu_bound
        from hea.hea.execution.base_operator import BaseOperator

        @cpu_bound
        class MyOp(BaseOperator):
            operator_id = "cpu_op"
            operator_type = "CpuOp"

            async def process(self, record):
                return []

            def get_state(self):
                return {}

            def restore_state(self, state):
                pass

        op = MyOp()
        assert op.operator_id == "cpu_op"

    def test_decorated_class_preserves_methods(self):
        from hea.hea.execution.decorators import cpu_bound
        from hea.hea.execution.base_operator import BaseOperator

        @cpu_bound
        class MyOp(BaseOperator):
            operator_id = "cpu_op"
            operator_type = "CpuOp"

            async def process(self, record):
                return [{"doubled": record["val"] * 2}]

            def get_state(self):
                return {"x": 1}

            def restore_state(self, state):
                pass

        op = MyOp()
        assert op.get_state() == {"x": 1}
        assert op.get_slo_ms() is None


class TestIoBoundDecorator:

    def test_sets_cpu_bound_false(self):
        from hea.hea.execution.decorators import io_bound
        from hea.hea.execution.base_operator import BaseOperator

        @io_bound
        class MyOp(BaseOperator):
            operator_id = "io_op"
            operator_type = "IoOp"

            async def process(self, record):
                return []

            def get_state(self):
                return {}

            def restore_state(self, state):
                pass

        assert MyOp._cpu_bound is False

    def test_decorated_class_still_instantiable(self):
        from hea.hea.execution.decorators import io_bound
        from hea.hea.execution.base_operator import BaseOperator

        @io_bound
        class MyOp(BaseOperator):
            operator_id = "io_op"
            operator_type = "IoOp"

            async def process(self, record):
                return []

            def get_state(self):
                return {}

            def restore_state(self, state):
                pass

        op = MyOp()
        assert op.operator_id == "io_op"


class TestIsCpuBound:

    def test_cpu_bound_class_returns_true(self):
        from hea.hea.execution.decorators import cpu_bound, is_cpu_bound
        from hea.hea.execution.base_operator import BaseOperator

        @cpu_bound
        class CpuOp(BaseOperator):
            operator_id = "c"
            operator_type = "C"

            async def process(self, record):
                return []

            def get_state(self):
                return {}

            def restore_state(self, state):
                pass

        assert is_cpu_bound(CpuOp) is True

    def test_io_bound_class_returns_false(self):
        from hea.hea.execution.decorators import io_bound, is_cpu_bound
        from hea.hea.execution.base_operator import BaseOperator

        @io_bound
        class IoOp(BaseOperator):
            operator_id = "i"
            operator_type = "I"

            async def process(self, record):
                return []

            def get_state(self):
                return {}

            def restore_state(self, state):
                pass

        assert is_cpu_bound(IoOp) is False

    def test_undecorated_class_returns_false(self):
        from hea.hea.execution.decorators import is_cpu_bound
        from hea.hea.execution.base_operator import BaseOperator

        class PlainOp(BaseOperator):
            operator_id = "p"
            operator_type = "P"

            async def process(self, record):
                return []

            def get_state(self):
                return {}

            def restore_state(self, state):
                pass

        assert is_cpu_bound(PlainOp) is False
