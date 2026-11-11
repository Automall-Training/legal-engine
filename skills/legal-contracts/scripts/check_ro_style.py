#!/usr/bin/env python3
"""Read-only Romanian voice review for MD/text and accepted DOCX text.

Finite lexical heuristics, not a grammar or legal validator. Never rewrites text.
Exit 1: unresolved candidates/coverage gaps; 2: invalid input or stale decisions.
"""
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _engine_env import write_report  # noqa: E402


class StyleInputError(ValueError):
    """An input file or the decisions file cannot be reviewed."""


W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS={'w':W}
DELETED={f'{{{W}}}del',f'{{{W}}}moveFrom'}
PART=re.compile(r'word/(?:document|header\d*|footer\d*|footnotes|endnotes)\.xml$')

def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.lower()) if unicodedata.category(c)!='Mn')

# Whole words: a suffix rule would incorrectly flag sistem, regim, legitim, minim.
PLURAL=set(fold('''afirmăm anonimizăm anulăm anunțăm aplicăm atașăm avem cerem colectăm
comunicăm confirmăm considerăm convenim credem decidem declarăm descriem dezvăluim dispunem
dorim eliminăm emitem efectuăm exercităm explicăm facturăm facem folosim furnizăm garantăm
gestionăm impunem informăm începem încheiem înregistrăm înțelegem luăm menținem modificăm
notificăm oferim organizăm păstrăm permitem plătim prelucrăm presupunem prezentăm primim
procesăm promitem protejăm publicăm punem putem rambursăm răspundem realizăm recunoaștem
refuzăm respectăm restituim retragem reținem revizuim rezervăm solicităm soluționăm stocăm
suntem ștergem transmitem tratăm trimitem utilizăm verificăm vindem asumăm obligăm angajăm
acceptăm acordăm analizăm autentificăm blocăm consimțim demonstrăm desemnăm distribuim
identificăm includem limităm primim raportăm suspendăm transferăm validăm''').split())
SINGULAR=set(fold('accept confirm consimt declar doresc exprim înțeleg solicit recunosc').split())
SECOND=set(fold('sunteți puteți aveți beneficiați trimiteți alegeți acceptați solicitați doriți apăsați retrageți contactați transmiteți ați primiți utilizați confirmați publicați').split())
PRONOUNS=set(fold('nostru noastră noastre noștri îmi mie mă meu mea mei mele').split())
WORDS=re.compile(r'\b[a-z]+\b')

def tokens(text,profile='formal'):
    norm=fold(text); result=[]
    for m in WORDS.finditer(norm):
        word=m.group();rule=None
        if word in PLURAL:rule='first_plural'
        elif word in SINGULAR or word in PRONOUNS:rule='first_person_or_declaration'
        elif profile=='formal' and word in SECOND:rule='direct_address'
        if rule:result.append({'rule':rule,'token':text[m.start():m.end()],'offset':m.start()})
    for m in re.finditer(r'\b(?:vom|am)\s+[a-z]+|\bam\s*\[|\bne\s+(?:puteti|comunica|contactati|rezervam|asumam)|\bni\s+se\b|\bnoi\s+(?:vom|am|suntem|putem)\b',norm):
        result.append({'rule':'first_person_phrase','token':text[m.start():m.end()],'offset':m.start()})
    return result

def blocks(path):
    """Return text blocks plus surfaces that still require visual/manual reading."""
    if path.suffix.lower() in {'.md','.txt'}:
        return [(f'line:{i}',line) for i,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1) if line.strip()],[]
    if path.suffix.lower()!='.docx':raise StyleInputError('Unsupported input: '+str(path))
    out=[];gaps=[]
    with ZipFile(path) as z:
        names=z.namelist()
        if 'word/document.xml' not in names:raise StyleInputError('Not a Word document: '+str(path))
        for part in sorted(n for n in names if PART.fullmatch(n)):
            root=ET.fromstring(z.read(part));parent={c:p for p in root.iter() for c in p}
            def deleted(node):
                while node is not None:
                    if node.tag in DELETED:return True
                    node=parent.get(node)
                return False
            def paragraph_text(p):
                fragments=[]
                def visit(n):
                    if n.tag in DELETED:return
                    if n is not p and n.tag==f'{{{W}}}p':return
                    if n.tag==f'{{{W}}}t':fragments.append(n.text or '')
                    elif n.tag==f'{{{W}}}tab':fragments.append('\t')
                    elif n.tag==f'{{{W}}}br':fragments.append('\n')
                    for c in n:visit(c)
                visit(p);return ''.join(fragments)
            for i,p in enumerate(root.iter(f'{{{W}}}p')):
                if deleted(p):continue
                t=paragraph_text(p)
                if t.strip():out.append((f'{part}:p:{i}',t))
            for tag in ['altChunk','object','pict','drawing']:
                active=[n for n in root.iter(f'{{{W}}}{tag}') if not deleted(n)]
                if active:gaps.append(f'{part}: {len(active)} {tag} object(s): check rendered/embedded text manually')
    return out,gaps

def analyze(paths,root=None,profile='formal',decisions=None):
    candidates=[];coverage=[];inventory=[]
    for p in sorted({Path(p).resolve() for p in paths}):
        name=str(p.relative_to(root)) if root and p.is_relative_to(root) else str(p)
        extracted,gaps=blocks(p)
        inventory.append({'file':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'blocks':len(extracted)})
        for locator,text in extracted:
            digest=hashlib.sha256(text.encode()).hexdigest()
            for token in tokens(text,profile):
                base=f'{name}\0{locator}\0{digest}\0{token["rule"]}\0{token["offset"]}'
                candidates.append({'id':hashlib.sha256(base.encode()).hexdigest(),'file':name,'locator':locator,'text_sha256':digest,'text':text,**token})
        coverage.extend({'file':name,'detail':g} for g in gaps)
    errors=[];allowed={}
    roles={'personal_declaration','interface_label','quoted_source','user_selected_voice','false_positive'}
    decisions=decisions or {'exceptions':[]}
    if not isinstance(decisions,dict) or not isinstance(decisions.get('exceptions'),list):raise StyleInputError('Decisions require exceptions array')
    byid={c['id']:c for c in candidates}
    for d in decisions['exceptions']:
        if not isinstance(d,dict):
            errors.append('Each exception must be an object');continue
        ident=d.get('id')
        if not isinstance(ident,str):
            errors.append('Exception id must be a string');continue
        if ident in allowed:errors.append('Duplicate exception: '+str(ident));continue
        if ident not in byid:errors.append('Stale/unknown exception: '+str(ident));continue
        if d.get('role') not in roles or not str(d.get('reason','')).strip():errors.append('Exception needs a role and reason: '+ident);continue
        if d.get('text_sha256')!=byid[ident]['text_sha256']:errors.append('Changed exception text: '+ident);continue
        allowed[ident]=d
    for c in candidates:
        c['status']='reviewed_exception' if c['id'] in allowed else 'unresolved'
        if c['id'] in allowed:c['decision']=allowed[c['id']]
    unresolved=sum(c['status']=='unresolved' for c in candidates)
    return {'status':'invalid_review' if errors else 'needs_review' if unresolved or coverage else 'no_unresolved_candidates','profile':profile,'files':inventory,'candidates':candidates,'unresolved':unresolved,'reviewed_exceptions':len(allowed),'coverage_gaps':coverage,'errors':errors,'manual_review_required':True,'scope':'Romanian finite-lexicon voice review. Does not establish complete grammar, legal validity, meaning preservation, or image/OLE content. DOCX reads accepted text including tables, headers, footers, foot/endnotes and text boxes; excludes deleted revisions and reviewer comments.'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('paths',nargs='+',type=Path)
    p.add_argument('--root',type=Path)
    p.add_argument('--profile',choices=['formal','notice'],default='formal',help='notice does not flag second-person addressing; first-person still reviewed')
    p.add_argument('--review',type=Path)
    p.add_argument('--report',type=Path)
    a=p.parse_args(argv)
    try:
        # Explicit file list avoids silently scanning baselines/reports or skipping annexes.
        if any(not x.is_file() for x in a.paths):raise StyleInputError('Pass existing files, not directories; enumerate the intended scope explicitly')
        r=analyze(a.paths,a.root.resolve() if a.root else None,a.profile,json.loads(a.review.read_text(encoding='utf-8')) if a.review else None)
        output=json.dumps(r,ensure_ascii=False,indent=2)+'\n'
        if a.report:write_report(a.report,output,[*a.paths,a.review],StyleInputError)
        else:print(output,end='')
        return 2 if r['errors'] else 1 if r['unresolved'] or r['coverage_gaps'] else 0
    except (ValueError,OSError,ET.ParseError,BadZipFile) as e:
        print(json.dumps({'status':'input_error','error':str(e)},ensure_ascii=False));return 2

if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # why: a Windows pipe defaults to the ANSI code page (no ș, ț, Cyrillic)
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8")
    raise SystemExit(main())
