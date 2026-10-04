"""Synthetic terminal gates only; never a real confirmation outcome source."""
from unittest.mock import Mock, patch

import pytest

from richping.research_v2.strategy import h0002_efficacy as e
from richping.research_v2.strategy.h0002_defense import PRIMARY, COMPARATOR


@pytest.mark.parametrize('price,volume,expected', [
    (([.01,.02],[.001,.002]), ([-.02,-.01],[-.002,-.001]), 'PASS'),
    (([-.02,-.01],[.001,.002]), ([.01,.02],[.001,.002]), 'REJECT'),
    (([0,.01],[.001,.002]), ([.01,.02],[.001,.002]), 'INCONCLUSIVE'),
    (([-.01,0],[.001,.002]), ([.01,.02],[.001,.002]), 'INCONCLUSIVE'),
])
def test_terminal_joint_rule_and_volume_cannot_rescue_primary(price, volume, expected):
    denominator = {f: {'events': 40, 'event_sessions': 20, 'occupied_blocks': 8} for f in (PRIMARY, COMPARATOR)}
    intervals = {f: {'status':'COMPLETE','intervals':list(ci)} for f,ci in ((PRIMARY,price),(COMPARATOR,volume))}
    loader = Mock(return_value='SYNTHETIC_AGGREGATES_ONLY')
    with patch.object(e, 'utcnow', return_value='2027-10-24T00:01:00Z'), patch.object(e, '_registered_bootstrap', return_value=intervals):
        result = e.terminal_inference(loader, identity_verified=True, coverage_complete=True, denominators=denominator)
    assert result['status'] == expected and not result['comparator_can_replace_primary']
    assert loader.call_count == 1


def test_empty_bootstrap_family_unresolved_not_negative_or_zero_effect():
    denominator = {f: {'events':40,'event_sessions':20,'occupied_blocks':8} for f in (PRIMARY,COMPARATOR)}
    intervals = {f: {'status':'UNRESOLVED','intervals':[None,None]} for f in (PRIMARY,COMPARATOR)}
    with patch.object(e, 'utcnow', return_value='2027-10-24T00:01:00Z'), patch.object(e, '_registered_bootstrap', return_value=intervals):
        result = e.terminal_inference(lambda:'SYNTHETIC_ONLY', identity_verified=True, coverage_complete=True, denominators=denominator)
    assert result['status'] == 'UNRESOLVED'
