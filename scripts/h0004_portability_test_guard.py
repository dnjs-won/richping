"""Regression plugin: fail closed on real H0004 outcomes in this P0 action."""
from contextlib import ExitStack
from unittest.mock import patch
import pytest


@pytest.fixture(autouse=True)
def deny_real_h0004_outcomes():
    from richping.research_v2.strategy import h0004_directional_evaluator as e
    def guard(original):
        def wrapped(self,*args,**kwargs):
            if not self.binding.synthetic:
                raise AssertionError('P0 regression forbids real H0004 outcomes')
            return original(self,*args,**kwargs)
        return wrapped
    with ExitStack() as stack:
        for name in ('label','aggregate','readiness'):
            stack.enter_context(patch.object(e.DirectionalEvaluator,name,guard(getattr(e.DirectionalEvaluator,name))))
        yield
