import importlib.util, pathlib, unittest
spec=importlib.util.spec_from_file_location('structure',pathlib.Path(__file__).parents[1]/'scripts/check_structure.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class StructureTests(unittest.TestCase):
    def test_romanian_trailing_dot_numbering(self):
        # E2E 2026-11-05: '1.1.' (the usual Romanian form) was skipped and a duplicate passed unseen
        issues=m.inspect('## 1. Obiect\n1.1. Text.\n1.1. Alt.\n1.3. Salt.\n**2.1.** Alt articol.\n')
        rules=[i['rule'] for i in issues]
        self.assertIn('duplicate_clause',rules)
        self.assertEqual(rules.count('clause_sequence'),3)
    def test_mismatched_allocation(self):
        self.assertEqual(m.reconcile({'total':'3000','components':['220']*14}),['components: sum differs from total'])
    def test_decimal_rounding_and_installments(self):
        self.assertEqual(m.reconcile({'total':'3000','components':['214.29']*13+['214.23'],'installments':['1500','1500']}),[])
    def test_capacity_is_not_promised_total(self):
        self.assertEqual(m.reconcile({'total':'0','deliveries':[{'total':3,'periods':6,'per_period_cap':1}]}),[])
        self.assertTrue(m.reconcile({'total':'0','deliveries':[{'total':7,'periods':6,'per_period_cap':1}]}))
    def test_unknown_not_zero(self):
        for value in (None,'NaN','Infinity','-1',0):
            with self.assertRaises(Exception):m.reconcile({'total':value})
    def test_numbering(self):
        self.assertFalse(m.inspect('## 1 Obiect\n1.1 Text.\n1.2 Text.\n## 2 Preț\n2.1 Text.'))
        self.assertTrue(m.inspect('## 1 Obiect\n1.1 Text.\n1.1 Alt text.'))
    def test_packed_fields(self):
        self.assertTrue(m.inspect('Limba [ ]; data [ ]; locuri [ ]; preț [ ]; acces [ ].'))
        self.assertFalse(m.inspect('| Preț | [DE COMPLETAT] |'))

if __name__=='__main__':unittest.main()
