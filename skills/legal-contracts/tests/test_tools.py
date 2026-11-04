"""Synthetic invariants; these tests do not establish current law or model behaviour."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
R=module('docx_redline'); B=module('build_docx')

def fixture(path,comments=False):
    d=Document(); s=d.sections[0]
    s.page_width=Cm(21);s.page_height=Cm(29.7)
    s.top_margin=s.bottom_margin=s.left_margin=s.right_margin=Cm(2.5)
    for name in ['Normal','Title','Heading 1']:
        d.styles[name].font.name='Times New Roman';d.styles[name].font.color.rgb=RGBColor(0,0,0)
        d.styles[name].font.size=Pt(11 if name=='Normal' else 16 if name=='Title' else 12)
    d.add_paragraph('Exemplu sintetic de revizuire','Title')
    d.add_paragraph('Document tehnic de test. Nu reprezintă un contract validat juridic și nu este destinat semnării.')
    p=d.add_paragraph('1. Plata se efectuează în ')
    p.add_run('10').bold=True; p.add_run(' zile').italic=True; p.add_run(' de la primirea facturii.')
    d.add_paragraph('2. Livrabilele sunt descrise în Anexa A.')
    d.add_paragraph('3. Comunicările se transmit în scris. Text provizoriu.')
    t=d.add_table(rows=2,cols=2);t.style='Table Grid'
    t.cell(0,0).text='Anexă';t.cell(0,1).text='Obiect'
    t.cell(1,0).text='A';t.cell(1,1).text='Specificație sintetică'
    p=d.add_paragraph('Anexa A conține exclusiv date fictive pentru verificare.')
    if comments: d.add_comment(p.runs[0],text='Комментарий на русском языке для проверки сохранности.',author='Reviewer')
    p=d.add_paragraph('Referință internă: '); p.style='List Number'
    link=OxmlElement('w:hyperlink');link.set(qn('w:anchor'),'annex_a')
    run=OxmlElement('w:r');tt=OxmlElement('w:t');tt.text='Anexa A';run.append(tt);link.append(run)
    p._p.append(link)
    mark=OxmlElement('w:bookmarkStart');mark.set(qn('w:id'),'100');mark.set(qn('w:name'),'annex_a')
    end=OxmlElement('w:bookmarkEnd');end.set(qn('w:id'),'100')
    d.paragraphs[5]._p.insert(0,mark);d.paragraphs[5]._p.append(end)
    s.header.paragraphs[0].text='EXEMPLU SINTETIC'
    s.footer.paragraphs[0].text='Verificare tehnică a modificărilor'
    B.polish(d);d.save(path)

def plan():
    return {'author':'Legal review','changes':[
        {'paragraph':2,'expected_paragraph':'1. Plata se efectuează în 10 zile de la primirea facturii.',
         'old':'10 zile','new':'15 zile'},
        {'paragraph':4,'expected_paragraph':'3. Comunicările se transmit în scris. Text provizoriu.',
         'old':' Text provizoriu.','new':''}]}

class RedlineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.src=self.base/'original.docx';fixture(self.src)
    def test_multirun_accept_reject_and_preservation(self):
        before=self.src.read_bytes(); out=self.base/'out';r=R.apply(self.src,plan(),out)
        self.assertEqual(before,self.src.read_bytes());self.assertEqual(r['revisions'],3)
        self.assertTrue(r['accept_equals_clean']);self.assertTrue(r['reject_equals_original'])
        a=R.read_package(self.src)[1];b=R.read_package(out/'tracked.docx')[1]
        for n in a:
            if n not in {'word/document.xml','word/settings.xml'}:self.assertEqual(a[n],b[n],n)
        clean=Document(out/'clean.docx')
        self.assertEqual(clean.paragraphs[2].text,'1. Plata se efectuează în 15 zile de la primirea facturii.')
        self.assertEqual(clean.tables[0].cell(1,1).text,'Specificație sintetică')
        self.assertEqual(clean.sections[0].header.paragraphs[0].text,'EXEMPLU SINTETIC')
    def test_existing_comment_preserved(self):
        fixture(self.src,comments=True);out=self.base/'out';R.apply(self.src,plan(),out)
        a=R.read_package(self.src)[1];b=R.read_package(out/'clean.docx')[1]
        self.assertEqual(a['word/comments.xml'],b['word/comments.xml'])
        self.assertIn('Комментарий',b['word/comments.xml'].decode())
    def test_table_cell_edit(self):
        inv=R.inspect(self.src);t=next(p for p in inv['paragraphs'] if p['text']=='Specificație sintetică')
        p={'author':'Review','changes':[dict(t,expected_paragraph=t['text'],old='sintetică',new='de test')]}
        R.apply(self.src,p,self.base/'out')
        self.assertEqual(Document(self.base/'out/clean.docx').tables[0].cell(1,1).text,'Specificație de test')
    def test_bad_baseline_refused_without_output(self):
        p=plan();p['changes'][0]['expected_paragraph']='Different'
        with self.assertRaises(ValueError):R.apply(self.src,p,self.base/'out')
        self.assertFalse((self.base/'out').exists())
    def test_complex_target_refused(self):
        inv=R.inspect(self.src);t=next(p for p in inv['paragraphs'] if p['text'].startswith('Referință'))
        p={'author':'Review','changes':[dict(t,expected_paragraph=t['text'],old='internă',new='nouă')]}
        with self.assertRaisesRegex(ValueError,'Complex'):R.apply(self.src,p,self.base/'out')
    def test_existing_revisions_refused(self):
        R.apply(self.src,plan(),self.base/'out')
        with self.assertRaisesRegex(ValueError,'Existing revisions'):R.apply(self.base/'out/tracked.docx',plan(),self.base/'out2')
    def test_tampered_clean_is_detected(self):
        R.apply(self.src,plan(),self.base/'out');f=self.base/'out/clean.docx'
        d=Document(f);d.tables[0].cell(1,1).text='Lost legal content';d.save(f)
        with self.assertRaises(ValueError):R.verify(self.src,self.base/'out/tracked.docx',f)
    def test_output_overwrite_refused(self):
        R.apply(self.src,plan(),self.base/'out')
        with self.assertRaisesRegex(ValueError,'must be new'):R.apply(self.src,plan(),self.base/'out')
    def test_builder_creates_readable_docx(self):
        target=self.base/'built.docx'
        B.build({'title':'Proiect sintetic','blocks':[{'type':'paragraph','text':'Text în română.'},
                {'type':'table','rows':[['Anexă','Conținut'],['A','Test']]}]},target)
        d=Document(target);self.assertEqual(d.paragraphs[1].text,'Text în română.')
        self.assertEqual(d.tables[0].cell(1,1).text,'Test')

if __name__=='__main__':unittest.main(verbosity=2)
