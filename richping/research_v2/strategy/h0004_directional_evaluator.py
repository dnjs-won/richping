"""H0004 exact-slot directional labels, separate from signal generation.

No loader, provider, database or automatic execution. Metadata readiness never
calls the close reader. Real evaluation requires an independently verified
pre-access permit; fixtures must use a distinct SYNTHETIC: dataset namespace.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
import math
from statistics import mean

from ...core import digest, timestamp
from ..contracts import payload
from ..sessions import NY
from .h0004_experiment import scheduled_window, calendar_contract, DEADLINE

VERSION = 'H0004_EXACT_SLOT_DIRECTIONAL_ADAPTER_V1'
PROTOCOL_HASH = '09e8202e4edd3a06c3b7907d7aafa70c93c05155d5f1d902c5d07798540d8d1f'
FREEZE_HASH = 'f4226caf0d6a0bd825347a06ee4be26307e7eda551ed560e9538cc38dd932de8'
STREAM_HASH = '8e64aecd6fa26261bf5735126f3615427427bbe5ae34b0d242b8d14dd513d14d'
DATASET_ID = 'soxx-alpaca-sip-15m-discovery-20260505-20260813-v1'
DATASET_HASH = '4b39f109e8cffce8a7e680e773b560b307e21dd5a92dcad6d06fcd47bb0aa8bd'
PRICE_CONTRACT = ('SOXX','15m','alpaca','sip','raw','USD/share','04:00-20:00 America/New_York',
                  'historical_bar_end_assumed_availability')


class Scope(str, Enum):
    DISCOVERY_EXPLORATORY = 'DISCOVERY_EXPLORATORY'
    CONFIRMATION_TERMINAL = 'CONFIRMATION_TERMINAL'


def semantics():
    return dict(version=VERSION,formula='SOXX_close(t+16)/SOXX_close(t)-1',primary_slots=16,
        path='Anchor plus exact scheduled t+1..t+16; no missing-slot compression or adjusted fallback',
        closure='Overnight/weekend/holiday consume no slot; unsupported nominal dates retained',
        weighting='Equal events within anchor session; equal occupied anchor sessions',
        completeness='All emitted candidates retained; any noncomplete row blocks full-cohort mean',
        action_unit='Any split/share-unit change/unknown or incompatible raw-unit segment => UNRESOLVED',
        cash_dividends='Disclosure only; raw price-only return, no total-return transform',
        scopes=[s.value for s in Scope],confirmation_deadline=DEADLINE,
        confirmation='Strictly after receipt deadline; real future admission/terminal seal also required',
        profitability='NOT_ESTIMATED',MFE_MAE='NONE',benchmarks='NONE',controls='NONE')


@dataclass(frozen=True, slots=True)
class Anchor:
    event_id: str
    episode_id: str
    at: str
    session: str
    dataset_id: str
    snapshot_hash: str
    close_identity: str


def close_identity(dataset_id, at, close):
    return digest([dataset_id,'SOXX',timestamp(at).isoformat(),close])


def anchors_from_frozen(events):
    """Only signal-time snapshots; does not map/query any real forward endpoint."""
    return tuple(Anchor(e['id'],e['episode_id'],e['at'],e['session'],e['snapshot']['bar']['dataset_id'],
        digest(e['snapshot']),close_identity(e['snapshot']['bar']['dataset_id'],e['at'],
                                            e['snapshot']['bar']['close'])) for e in events)


@dataclass(frozen=True, slots=True)
class Binding:
    scope: Scope
    dataset_id: str
    dataset_hash: str
    candidate_stream_hash: str
    anchor_metadata_hash: str
    admission_hash: str
    protocol_hash: str = PROTOCOL_HASH
    signal_freeze_hash: str = FREEZE_HASH
    calendar_hash: str = ''
    semantics_hash: str = ''
    synthetic: bool = False

    def validate(self):
        if (not isinstance(self.scope,Scope) or type(self.synthetic) is not bool
                or (self.protocol_hash,self.signal_freeze_hash)!=(PROTOCOL_HASH,FREEZE_HASH)
                or self.calendar_hash!=digest(calendar_contract()) or self.semantics_hash!=digest(semantics())
                or any(not isinstance(v,str) or not v for v in (self.dataset_id,self.dataset_hash,
                       self.candidate_stream_hash,self.anchor_metadata_hash,self.admission_hash))):
            raise ValueError('INVALID_FAIL_CLOSED: protocol/signal/calendar/semantics identity')
        if self.synthetic:
            if not self.dataset_id.startswith('SYNTHETIC:'):
                raise PermissionError('Synthetic arithmetic cannot use a real dataset identity')
        elif self.scope is Scope.DISCOVERY_EXPLORATORY:
            if (self.dataset_id,self.dataset_hash,self.candidate_stream_hash)!=(DATASET_ID,DATASET_HASH,STREAM_HASH):
                raise ValueError('INVALID_FAIL_CLOSED: discovery dataset/stream identity')
        else:
            raise PermissionError('Future confirmation requires separate interval admission and terminal seal')


@dataclass(frozen=True, slots=True)
class SlotMetadata:
    end_at: str
    known_at: str
    close_identity: str
    unit_segment: str = 'raw_unit_1'
    action: str = 'NONE_CONFIRMED'
    unit_certified: bool = True
    contract: tuple = PRICE_CONTRACT
    cash_dividend: bool = False


@dataclass(frozen=True, slots=True)
class DatasetMetadata:
    dataset_id: str
    dataset_hash: str
    admission_hash: str
    start_session: str
    end_session: str
    slots: tuple[SlotMetadata, ...]


class DirectionalEvaluator:
    def __init__(self, anchors, binding, metadata, as_of, permit=None):
        binding.validate()
        self.anchors = tuple(anchors)
        self.binding, self.metadata, self.as_of, self.permit = binding, metadata, timestamp(as_of), permit
        if (digest(payload(self.anchors))!=binding.anchor_metadata_hash
                or (metadata.dataset_id,metadata.dataset_hash,metadata.admission_hash)!=
                    (binding.dataset_id,binding.dataset_hash,binding.admission_hash)
                or not isinstance(metadata.slots,tuple)):
            raise ValueError('INVALID_FAIL_CLOSED: detached cohort/admission binding')
        if len({a.event_id for a in self.anchors})!=len(self.anchors) or len({a.episode_id for a in self.anchors})!=len(self.anchors):
            raise ValueError('INVALID_FAIL_CLOSED: duplicate candidate/episode')
        if not binding.synthetic and len(self.anchors)!=48:
            raise ValueError('INVALID_FAIL_CLOSED: full frozen48 denominator required')
        prior = None
        for a in self.anchors:
            at = timestamp(a.at)
            if (a.dataset_id!=binding.dataset_id or at.astimezone(NY).date().isoformat()!=a.session
                    or any(not v for v in (a.event_id,a.episode_id,a.snapshot_hash,a.close_identity))
                    or (prior is not None and at<=prior)):
                raise ValueError('INVALID_FAIL_CLOSED: anchor identity/clock/order')
            if binding.scope is Scope.DISCOVERY_EXPLORATORY:
                if not '2026-05-05'<=a.session<='2026-08-13':
                    raise PermissionError('Discovery cannot access confirmation/non-discovery anchor')
            elif not '2026-10-19'<=a.session<='2027-10-19':
                raise PermissionError('Confirmation cannot access discovery/nonconfirmation anchor')
            prior = at
        if binding.scope is Scope.DISCOVERY_EXPLORATORY:
            if not '2026-05-05'<=metadata.start_session<=metadata.end_session<='2026-08-13':
                raise PermissionError('Discovery source cannot extend sealed scope')
        else:
            if not '2026-10-19'<=metadata.start_session<=metadata.end_session<='2027-10-20':
                raise PermissionError('Confirmation label source outside registered interval')
        self.slots = {}
        for m in metadata.slots:
            key = timestamp(m.end_at)
            day = key.astimezone(NY).date().isoformat()
            if key in self.slots or not metadata.start_session<=day<=metadata.end_session:
                raise ValueError('INVALID_FAIL_CLOSED: duplicate/outside-scope metadata slot')
            self.slots[key] = m
        self.by_id = {a.event_id:a for a in self.anchors}
        self.audit = Counter(forward_price_queries=0,discovery_label_reads=0,confirmation_label_reads=0,
                             return_calculations=0,efficacy_aggregations=0,profitability_calculations=0)

    def _authorize_real(self):
        # An arbitrary callback/boolean cannot stand in for verified sealing.
        from scripts.h0004_preaccess import DiscoveryPermit
        if type(self.permit) is not DiscoveryPermit:
            raise PermissionError('Verified pre-access permit and separate execution action required')
        checked,anchors = self.permit.authorize()
        if checked!=self.binding or anchors!=self.anchors:
            raise ValueError('Sealed execution cohort changed')

    def readiness(self, event_id):
        """Identity/maturity/coverage metadata only; never exposes a future value."""
        if event_id not in self.by_id: raise PermissionError('Candidate absent from sealed cohort')
        a = self.by_id[event_id]
        base = dict(event_id=a.event_id,episode_id=a.episode_id,session=a.session,
                    anchor_at=a.at,horizon_slots=16,status='UNRESOLVED',reason=None)
        try: window,unsupported = scheduled_window(a.at)
        except ValueError:
            return dict(base,status='INVALID_FAIL_CLOSED',reason='unsupported_or_invalid_anchor_slot')
        path = (timestamp(a.at),*window)
        target = window[-1]
        base['target_at'] = target.isoformat()
        days = [t.astimezone(NY).date().isoformat() for t in path]
        if any(not self.metadata.start_session<=d<=self.metadata.end_session for d in days):
            return dict(base,reason='outside_sealed_scope')
        if self.binding.scope is Scope.CONFIRMATION_TERMINAL and self.as_of<=timestamp(DEADLINE):
            return dict(base,status='PENDING',reason='confirmation_terminal_deadline')
        if target>self.as_of:
            return dict(base,status='PENDING',reason='label_not_mature')
        if unsupported: return dict(base,reason='unsupported_nominal_session')
        if any(t not in self.slots for t in path):
            return dict(base,reason='missing_expected_supported_slot')
        rows = [self.slots[t] for t in path]
        if any(timestamp(m.known_at)>self.as_of for m in rows):
            return dict(base,status='PENDING',reason='slot_not_yet_available')
        if any(timestamp(m.known_at)!=t or tuple(m.contract)!=PRICE_CONTRACT or not m.close_identity
               for t,m in zip(path,rows)) or rows[0].close_identity!=a.close_identity:
            return dict(base,status='INVALID_FAIL_CLOSED',reason='clock_contract_or_anchor_identity')
        if (any(m.unit_certified is not True or m.action not in ('NONE_CONFIRMED','CASH_DIVIDEND') for m in rows)
                or len({m.unit_segment for m in rows})!=1 or not rows[0].unit_segment):
            return dict(base,reason='action_or_raw_unit_ambiguity')
        return dict(base,status='READY_TO_EVALUATE',reason='exact_admitted_scheduled_path')

    def label(self, event_id, reader):
        if not self.binding.synthetic:
            self._authorize_real()
        result = self.readiness(event_id)
        result['gross_return'] = None
        result['cash_dividend_disclosed'] = False
        if result['status']!='READY_TO_EVALUATE': return result
        at,target = timestamp(result['anchor_at']),timestamp(result['target_at'])
        path = (at,*scheduled_window(at)[0])
        result['cash_dividend_disclosed'] = any(self.slots[t].cash_dividend or self.slots[t].action=='CASH_DIVIDEND' for t in path)
        values = []
        for slot in (at,target):
            self.audit['forward_price_queries'] += int(slot!=at)
            self.audit['discovery_label_reads' if self.binding.scope is Scope.DISCOVERY_EXPLORATORY else 'confirmation_label_reads'] += 1
            value = reader(slot,self.slots[slot].close_identity)
            if type(value) not in (float,int) or not math.isfinite(value) or value<=0:
                return dict(result,status='INVALID_FAIL_CLOSED',reason='nonfinite_or_nonpositive_close')
            if close_identity(self.binding.dataset_id,slot,value)!=self.slots[slot].close_identity:
                return dict(result,status='INVALID_FAIL_CLOSED',reason='close_identity_mismatch')
            values.append(value)
        self.audit['return_calculations'] += 1
        value = values[1]/values[0]-1
        if not math.isfinite(value): return dict(result,status='INVALID_FAIL_CLOSED',reason='nonfinite_return')
        return dict(result,status='COMPLETE',reason='exact_t_plus_16',gross_return=value)

    def evaluate(self, reader):
        return tuple(self.label(a.event_id,reader) for a in self.anchors)

    def aggregate(self, rows):
        if self.binding.scope is Scope.CONFIRMATION_TERMINAL and self.as_of<=timestamp(DEADLINE):
            raise PermissionError('No preterminal confirmation outcome aggregation')
        if not self.binding.synthetic:
            self._authorize_real()
        rows = tuple(rows)
        if [r['event_id'] for r in rows]!=[a.event_id for a in self.anchors]:
            raise ValueError('Full cohort denominator/order cannot be changed')
        if any((r['episode_id'],r['session'],r['anchor_at'],r['horizon_slots'])!=
               (a.episode_id,a.session,a.at,16) for r,a in zip(rows,self.anchors)):
            raise ValueError('Row cohort identity changed')
        counts = Counter({k:0 for k in ('COMPLETE','PENDING','UNRESOLVED','INVALID_FAIL_CLOSED')})
        for r in rows:
            if r['status'] not in counts: raise ValueError('Unevaluated/unknown label state')
            counts[r['status']] += 1
            v = r['gross_return']
            if r['status']=='COMPLETE':
                if type(v) not in (int,float) or not math.isfinite(v): raise ValueError('Nonfinite complete label')
            elif v is not None: raise ValueError('Noncomplete label cannot expose value')
        self.audit['efficacy_aggregations'] += 1
        state = next((s for s in ('INVALID_FAIL_CLOSED','PENDING','UNRESOLVED') if counts[s]),
                     'COMPLETE' if rows else 'ZERO_SIGNAL')
        grouped = defaultdict(list)
        if state=='COMPLETE':
            for r in rows: grouped[r['session']].append(r['gross_return'])
        estimate = mean(mean(v) for v in grouped.values()) if grouped else None
        if estimate is not None and not math.isfinite(estimate): raise ValueError('Nonfinite full-cohort mean')
        return dict(status=state,total_emitted=len(rows),complete=counts['COMPLETE'],pending=counts['PENDING'],
                    unresolved=counts['UNRESOLVED'],invalid=counts['INVALID_FAIL_CLOSED'],
                    candidate_sessions=len({a.session for a in self.anchors}),
                    full_cohort_session_balanced_mean=estimate,profitability='NOT_ESTIMATED',
                    uncertainty=None,disposition='DESCRIPTIVE_ONLY_NO_PASS_REJECT')
