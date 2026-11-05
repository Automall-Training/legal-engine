#!/usr/bin/env python3
"""Limited Markdown clause/field review and explicit Decimal manifest reconciliation."""
import argparse, json, re, sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _engine_env import write_report  # noqa: E402


class StructureInputError(ValueError):
    """The commercial manifest or a Markdown file cannot be checked."""


def money(value):
    if not isinstance(value, str):
        raise StructureInputError('Amounts must be decimal strings')
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0:
        raise StructureInputError('Amounts must be finite and nonnegative')
    return amount

def reconcile(data):
    issues=[]
    total=money(data['total'])
    for key in ('components','installments'):
        if key in data and sum((money(v) for v in data[key]), Decimal(0)) != total:
            issues.append(key+': sum differs from total')
    for i,d in enumerate(data.get('deliveries',[])):
        values=[d[k] for k in ('total','periods','per_period_cap')]
        if any(type(v) is not int or v < 0 for v in values):
            raise StructureInputError('Delivery counts must be nonnegative integers')
        if d['total'] > d['periods']*d['per_period_cap']:
            issues.append(f'deliveries[{i}]: total exceeds scheduling capacity')
    return issues

def inspect(text):
    issues=[]; clauses=set(); article=None; expected=1
    for i,line in enumerate(text.splitlines(),1):
        heading=re.match(r'^## (\d+)[ .]',line)
        if heading: article=int(heading[1]); expected=1
        # why: Romanian contracts usually write '1.1.' (trailing dot); '1.1' alone was the only form matched
        match=re.match(r'^(?:[-*]\s+)?(?:\*\*)?(\d+)\.(\d+)\.?(?:\*\*)?\s',line)
        if match:
            key=(int(match[1]),int(match[2]))
            if key in clauses: issues.append({'line':i,'rule':'duplicate_clause','value':match[0].strip()})
            if article is not None and key != (article,expected):
                issues.append({'line':i,'rule':'clause_sequence','expected':f'{article}.{expected}'})
            clauses.add(key); expected=key[1]+1
        if not line.startswith(('#','|','<!--')) and len(line.split()) > 120:
            issues.append({'line':i,'rule':'dense_paragraph','words':len(line.split()),'review':'Manual review; length alone is not an error'})
        if not line.startswith('|') and len(re.findall(r'\[[^\]]*\]',line)) >= 5:
            issues.append({'line':i,'rule':'packed_fields','review':'Consider one field per table row'})
    return issues

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths',nargs='*',type=Path);parser.add_argument('--commercial',type=Path)
    parser.add_argument('--report',type=Path);a=parser.parse_args(argv)
    try:
        if not a.paths and not a.commercial: raise StructureInputError('Supply Markdown paths or commercial JSON')
        findings={str(p):inspect(p.read_text(encoding='utf-8')) for p in a.paths}
        calculations=reconcile(json.loads(a.commercial.read_text(encoding='utf-8'))) if a.commercial else []
        out={'status':'needs_review' if any(findings.values()) or calculations else 'no_candidates', 'files':findings,'calculations':calculations,'scope':'Limited structural candidates only; manual legal, semantic, cross-reference and rendered review required'}
        encoded=json.dumps(out,ensure_ascii=False,indent=2)+'\n'
        if a.report:write_report(a.report,encoded,[*a.paths,a.commercial],StructureInputError)
        else:print(encoded,end='')
        return int(out['status']=='needs_review')
    except (ValueError,KeyError,TypeError,OSError,InvalidOperation) as e:
        print(json.dumps({'status':'input_error','error':str(e)}));return 2

if __name__=='__main__':raise SystemExit(main())
