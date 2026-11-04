"""Voice-lint regression tests. Not a Romanian grammar or legal audit."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from docx import Document

S=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ro_style',S/'scripts/check_ro_style.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

class StyleTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
    def md(self,text,name='contract.ro.md'):
        p=self.root/name;p.write_text(text);return p
    def run_file(self,p,decisions=None,profile='formal'):
        return M.analyze([p],self.root,profile,decisions)
    def allow(self,r,role='personal_declaration'):
        return {'exceptions':[{'id':c['id'],'text_sha256':c['text_sha256'],'role':role,'reason':'Individual signed declaration, reviewed in context.'} for c in r['candidates']]}
    def test_reported_failure_is_detected(self):
        r=self.run_file(self.md('Dacă anulăm un serviciu și nu este acceptată o alternativă, restituim partea neprestată și respectăm celelalte drepturi aplicabile.'))
        self.assertEqual({c['token'] for c in r['candidates']},{'anulăm','restituim','respectăm'})
        self.assertEqual(r['status'],'needs_review')
    def test_third_person_counterpart(self):
        r=self.run_file(self.md('Dacă Furnizorul anulează un serviciu și nu este acceptată o alternativă, acesta restituie partea neprestată și respectă celelalte drepturi aplicabile.'))
        self.assertEqual(r['unresolved'],0)
    def test_declaration_is_not_silently_discarded(self):
        p=self.md('Solicit expres începerea serviciilor și confirm că am luat cunoștință de condiții.','formulare.ro.md');r=self.run_file(p)
        self.assertGreater(r['unresolved'],0);done=self.run_file(p,self.allow(r))
        self.assertEqual(done['unresolved'],0);self.assertTrue(done['manual_review_required'])
    def test_whole_form_is_not_an_exemption(self):
        p=self.md('Solicit expres începerea.\nNu garantăm venituri.','formulare.ro.md');r=self.run_file(p)
        d=self.allow(r);d['exceptions']=[x for x in d['exceptions'] if x['id']==r['candidates'][0]['id']]
        done=self.run_file(p,d)
        self.assertEqual([x['token'] for x in done['candidates'] if x['status']=='unresolved'],['garantăm'])
    def test_changed_paragraph_invalidates_decision(self):
        p=self.md('Solicit începerea serviciilor.');r=self.run_file(p);d=self.allow(r)
        p.write_text('Solicit începerea tuturor serviciilor.')
        self.assertEqual(self.run_file(p,d)['status'],'invalid_review')
    def test_exception_cannot_omit_reason_or_hash(self):
        p=self.md('Confirm primirea.');r=self.run_file(p);d=self.allow(r);d['exceptions'][0]['reason']=''
        self.assertTrue(self.run_file(p,d)['errors'])
        d=self.allow(r);d['exceptions'][0]['text_sha256']='incorrect';self.assertTrue(self.run_file(p,d)['errors'])
    def test_quotes_do_not_hide_company_voice(self):
        self.assertGreater(self.run_file(self.md('Clauza: „Noi vom răspunde și restituim suma.”'))['unresolved'],0)
    def test_new_is_not_the_pronoun_we(self):
        r=self.run_file(self.md('Sistem nou; servicii noi, comenzi noi și furnizori noi. Interes legitim, regim legal, acces minim.'))
        self.assertEqual(r['unresolved'],0)
    def test_ascii_and_decomposed_diacritics(self):
        r=self.run_file(self.md('Daca anulam, restituim. Respecta\u0306m condițiile.'))
        self.assertEqual(len(r['candidates']),3)
    def test_notice_address_profile(self):
        p=self.md('Puteți solicita accesul. Prelucrăm datele.')
        self.assertEqual(self.run_file(p,profile='notice')['unresolved'],1)
        self.assertEqual(self.run_file(p)['unresolved'],2)
    def test_every_copy_is_in_scope(self):
        a=self.md('Nu garantăm venituri.','a.ro.md');b=self.md('Nu garantăm venituri.','b.ro.md')
        r=M.analyze([a,b],self.root);self.assertEqual(len(r['candidates']),2)
        self.assertNotEqual(r['candidates'][0]['id'],r['candidates'][1]['id'])
    def docx(self):
        p=self.root/'contract.docx';d=Document();d.add_paragraph('Furnizorul prestează serviciul.')
        d.add_table(rows=1,cols=1).cell(0,0).text='Restituim prețul.'
        d.sections[0].header.paragraphs[0].text='Noi vom răspunde.'
        d.sections[0].footer.paragraphs[0].text='Păstrăm datele.'
        d.save(p);return p
    def test_word_tables_headers_and_footers(self):
        r=self.run_file(self.docx());locs=[c['locator'] for c in r['candidates']]
        self.assertTrue(any(x.startswith('word/document.xml') for x in locs))
        self.assertTrue(any(x.startswith('word/header') for x in locs))
        self.assertTrue(any(x.startswith('word/footer') for x in locs))
    def patch_xml(self,p,part,body):
        with ZipFile(p) as z:data={n:z.read(n) for n in z.namelist()}
        data[part]=body.encode()
        with ZipFile(p,'w',ZIP_DEFLATED) as z:
            for n,b in data.items():z.writestr(n,b)
    def test_accepted_revisions_not_deleted_history(self):
        p=self.docx();self.patch_xml(p,'word/document.xml',f'<w:document xmlns:w="{M.W}"><w:body><w:p><w:del><w:r><w:delText>Anulăm.</w:delText></w:r></w:del><w:ins><w:r><w:t>Furnizorul anulează.</w:t></w:r></w:ins></w:p><w:moveFrom><w:p><w:r><w:t>Restituim.</w:t></w:r></w:p></w:moveFrom></w:body></w:document>')
        r=self.run_file(p);self.assertFalse(any(c['locator'].startswith('word/document.xml') for c in r['candidates']))
    def test_notes_textbox_and_split_runs(self):
        p=self.docx();self.patch_xml(p,'word/footnotes.xml',f'<w:footnotes xmlns:w="{M.W}"><w:footnote w:id="1"><w:p><w:r><w:t>Prelu</w:t></w:r><w:r><w:t>crăm datele.</w:t></w:r></w:p></w:footnote></w:footnotes>')
        self.patch_xml(p,'word/document.xml',f'<w:document xmlns:w="{M.W}"><w:body><w:p><w:r><w:pict><w:txbxContent><w:p><w:r><w:t>Anulăm.</w:t></w:r></w:p></w:txbxContent></w:pict></w:r></w:p></w:body></w:document>')
        r=self.run_file(p);self.assertTrue(any(c['token']=='Prelucrăm' for c in r['candidates']))
        self.assertEqual(sum(c['token']=='Anulăm' for c in r['candidates']),1)
        self.assertTrue(r['coverage_gaps'])
    def test_script_is_read_only(self):
        p=self.docx();b=p.read_bytes();self.run_file(p);self.assertEqual(p.read_bytes(),b)

    def test_corporate_placeholder_is_not_missed(self):
        self.assertTrue(any(t['rule']=='first_person_phrase' for t in M.tokens('Am [acțiunile și sistemele].')))
    def test_malformed_exception_is_reported(self):
        p=self.docx()
        r=M.analyze([p],decisions={'exceptions':['bad',{'id':[]} ]})
        self.assertEqual(r['status'],'invalid_review')
        self.assertEqual(len(r['errors']),2)

    def test_contract_address_auxiliary_and_action(self):
        hits=M.tokens('Confirmați că ați luat cunoștință și transmiteți comanda.')
        self.assertEqual([h['rule'] for h in hits],['direct_address']*3)

if __name__=='__main__':unittest.main(verbosity=2)
