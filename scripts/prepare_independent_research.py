"""Prepare the next independent hypothesis intake without inventing strategy meaning."""
from argparse import ArgumentParser
from copy import deepcopy
from pathlib import Path
import re
import yaml

from richping.core import digest
from scripts.h0001_alpaca_admission import encode
from scripts.h0001_long_history_audit import write_new

STAGES = ['HYPOTHESIS_GENERATION_SELECTION', 'CAUSAL_DISCOVERY', 'PREREGISTRATION',
          'FUTURE_CONFIRMATION', 'FAIL_PRESERVE_OR_PROMOTE', 'NEXT_INDEPENDENT_HYPOTHESIS']


def prepare(root=Path('.')):
    entries = []
    for path in sorted((root/'research/hypotheses').glob('H*-r*.yaml')):
        match = re.fullmatch(r'H(\d{4})-r(\d{2})\.yaml', path.name)
        if not match: raise ValueError('Unrecognized hypothesis identity')
        body = yaml.safe_load(path.read_text(encoding='utf-8'))
        if body['hypothesis_id'] != 'H'+match[1] or body['revision'] != int(match[2]):
            raise ValueError('Hypothesis file/identity mismatch')
        entries.append({'id':body['hypothesis_id'], 'revision':body['revision'], 'path':path.relative_to(root).as_posix(),
                        'status':body['status'], 'content_hash':digest(body)})
    next_number = max([int(e['id'][1:]) for e in entries], default=0)+1
    if next_number > 9999: raise ValueError('Hypothesis identity exhausted')
    return {'schema':'independent_research_intake_v1', 'status':'READY_FOR_OWNER_STRATEGY_MEANING',
        'next_hypothesis_id':f'H{next_number:04d}', 'next_revision':1,
        'next_action':'INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION',
        'next_action_status':'USER_DECISION_REQUIRED', 'stages':STAGES,
        'registered_hypotheses':entries,
        'independence_requirement':'Different testable thesis; changing H0001 thresholds/window/provider is not a new independent hypothesis.',
        'selection_basis':['User market observation or explicitly selected independent thesis',
            'Causal observable feature/data feasibility', 'One bounded preregistered primary comparison'],
        'prior_trials_preserved':True, 'candidate_outcome_access':False,
        'future_confirmation_dependency':False,
        'execution_authority':'Intake only; no experiment, production write, risk reset or promotion.',
        'unknowns':['Independent thesis/observation not yet selected; preserve as unknown rather than inventing one.']}


def capture_observation(root, observation, thesis, created_at):
    if not observation.strip() or not thesis.strip(): raise ValueError('Explicit observation and thesis required')
    from richping.core import timestamp
    clock = timestamp(created_at).isoformat()
    prepared = prepare(root)
    body = deepcopy(yaml.safe_load((root/'research/templates/hypothesis.yaml').read_text(encoding='utf-8')))
    body.update(hypothesis_id=prepared['next_hypothesis_id'], revision=1, status='DRAFT',
                created_at=clock, updated_at=clock, title='Independent hypothesis intake', thesis=thesis.strip(),
                observations=[observation.strip()], supersedes=None)
    body['source'].update(type='chat', discussion_date=clock[:10], reference=None, issue=None)
    body['unknowns'] = ['Rules, causal input scope, label/metric, null, costs, evidence floor and confirmation contract require specification.']
    body['rules'] = {k:['UNKNOWN_NOT_SELECTED'] for k in body['rules']}
    body['required_data'] = ['UNKNOWN_NOT_SELECTED']
    for key in ('null_hypothesis','primary_metric','decision_rule','cost_assumption','sample_unit','multiple_testing_family'):
        body['test'][key] = 'UNKNOWN_NOT_SELECTED'
    body['test']['leakage_risks'] = ['Prior discovery exposures must be recorded; no confirmation reuse.']
    path = root/'research/hypotheses'/(prepared['next_hypothesis_id']+'-r01.yaml')
    write_new(path, yaml.safe_dump(body, allow_unicode=True, sort_keys=False).encode('utf-8'))
    return path


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    write_new(args.output, encode(prepare()))


if __name__ == '__main__': main()
