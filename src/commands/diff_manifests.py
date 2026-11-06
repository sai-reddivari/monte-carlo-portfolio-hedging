"""Compare regenerated full-precision contracts with the immutable Phase 0 baseline."""
import argparse
import json
import math
from pathlib import Path


def compare(before,after,allow_subset=False):
    expected={e['name'].removesuffix('_accelerate_pinned'):e for e in before['experiments']
              if e['name'].endswith('_accelerate_pinned') and not e['name'].startswith('equity_overlays_freeze')}
    actual={e['name']:e for e in after['experiments']}
    errors=[];numbers=0
    if not allow_subset and set(expected)!=set(actual):
        errors.append(dict(reason='experiment set',missing=sorted(set(expected)-set(actual)),added=sorted(set(actual)-set(expected))))
    for name,entry in actual.items():
        if name not in expected:
            errors.append(dict(experiment=name,reason='not in frozen baseline'));continue
        old=expected[name]['numeric_contracts'];new=entry['numeric_contracts']
        if set(old)!=set(new):
            errors.append(dict(experiment=name,reason='contract table set changed'));continue
        for table,contract in old.items():
            current=new[table]
            if contract['row_identifiers']!=current['row_identifiers']:
                errors.append(dict(experiment=name,table=table,reason='row identity/order changed'))
            if contract['numbers'].keys()!=current['numbers'].keys():
                errors.append(dict(experiment=name,table=table,reason='numeric columns changed'));continue
            for column,values in contract['numbers'].items():
                other=current['numbers'][column]
                if len(values)!=len(other):
                    errors.append(dict(experiment=name,table=table,column=column,reason='length changed'));continue
                for row,(a,b) in enumerate(zip(values,other)):
                    numbers+=1
                    equal=(a is None and b is None) or (a is not None and b is not None and math.isclose(a,b,rel_tol=1e-9,abs_tol=0))
                    if not equal:
                        errors.append(dict(experiment=name,table=table,column=column,row=row,before=a,after=b))
    table_errors=[c for e in actual.values() for c in e['table_comparison'] if not c['passed']]
    errors.extend(table_errors)
    summary=dict(experiments=len(actual),full_precision_contract_values=numbers,
        csv_tables=sum(len(e['table_comparison']) for e in actual.values()),
        csv_numeric_cells=sum(c['numeric_cells'] for e in actual.values() for c in e['table_comparison']),
        relative_tolerance=1e-9,absolute_tolerance=0,mismatches=len(errors),passed=not errors)
    return summary,errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before',nargs='?',type=Path,default=Path('results/manifest_pre_refactor.json'))
    parser.add_argument('after',nargs='?',type=Path,default=Path('results/manifest_post_refactor.json'))
    parser.add_argument('--allow-subset',action='store_true')
    args=parser.parse_args()
    summary,errors=compare(json.loads(args.before.read_text()),json.loads(args.after.read_text()),args.allow_subset)
    print(json.dumps(summary,indent=2))
    if errors:print(json.dumps(errors[:20],indent=2))
    raise SystemExit(0 if summary['passed'] else 1)


if __name__=='__main__':main()
