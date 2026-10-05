"""Explicit artificial H0004 input; never opens a repository price dataset."""
from richping.core import digest,timestamp
from richping.research_v2.contracts import payload
from richping.research_v2.sessions import NY
from richping.research_v2.strategy.h0004_experiment import scheduled_window,calendar_contract
from richping.research_v2.strategy.h0004_directional_evaluator import (
    Anchor,Binding,Scope,SlotMetadata,DatasetMetadata,DirectionalEvaluator,close_identity,semantics)


def fixture(times=('2026-05-06T10:00:00-04:00',),returns=(.10,),scope=Scope.DISCOVERY_EXPLORATORY,
            as_of='2026-08-13T20:00:00-04:00',start='2026-05-05',end='2026-08-13'):
    dataset = 'SYNTHETIC:H0004-contract-fixture'
    values,anchors = {},[]
    for i,(time,result) in enumerate(zip(times,returns,strict=True)):
        at = timestamp(time)
        path = (at,*scheduled_window(at)[0])
        for slot in path: values.setdefault(slot,100.0)
        values[at] = 100.0
        values[path[-1]] = 100.0*(1+result)
        anchors.append(Anchor(f'synthetic_event_{i}',f'synthetic_episode_{i}',at.isoformat(),
            at.astimezone(NY).date().isoformat(),dataset,digest(['synthetic_snapshot',i]),close_identity(dataset,at,100.0)))
    anchors = tuple(anchors)
    binding = Binding(scope,dataset,digest(['synthetic_vintage']),digest(payload(anchors)),digest(payload(anchors)),
        digest(['synthetic_admission']),calendar_hash=digest(calendar_contract()),semantics_hash=digest(semantics()),synthetic=True)
    slots = tuple(SlotMetadata(at.isoformat(),at.isoformat(),close_identity(dataset,at,value))
                  for at,value in sorted(values.items()) if start<=at.astimezone(NY).date().isoformat()<=end)
    metadata = DatasetMetadata(dataset,binding.dataset_hash,binding.admission_hash,start,end,slots)
    evaluator = DirectionalEvaluator(anchors,binding,metadata,as_of)
    def reader(at,identity):
        return values[at]
    return evaluator,reader
