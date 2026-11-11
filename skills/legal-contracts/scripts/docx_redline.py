#!/usr/bin/env python3
"""Conservative OOXML redlining. No network. Refuses unsupported target structures.

CLI: inspect INPUT; apply INPUT PLAN.json OUTPUT_DIR; verify ORIGINAL TRACKED CLEAN.
Python >=3.10, lxml. See references/files.md for supported scope.
"""
import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _engine_env import reexec, refuse_inside_engine  # noqa: E402

try:
    from lxml import etree as E
except ImportError as exc:  # why: plain python3 without the engine's packages → re-run inside .venv
    if __name__ == '__main__':
        reexec(__file__, exc.name or 'lxml')
    raise


class RedlineError(ValueError):
    """The document or the change plan is outside what this helper can edit safely."""


W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
XMLSPACE = '{http://www.w3.org/XML/1998/namespace}space'
REV = {'ins', 'del', 'moveFrom', 'moveTo', 'moveFromRangeStart', 'moveFromRangeEnd',
       'moveToRangeStart', 'moveToRangeEnd', 'cellIns', 'cellDel', 'cellMerge', 'numberingChange'}

def q(n): return '{' + W + '}' + n
def parse(data): return E.fromstring(data, E.XMLParser(resolve_entities=False, no_network=True))
def dump(root): return E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_package(path):
    with ZipFile(path) as z:
        infos = z.infolist()
        if len({i.filename for i in infos}) != len(infos): raise RedlineError('Duplicate ZIP entries')
        if sum(i.file_size for i in infos) > 100_000_000: raise RedlineError('Package exceeds 100 MB limit')
        data = {i.filename: z.read(i) for i in infos}
    if 'word/document.xml' not in data: raise RedlineError('Not a supported DOCX')
    return infos, data

def write_package(path, infos, data):
    with ZipFile(path, 'x') as z:
        for info in infos: z.writestr(info, data[info.filename])

def word_roots(data):
    return {n: parse(b) for n, b in data.items() if n.startswith('word/') and n.endswith('.xml')}

def revisions(root):
    return [e for e in root.iter() if isinstance(e.tag, str) and e.tag.startswith('{' + W + '}')
            and (E.QName(e).localname in REV or E.QName(e).localname.endswith('PrChange'))]

def preflight(data):
    if any(n.startswith('_xmlsignatures/') or n.endswith('vbaProject.bin') for n in data):
        raise RedlineError('Signed or macro-enabled package: use a suitable editor on a copy')
    for n, root in word_roots(data).items():
        if revisions(root): raise RedlineError('Existing revisions in ' + n + '; preserve/reconcile baseline first')
        if root.find('.//w:documentProtection', NS) is not None:
            raise RedlineError('Protected document: no automatic removal of protection')

def text(p): return ''.join(p.xpath('.//w:t/text()', namespaces=NS))

HIDDEN = {q('txbxContent'), '{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent',
          '{urn:schemas-microsoft-com:vml}textbox'}

def simple(p):
    # why: a paragraph in a text box or an AlternateContent fallback may be a copy Word never shows.
    if any(a.tag in HIDDEN for a in p.iterancestors()): return False
    if any(c.tag not in {q('pPr'), q('r')} for c in p): return False
    return all(all(c.tag in {q('rPr'), q('t')} for c in r) for r in p.findall('w:r', NS))

def run_slice(run, start, end, deleted=False):
    s = ''.join(run.xpath('./w:t/text()', namespaces=NS))[start:end]
    if not s: return None
    out = E.Element(q('r'), attrib=dict(run.attrib))
    props = run.find('w:rPr', NS)
    if props is not None: out.append(copy.deepcopy(props))
    t = E.SubElement(out, q('delText' if deleted else 't')); t.set(XMLSPACE, 'preserve'); t.text = s
    return out

def take(runs, begin, end, deleted=False):
    out, pos = [], 0
    for run in runs:
        length = len(''.join(run.xpath('./w:t/text()', namespaces=NS)))
        lo, hi = max(begin-pos, 0), min(end-pos, length)
        if hi > lo: out.append(run_slice(run, lo, hi, deleted))
        pos += length
    return out

def check_plan(plan):
    """why: a malformed plan must give the typed error and exit 2, never a traceback mid-edit."""
    if not isinstance(plan, dict) or not isinstance(plan.get('changes'), list):
        raise RedlineError('Plan must be an object with a "changes" list')
    if not isinstance(plan.get('author', ''), str): raise RedlineError('Author must be a string')
    for i, ch in enumerate(plan['changes']):
        if not isinstance(ch, dict): raise RedlineError(f'changes[{i}] must be an object')
        if type(ch.get('paragraph')) is not int: raise RedlineError(f'changes[{i}].paragraph must be an integer')
        if not isinstance(ch.get('part', 'word/document.xml'), str): raise RedlineError(f'changes[{i}].part must be a string')
        for key in ('expected_paragraph', 'old', 'new'):
            if not isinstance(ch.get(key), str): raise RedlineError(f'changes[{i}].{key} must be a string')

def apply(input_path, plan, output_dir):
    infos, data = read_package(input_path); preflight(data)
    if 'word/settings.xml' not in data: raise RedlineError('Missing settings.xml; use a full editor')
    check_plan(plan)
    author = plan.get('author', '')
    if not author.strip(): raise RedlineError('Non-empty revision author required')
    changes = plan.get('changes', [])
    if not changes: raise RedlineError('No changes')
    roots = word_roots(data)
    max_id = max([int(v) for root in roots.values() for v in root.xpath('//@w:id', namespaces=NS)
                  if re.fullmatch(r'\d+', v)] + [0])
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    used, modified = set(), set()
    for ch in changes:
        part, index = ch.get('part', 'word/document.xml'), ch['paragraph']
        if not re.fullmatch(r'word/(document|header\d+|footer\d+|footnotes|endnotes)\.xml', part):
            raise RedlineError('Only supported document story parts can contain new tracked edits')
        if part not in roots or not isinstance(index, int) or index < 0: raise RedlineError('Invalid target')
        if (part,index) in used: raise RedlineError('Only one contiguous edit per paragraph per plan')
        used.add((part,index))
        ps = roots[part].findall('.//w:p', NS)
        if index >= len(ps): raise RedlineError('Paragraph index out of range')
        p = ps[index]
        if not simple(p): raise RedlineError('Complex target paragraph: fields, links, comments or objects; use editor')
        full, old, new = text(p), ch['old'], ch['new']
        if full != ch['expected_paragraph']: raise RedlineError('Baseline mismatch; re-read document')
        if not old or full.count(old) != 1: raise RedlineError('Old text must match exactly once within target')
        if old == new or any(c in new for c in '\r\n\t'): raise RedlineError('Use editor for structural edits or tabs')
        start, stop = full.index(old), full.index(old)+len(old)
        runs = p.findall('w:r', NS)
        prefix, removed, suffix = take(runs,0,start), take(runs,start,stop,True), take(runs,stop,len(full))
        for run in runs: p.remove(run)
        for run in prefix: p.append(run)
        max_id += 1
        deletion = E.SubElement(p,q('del'),{q('id'):str(max_id),q('author'):author,q('date'):stamp})
        deletion.extend(removed)
        if new:
            max_id += 1
            insertion = E.SubElement(p,q('ins'),{q('id'):str(max_id),q('author'):author,q('date'):stamp})
            run = copy.deepcopy(removed[0])
            for c in list(run):
                if c.tag != q('rPr'): run.remove(c)
            t = E.SubElement(run,q('t')); t.set(XMLSPACE,'preserve'); t.text=new
            insertion.append(run)
        for run in suffix: p.append(run)
        modified.add(part)
    settings=roots['word/settings.xml']
    if settings.find('w:trackRevisions',NS) is None:
        track=E.Element(q('trackRevisions'))
        successors={'doNotTrackMoves','doNotTrackFormatting','documentProtection','autoFormatOverride',
          'styleLockTheme','styleLockQFSet','defaultTabStop','autoHyphenation','consecutiveHyphenLimit',
          'hyphenationZone','doNotHyphenateCaps','showEnvelope','summaryLength','clickAndTypeStyle',
          'defaultTableStyle','evenAndOddHeaders','bookFoldRevPrinting','bookFoldPrinting',
          'drawingGridHorizontalSpacing','compat','rsids','mathPr','themeFontLang','clrSchemeMapping'}
        before=next((i for i,e in enumerate(settings) if E.QName(e).localname in successors),len(settings))
        settings.insert(before,track)
    else:
        settings.find('w:trackRevisions',NS).attrib.pop(q('val'),None)
    modified.add('word/settings.xml')
    tracked=dict(data)
    for n in modified: tracked[n]=dump(roots[n])
    clean=project(tracked,True)
    dest=refuse_inside_engine(output_dir,RedlineError)
    if dest.exists(): raise RedlineError('Output directory must be new; no overwrite')
    dest.parent.mkdir(parents=True,exist_ok=True)
    # why: unverified files must never sit in output/ looking like a deliverable; publish the folder only
    # after verification passes.
    work=Path(tempfile.mkdtemp(prefix='.redline-',dir=dest.parent))
    try:
        write_package(work/'tracked.docx',infos,tracked); write_package(work/'clean.docx',infos,clean)
        result=verify(input_path,work/'tracked.docx',work/'clean.docx')
    except Exception:
        shutil.rmtree(work,ignore_errors=True); raise
    result.update({'source_sha256':sha(input_path),'author':author,'created_at':stamp,'changes':changes})
    (work/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    work.rename(dest)
    return result

def project(data, accept):
    out=dict(data)
    for n,root in word_roots(data).items():
        revs=revisions(root)
        if any(E.QName(e).localname not in {'ins','del'} or e.getparent().tag != q('p')
               or any(c.tag != q('r') for c in e) for e in revs):
            raise RedlineError('Unsupported revision type; no silent acceptance')
        dirty=bool(revs)
        for e in revs:
            parent=e.getparent(); idx=parent.index(e)
            keep=(e.tag==q('ins'))==accept
            if keep:
                for run in list(e):
                    for t in run.iter(q('delText')): t.tag=q('t')
                    parent.insert(idx,run); idx+=1
            parent.remove(e)
        if n=='word/settings.xml':
            for e in root.findall('w:trackRevisions',NS): root.remove(e); dirty=True
        if dirty: out[n]=dump(root)
    return out

def canonical(data):
    root=parse(data)
    for p in root.findall('.//w:p',NS):
        if not simple(p): continue
        rebuilt=[]
        for child in p:
            if child.tag==q('pPr'): rebuilt.append(copy.deepcopy(child)); continue
            val=''.join(child.xpath('./w:t/text()',namespaces=NS))
            if not val: continue
            run=run_slice(child,0,len(val))
            props=run.find('w:rPr',NS)
            signature=(dict(run.attrib), E.tostring(props,method='c14n') if props is not None else None)
            if rebuilt and rebuilt[-1].tag==q('r'):
                prev=rebuilt[-1]; pp=prev.find('w:rPr',NS)
                psig=(dict(prev.attrib),E.tostring(pp,method='c14n') if pp is not None else None)
                if signature==psig: prev.find('w:t',NS).text+=val; continue
            rebuilt.append(run)
        p[:]=rebuilt
    return E.tostring(root,method='c14n')

def same_packages(a,b):
    if set(a)!=set(b): raise RedlineError('Package parts changed')
    for n in a:
        if a[n]==b[n]: continue
        if not n.startswith('word/') or not n.endswith('.xml') or canonical(a[n])!=canonical(b[n]):
            raise RedlineError('Package mismatch: '+n)

def verify(original,tracked,clean):
    _,a=read_package(original); _,b=read_package(tracked); _,c=read_package(clean)
    preflight(a)
    revs=[e for root in word_roots(b).values() for e in revisions(root)]
    if not revs: raise RedlineError('No real revisions')
    ids=[e.get(q('id')) for e in revs]
    if len(ids)!=len(set(ids)) or any(x is None or not x.isdigit() for x in ids): raise RedlineError('Bad IDs')
    for e in revs:
        if not e.get(q('author')) or not e.get(q('date')): raise RedlineError('Missing revision metadata')
        if e.tag==q('del') and e.find('.//w:t',NS) is not None: raise RedlineError('Deletion must use delText')
    if any(revisions(root) for root in word_roots(c).values()): raise RedlineError('Clean has revisions')
    if parse(b['word/settings.xml']).find('w:trackRevisions',NS) is None: raise RedlineError('Tracking missing')
    same_packages(project(b,True),c)
    same_packages(project(b,False),project(a,False))
    changed={n for n in a if a[n]!=b.get(n)}
    if set(a)!=set(b) or any(not n.startswith('word/') or not n.endswith('.xml') for n in changed):
        raise RedlineError('Unexpected package changes')
    return {'status':'passed','accept_equals_clean':True,'reject_equals_original':True,
            'revisions':len(revs),'changed_parts':sorted(changed),
            'scope':'OOXML structural checks; not Word UI or legal validation'}

def inspect(path):
    _,data=read_package(path)
    return {'sha256':sha(path),'parts':list(data),'paragraphs':[
        {'part':n,'paragraph':i,'text':text(p),'simple_target':simple(p)}
        for n,r in word_roots(data).items() for i,p in enumerate(r.findall('.//w:p',NS))],
        'existing_revisions':sum(len(revisions(r)) for r in word_roots(data).values())}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); sub=ap.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('inspect'); p.add_argument('input')
    p=sub.add_parser('apply'); p.add_argument('input'); p.add_argument('plan'); p.add_argument('output_dir')
    p=sub.add_parser('verify'); p.add_argument('original'); p.add_argument('tracked'); p.add_argument('clean')
    a=ap.parse_args(argv)
    try:
        if a.mode=='inspect': result=inspect(a.input)
        elif a.mode=='apply': result=apply(a.input,json.loads(Path(a.plan).read_text(encoding='utf-8')),a.output_dir)
        else: result=verify(a.original,a.tracked,a.clean)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,KeyError,IndexError,OSError,E.XMLSyntaxError) as e:
        print(json.dumps({'error':str(e)},ensure_ascii=False),file=sys.stderr); return 2
    return 0

if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # why: a Windows pipe defaults to the ANSI code page (no ș, ț, Cyrillic)
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8")
    sys.exit(main())
