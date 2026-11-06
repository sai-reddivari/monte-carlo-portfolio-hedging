"""Compare saved experiment outputs with freshly reproduced numeric results."""
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def csv_comparison(original, reproduced):
    result = dict(table=str(original.relative_to(ROOT)),
        reproduction=str(reproduced.relative_to(ROOT, walk_up=True)), saved_sha256=digest(original),
        reproduced_sha256=digest(reproduced) if reproduced.is_file() else None,
        passed=False, numeric_cells=0, numeric_mismatches=0, text_mismatches=0,
        max_absolute_difference=0., max_finite_relative_difference=0., examples=[])
    result['byte_equal'] = result['saved_sha256'] == result['reproduced_sha256']
    if not reproduced.is_file():
        result['reason'] = 'Reproduction output missing'
        return result
    a = pd.read_csv(original, float_precision='round_trip')
    b = pd.read_csv(reproduced, float_precision='round_trip')
    if list(a.columns) != list(b.columns) or a.shape != b.shape:
        result['reason'] = f'Schema/shape differs: saved {a.shape}, new {b.shape}; saved columns {list(a.columns)}, new {list(b.columns)}'
        return result
    result['rows'], result['columns'] = a.shape
    for column in a.columns:
        left, right = a[column], b[column]
        numeric = pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right)
        if numeric:
            x, y = left.to_numpy(dtype=float), right.to_numpy(dtype=float)
            valid = np.isclose(x, y, rtol=1e-9, atol=0, equal_nan=True)
            result['numeric_cells'] += int((~np.isnan(x)).sum())
            result['numeric_mismatches'] += int((~valid).sum())
            finite = np.isfinite(x) & np.isfinite(y)
            absolute = np.abs(y[finite]-x[finite])
            if len(absolute):
                result['max_absolute_difference'] = max(result['max_absolute_difference'],float(absolute.max()))
            nonzero = finite & (x != 0)
            if nonzero.any():
                result['max_finite_relative_difference'] = max(result['max_finite_relative_difference'],float(np.max(np.abs((y[nonzero]-x[nonzero])/x[nonzero]))))
        else:
            valid = ((left == right) | (left.isna() & right.isna())).to_numpy()
            result['text_mismatches'] += int((~valid).sum())
        for row in np.flatnonzero(~valid)[:5]:
            if len(result['examples']) < 12:
                def value(v):
                    if pd.isna(v):
                        return None
                    return v.item() if isinstance(v,np.generic) else v
                result['examples'].append(dict(row=int(row),column=column,before=value(left.iloc[row]),after=value(right.iloc[row])))
    result['passed'] = result['numeric_mismatches'] == 0 and result['text_mismatches'] == 0
    return result


def contracts(folder):
    # Small result tables contain published summaries, interval endpoints,
    # diagnostics and window accounting. Large prediction/trace tables retain
    # exact byte hashes and are compared in full, rather than duplicated here.
    values = {}
    for path in sorted(folder.rglob('*.csv')):
        if path.stat().st_size > 1024*1024:
            continue
        frame = pd.read_csv(path, float_precision='round_trip')
        numeric = frame.select_dtypes(include='number')
        if numeric.empty:
            continue
        text = frame.select_dtypes(exclude='number').fillna('').astype(str)
        values[str(path.relative_to(folder))] = dict(
            saved_table_sha256=digest(path),
            row_identifiers=text.to_dict(orient='list'),
            numbers={name:[float(v) if np.isfinite(v) else None for v in numeric[name]] for name in numeric.columns},
            nonfinite_convention='null represents a saved nonfinite/missing numeric cell; original bytes are hashed')
    return values


def json_comparison(original, reproduced):
    import math
    result=dict(file=str(original.relative_to(ROOT)),reproduction=str(reproduced.relative_to(ROOT, walk_up=True)),
        byte_equal=reproduced.is_file() and digest(original)==digest(reproduced),numeric_cells=0,
        numeric_mismatches=[],observed_timing_differences=[],string_differences=[],structure_differences=[],boolean_differences=[])
    if not reproduced.is_file():
        result['structure_differences'].append('Reproduction output missing')
        result['passed']=False
        return result
    def compare(a,b,pointer=''):
        if isinstance(a,bool) or isinstance(b,bool):
            if a!=b:
                result['boolean_differences'].append(dict(pointer=pointer,before=a,after=b))
        elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
            if pointer=='/elapsed_seconds':
                if a!=b:
                    result['observed_timing_differences'].append(dict(pointer=pointer,before=a,after=b,
                        reason='Measured runtime is observational, not an economic/numerical result. Both measurements are retained; no equality tolerance is asserted.'))
                return
            result['numeric_cells']+=1
            if not math.isclose(a,b,rel_tol=1e-9,abs_tol=0) and not (math.isnan(a) and math.isnan(b)):
                result['numeric_mismatches'].append(dict(pointer=pointer,before=a,after=b))
        elif isinstance(a,dict) and isinstance(b,dict):
            if a.keys()!=b.keys():
                result['structure_differences'].append(dict(pointer=pointer,missing=sorted(a.keys()-b.keys()),added=sorted(b.keys()-a.keys())))
            for key in a.keys() & b.keys():
                compare(a[key],b[key],pointer+'/'+str(key))
        elif isinstance(a,list) and isinstance(b,list):
            if len(a)!=len(b):
                result['structure_differences'].append(dict(pointer=pointer,before_length=len(a),after_length=len(b)))
            for index,(left,right) in enumerate(zip(a,b)):
                compare(left,right,pointer+'/'+str(index))
        elif a!=b:
            result['string_differences'].append(dict(pointer=pointer,before=a,after=b))
    compare(json.loads(original.read_text()),json.loads(reproduced.read_text()))
    result['passed']=not(result['numeric_mismatches'] or result['structure_differences'] or result['boolean_differences'])
    return result
