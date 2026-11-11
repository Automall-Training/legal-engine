#!/usr/bin/env python3
"""Create a simple DOCX from reviewed JSON, not from unverified legal boilerplate."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _engine_env import reexec, refuse_inside_engine  # noqa: E402

try:
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
except ImportError as exc:  # why: plain python3 without the engine's packages → re-run inside .venv
    if __name__ == '__main__':
        reexec(__file__, exc.name or 'docx')
    raise


class BuildError(ValueError):
    """The document spec cannot be turned into a DOCX."""


def polish(d):
    """Clear inherited title ornament and set readable table borders/padding."""
    for name in ['Normal','Title','Heading 1','Heading 2']:
        style=d.styles[name]
        for node in list(style.element.xpath('./w:pPr/w:pBdr')): node.getparent().remove(node)
        for node in style.element.xpath('./w:rPr/w:rFonts'):
            for key in list(node.attrib):
                if key.endswith('Theme') or key.endswith('theme'): del node.attrib[key]
        for node in style.element.xpath('./w:rPr/w:color'):
            node.attrib.clear();node.set(qn('w:val'),'000000')
    for t in d.tables:
        props=t._tbl.tblPr
        borders=OxmlElement('w:tblBorders')
        for edge in ['top','left','bottom','right','insideH','insideV']:
            e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
        for old in props.findall(qn('w:tblBorders')):props.remove(old)
        props.append(borders)
        for i,row in enumerate(t.rows):
            for cell in row.cells:
                tc=cell._tc.get_or_add_tcPr();margin=OxmlElement('w:tcMar')
                for edge in ['top','left','bottom','right']:
                    e=OxmlElement('w:'+edge);e.set(qn('w:w'),'90');e.set(qn('w:type'),'dxa');margin.append(e)
                tc.append(margin)
                if i==0:
                    sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'F2F2F2');tc.append(sh)

def build(spec,output):
    refuse_inside_engine(output,BuildError)
    if Path(output).exists(): raise BuildError('Output exists; no overwrite')
    d=Document(); sec=d.sections[0]
    sec.page_width=Cm(21); sec.page_height=Cm(29.7)
    sec.top_margin=sec.bottom_margin=sec.left_margin=sec.right_margin=Cm(2.5)
    for name in ['Normal','Title','Heading 1','Heading 2']:
        s=d.styles[name]; s.font.name='Times New Roman'; s.font.color.rgb=RGBColor(0,0,0)
        s.font.size=Pt(11 if name=='Normal' else 16 if name=='Title' else 12)
        s.paragraph_format.space_after=Pt(6)
    lang=OxmlElement('w:lang'); lang.set(qn('w:val'),spec.get('language','ro-RO'))
    d.styles['Normal'].element.get_or_add_rPr().append(lang)
    d.add_paragraph(spec['title'],'Title')
    for b in spec['blocks']:
        if b['type']=='paragraph': d.add_paragraph(b['text'])
        elif b['type']=='heading': d.add_heading(b['text'],level=b.get('level',1))
        elif b['type']=='table':
            if not b['rows'] or any(len(r)!=len(b['rows'][0]) for r in b['rows']): raise BuildError('Invalid table')
            t=d.add_table(rows=0,cols=len(b['rows'][0])); t.style='Table Grid'
            for row in b['rows']:
                for cell,val in zip(t.add_row().cells,row): cell.text=str(val)
        else: raise BuildError('Unsupported block '+b['type'])
    d.core_properties.author=spec.get('author','')
    polish(d)
    d.save(output)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('spec'); p.add_argument('output'); a=p.parse_args(argv)
    try:
        build(json.loads(Path(a.spec).read_text(encoding='utf-8')),a.output)
    except (BuildError,KeyError,TypeError,AttributeError,OSError,json.JSONDecodeError) as e:
        print(json.dumps({'error':f'{type(e).__name__}: {e}'},ensure_ascii=False)); return 2
    print(json.dumps({'status':'created','output':str(Path(a.output).resolve())},ensure_ascii=False)); return 0

if __name__=='__main__':
    for _stream in (sys.stdout, sys.stderr):  # why: a Windows pipe defaults to the ANSI code page (no ș, ț, Cyrillic)
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8")
    sys.exit(main())
