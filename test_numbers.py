import json
import unittest
from decimal import Decimal
from financial_parser.numbers import parse_number
from financial_parser.exports import json_value


class NumberTests(unittest.TestCase):
    def test_explicit_fractional_profiles(self):
        for raw,profile in [('1,234.56','comma-dot'),('1.234,56','dot-comma'),
                            ('1 234.56','space-dot'),('1 234,56','space-comma'),
                            ('1\u202f234,56','space-comma'),('1\u00a0234.56','space-dot')]:
            with self.subTest(raw=raw):
                result=parse_number(raw,profile)
                self.assertEqual(result.status,'number')
                self.assertEqual(result.value,Decimal('1234.56'))
                self.assertEqual(result.raw_text,raw)
                self.assertIsInstance(result.value,Decimal)

    def test_auto_ambiguous_and_unique(self):
        for raw in ['1,234','1.234','△1,234','(1.234)']:
            result=parse_number(raw)
            self.assertEqual(result.status,'ambiguous')
            self.assertIsNone(result.value)
            self.assertGreater(len({x['value'] for x in result.interpretations}),1)
        for raw in ['1,234.56','1.234,56','1 234.56','1 234,56','1234.56']:
            self.assertEqual(parse_number(raw).value,Decimal('1234.56'))
        self.assertEqual(parse_number('1,234','comma-dot').value,Decimal('1234'))
        self.assertEqual(parse_number('1,234','dot-comma').value,Decimal('1.234'))

    def test_triangle_zero_zero_dash_blank_missing(self):
        negative=parse_number('△0')
        self.assertTrue(negative.negative_zero)
        self.assertTrue(negative.value.is_signed())
        self.assertEqual(negative.sign_style,'triangle')
        zero=parse_number('0')
        self.assertFalse(zero.negative_zero)
        self.assertEqual(zero.sign_style,'unsigned')
        for raw in ['－','-','—']:
            self.assertEqual(parse_number(raw).status,'dash')
            self.assertIsNone(parse_number(raw).value)
        self.assertEqual(parse_number(' \n').status,'blank')
        self.assertEqual(parse_number(None).status,'missing')

    def test_targeted_width_conversion_keeps_raw(self):
        raw='－１，２３４．５６'
        result=parse_number(raw,'comma-dot')
        self.assertEqual(result.value,Decimal('-1234.56'))
        self.assertEqual(result.raw_text,raw)
        self.assertEqual(parse_number('（１．２３４，５６）','dot-comma').value,Decimal('-1234.56'))

    def test_malformed_signs_and_footnotes_are_unparsed(self):
        for raw in ['--1','-△1','△-1','++1','+-1','(-1)','(△1)','1-',
                    '1,234*','1,234¹','1,234[1]','$1,234','1,234円','abc123',
                    '12,34.56','1,,234','1.2.3','1 23.45','NaN','Infinity',
                    '(123','123)','△','−−１','1\n234','1e3','123%']:
            with self.subTest(raw=raw):
                self.assertEqual(parse_number(raw,'comma-dot').status,'unparsed')
        for raw in ['1,234*','1,234¹','$123','△-1','(-1)']:
            self.assertEqual(parse_number(raw).status,'unparsed')

    def test_decimal_precision_and_json(self):
        raw='123456789012345678901234567890.1200'
        result=parse_number(raw,'comma-dot')
        self.assertEqual(str(result.value),raw)
        encoded=json.loads(json.dumps(result.to_dict(),default=json_value))
        self.assertEqual(encoded['value'],raw)
        self.assertEqual(encoded['raw_text'],raw)
        self.assertEqual(str(parse_number('△0').value),'-0')


class NumericPipelineTests(unittest.TestCase):
    def test_unit_evidence_and_profile_do_not_change_raw_cells(self):
        from pathlib import Path
        import tempfile
        from financial_parser import ParseConfig, parse
        raw_rows = None
        for profile in ['auto','comma-dot']:
            with tempfile.TemporaryDirectory() as tmp:
                result=parse('samples/financial-sample.pdf',tmp,ParseConfig(render=False,number_profile=profile))
                page=result['pages'][0]
                self.assertEqual(page['errors'],[])
                self.assertEqual(page['unit_evidence'][0]['currency'],'JPY')
                self.assertEqual(page['unit_evidence'][0]['scale'],Decimal('1000'))
                if raw_rows is None: raw_rows=page['tables'][0]['rows']
                self.assertEqual(raw_rows,page['tables'][0]['rows'])
                cell=next(c for c in page['tables'][0]['cells'] if c['raw_text']=='608,281')
                parsed=page['normalized_cells'][cell['id']]['number']
                self.assertEqual(parsed['raw_text'],'608,281')
                self.assertEqual(parsed['status'],'ambiguous' if profile=='auto' else 'number')
                if profile!='auto': self.assertEqual(parsed['value'],Decimal('608281'))
                stored=json.loads((Path(tmp)/'report.json').read_text())
                self.assertEqual(stored['pages'][0]['unit_evidence'][0]['scale'],'1000')
                triangle=next(c for c in page['tables'][0]['cells'] if c['raw_text']=='△0')
                self.assertEqual(stored['pages'][0]['normalized_cells'][triangle['id']]['number']['value'],'-0')
