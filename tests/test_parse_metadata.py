import logging
import os
import unittest

from pybel.parsers import ControlParser, MetadataParser
from pybel.parsers.utils import sanitize_file_lines, split_file_to_annotations_and_definitions

logging.getLogger("requests").setLevel(logging.WARNING)

dir_path = os.path.dirname(os.path.realpath(__file__))


class TestSanitize(unittest.TestCase):
    def test_a(self):
        s = '''SET Evidence = "The phosphorylation of S6K at Thr389, which is the TORC1-mediated site, was not inhibited
in the SIN1-/- cells (Figure 5A)."'''.split('\n')

        expect = [
            'SET Evidence = "The phosphorylation of S6K at Thr389, which is the TORC1-mediated site, was not inhibited '
            'in the SIN1-/- cells (Figure 5A)."']
        result = list(sanitize_file_lines(s))
        self.assertEqual(expect, result)

    def test_b(self):
        s = [
            '# Set document-defined annotation values\n',
            'SET Species = 9606',
            'SET Tissue = "t-cells"',
            '# Create an Evidence Line for a block of BEL Statements',
            'SET Evidence = "Here we show that interfereon-alpha (IFNalpha) is a potent producer \\',
            'of SOCS expression in human T cells, as high expression of CIS, SOCS-1, SOCS-2, \\',
            'and SOCS-3 was detectable after IFNalpha stimulation. After 4 h of stimulation \\',
            'CIS, SOCS-1, and SOCS-3 had ret'
        ]

        result = list(sanitize_file_lines(s))

        expect = [
            'SET Species = 9606',
            'SET Tissue = "t-cells"',
            'SET Evidence = "Here we show that interfereon-alpha (IFNalpha) is a potent producer of SOCS expression in '
            'human T cells, as high expression of CIS, SOCS-1, SOCS-2, and SOCS-3 was detectable after IFNalpha '
            'stimulation. After 4 h of stimulation CIS, SOCS-1, and SOCS-3 had ret'
        ]

        self.assertEqual(expect, result)

    def test_c(self):
        s = [
            'SET Evidence = "yada yada yada" //this is a comment'
        ]

        result = list(sanitize_file_lines(s))
        expect = ['SET Evidence = "yada yada yada"']

        self.assertEqual(expect, result)

    def test_d(self):
        """Test forgotten delimiters"""
        s = [
            'SET Evidence = "Something',
            'or other',
            'or other"'
        ]

        result = list(sanitize_file_lines(s))
        expect = ['SET Evidence = "Something or other or other"']

        self.assertEqual(expect, result)

    def test_e(self):
        path = os.path.join(dir_path, 'bel', 'test_bel_1.bel')

        with open(path) as f:
            lines = list(sanitize_file_lines(f))

        self.assertEqual(26, len(lines))

    def test_f(self):
        s = '''SET Evidence = "Arterial cells are highly susceptible to oxidative stress, which can induce both necrosis
and apoptosis (programmed cell death) [1,2]"'''.split('\n')
        lines = list(sanitize_file_lines(s))
        self.assertEqual(1, len(lines))


class TestSplitLines(unittest.TestCase):
    def test_parts(self):
        path = os.path.join(dir_path, 'bel', 'test_bel_1.bel')

        with open(path) as f:
            docs, defs, states = split_file_to_annotations_and_definitions(f)

        self.assertEqual(7, len(docs))
        self.assertEqual(5, len(defs))
        self.assertEqual(14, len(states))

        print(*docs, sep='\n')
        print('--')
        print(*defs, sep='\n')
        print('--')
        print(*states, sep='\n')


class TestParseMetadata(unittest.TestCase):
    def setUp(self):
        self.parser = MetadataParser()

    def test_control_1(self):
        s = 'DEFINE NAMESPACE MGI AS URL "http://resource.belframework.org/belframework/1.0/namespace/mgi-approved-symbols.belns"'

        self.parser.parse(s)
        self.assertIn('MGI', self.parser.namespace_dict)
        self.assertIn('MGI', self.parser.namespace_metadata)

    def test_control_2(self):
        s = 'DEFINE NAMESPACE Custom1 AS LIST {"A","B","C"}'
        self.parser.parse(s)
        self.assertIn('Custom1', self.parser.namespace_dict)
        self.assertIn('Custom1', self.parser.namespace_metadata)

    def test_control_3(self):
        s = 'DEFINE ANNOTATION CellStructure AS URL "http://resource.belframework.org/belframework/1.0/annotation/mesh-cell-structure.belanno"'
        self.parser.parse(s)
        self.assertIn('CellStructure', self.parser.annotations_dict)
        self.assertIn('CellStructure', self.parser.annotations_metadata)

    def test_control_4(self):
        s = 'DEFINE ANNOTATION TextLocation AS LIST {"Abstract","Results","Legend","Review"}'
        self.parser.parse(s)
        self.assertIn('TextLocation', self.parser.annotations_dict)
        self.assertIn('TextLocation', self.parser.annotations_metadata)

    def test_control_compound_1(self):
        s1 = 'DEFINE NAMESPACE MGI AS URL "http://resource.belframework.org/belframework/1.0/namespace/mgi-approved-symbols.belns"'
        s2 = 'DEFINE NAMESPACE CHEBI AS URL "http://resource.belframework.org/belframework/1.0/namespace/chebi-names.belns"'

        self.parser.parse_lines([s1, s2])

        self.assertIn('MGI', self.parser.namespace_dict)
        self.assertIn('CHEBI', self.parser.namespace_dict)

    def test_control_compound_2(self):
        s1 = 'DEFINE ANNOTATION CellStructure AS  URL "http://resource.belframework.org/belframework/1.0/annotation/mesh-cell-structure.belanno"'
        s2 = 'DEFINE ANNOTATION CellLine AS  URL "http://resource.belframework.org/belframework/1.0/annotation/atcc-cell-line.belanno"'
        s3 = 'DEFINE ANNOTATION TextLocation AS  LIST {"Abstract","Results","Legend","Review"}'
        self.parser.parse_lines([s1, s2, s3])

        self.assertIn('CellStructure', self.parser.annotations_dict)
        self.assertIn('CellLine', self.parser.annotations_dict)
        self.assertIn('TextLocation', self.parser.annotations_dict)

    def test_parse_document(self):
        s = '''SET DOCUMENT Name = "Alzheimer's Disease Model"'''

        self.parser.parse(s)

        self.assertIn('Name', self.parser.document_metadata)
        self.assertEqual("Alzheimer's Disease Model", self.parser.document_metadata['Name'])

    def test_parse_namespace_list_1(self):
        s = '''DEFINE NAMESPACE BRCO AS LIST {"Hippocampus", "Parietal Lobe"}'''

        self.parser.parse(s)

        expected_namespace_dict = {
            'BRCO': {'Hippocampus', 'Parietal Lobe'}
        }

        expected_namespace_annoations = {
            'BRCO': {}
        }

        self.assertIn('BRCO', self.parser.namespace_dict)
        self.assertEqual(2, len(self.parser.namespace_dict['BRCO']))
        self.assertEqual(expected_namespace_dict, self.parser.namespace_dict)

        self.assertIn('BRCO', self.parser.namespace_metadata)
        self.assertEqual(expected_namespace_annoations, self.parser.namespace_metadata)

    def test_parse_namespace_list_2(self):
        s1 = '''SET DOCUMENT Name = "Alzheimer's Disease Model"'''
        s2 = '''DEFINE NAMESPACE BRCO AS LIST {"Hippocampus", "Parietal Lobe"}'''

        self.parser.parse(s1)
        self.parser.parse(s2)

        expected_namespace_dict = {
            'BRCO': {'Hippocampus', 'Parietal Lobe'}
        }

        expected_namespace_annoations = {
            'BRCO': {
                'Name': "Alzheimer's Disease Model",
            }
        }

        self.assertIn('BRCO', self.parser.namespace_dict)
        self.assertEqual(2, len(self.parser.namespace_dict['BRCO']))
        self.assertEqual(expected_namespace_dict, self.parser.namespace_dict)
        self.assertEqual(expected_namespace_annoations, self.parser.namespace_metadata)

    def test_parse_namespace_url_1(self):
        path = os.path.join(dir_path, 'bel', 'test_ns_1.belns')
        s = '''DEFINE NAMESPACE TEST AS URL "file://{}"'''.format(path)
        self.parser.parse(s)

        expected_values = {
            'TestValue1': 'O',
            'TestValue2': 'O',
            'TestValue3': 'O',
            'TestValue4': 'O',
            'TestValue5': 'O'
        }

        self.assertIn('TEST', self.parser.namespace_dict)
        self.assertEqual(expected_values, self.parser.namespace_dict['TEST'])


class TestParseControl(unittest.TestCase):
    def setUp(self):
        custom_annotations = {
            'Custom1': {'Custom1_A', 'Custom1_B'},
            'Custom2': {'Custom2_A', 'Custom2_B'}
        }

        self.parser = ControlParser(custom_annotations=custom_annotations)

    def test_citation_short(self):
        s = 'SET Citation = {"PubMed","Trends in molecular medicine","12928037"}'

        self.parser.parse(s)

        expected_citation = {
            'type': 'PubMed',
            'name': 'Trends in molecular medicine',
            'reference': '12928037',
        }

        self.assertEqual(expected_citation, self.parser.citation)

    def test_citation_long(self):
        s = 'SET Citation = {"PubMed","Trends in molecular medicine","12928037","","de Nigris|Lerman A|Ignarro LJ",""}'

        self.parser.parse(s)

        expected_citation = {
            'type': 'PubMed',
            'name': 'Trends in molecular medicine',
            'reference': '12928037',
            'date': '',
            'authors': 'de Nigris|Lerman A|Ignarro LJ',
            'comments': ''
        }

        self.assertEqual(expected_citation, self.parser.citation)

    def test_citation_error(self):
        s = 'SET Citation = {"PubMed","Trends in molecular medicine","12928037",""}'
        with self.assertRaises(Exception):
            self.parser.parse(s)

    def test_evidence(self):
        s = 'SET Evidence = "For instance, during 7-ketocholesterol-induced apoptosis of U937 cells"'
        self.parser.parse(s)

        expected_annotation = {
            'Evidence': 'For instance, during 7-ketocholesterol-induced apoptosis of U937 cells'
        }

        self.assertEqual(expected_annotation, self.parser.annotations)

    def test_custom_annotation(self):
        s = 'SET Custom1 = "Custom1_A"'
        self.parser.parse(s)

        expected_annotation = {
            'Custom1': 'Custom1_A'
        }

        self.assertEqual(expected_annotation, self.parser.annotations)

    def test_custom_key_failure(self):
        s = 'SET FAILURE = "never gonna happen"'
        with self.assertRaises(Exception):
            self.parser.parse(s)

    def test_custom_value_failure(self):
        s = 'SET Custom1 = "Custom1_C"'
        with self.assertRaises(Exception):
            self.parser.parse(s)

    def test_reset_annotation(self):
        s1 = 'SET Evidence = "a"'
        s2 = 'SET Evidence = "b"'

        self.parser.parse(s1)
        self.parser.parse(s2)

        self.assertEqual('b', self.parser.annotations['Evidence'])

    def test_unset_evidence(self):
        s1 = 'SET Evidence = "a"'
        s2 = 'UNSET Evidence'

        self.parser.parse(s1)
        self.parser.parse(s2)

        self.assertEqual({}, self.parser.annotations)

    def test_unset_custom(self):
        s1 = 'SET Custom1 = "Custom1_A"'
        s2 = 'UNSET Custom1'

        self.parser.parse(s1)
        self.parser.parse(s2)

        self.assertEqual({}, self.parser.annotations)

    def test_reset_citation(self):
        s1 = 'SET Citation = {"a","b","c"}'
        s2 = 'SET Evidence = "d"'

        s3 = 'SET Citation = {"e","f","g"}'
        s4 = 'SET Evidence = "h"'

        self.parser.parse(s1)
        self.parser.parse(s2)
        self.parser.parse(s3)
        self.parser.parse(s4)

        self.assertEqual('h', self.parser.annotations['Evidence'])
        self.assertEqual('e', self.parser.citation['type'])
        self.assertEqual('f', self.parser.citation['name'])
        self.assertEqual('g', self.parser.citation['reference'])


class TestParseEvidence(unittest.TestCase):
    def test_111(self):
        statement = '''SET Evidence = "1.1.1 Easy case"'''
        expect = '''SET Evidence = "1.1.1 Easy case'''
        lines = list(sanitize_file_lines(statement.split('\n')))
        self.assertEqual(1, len(lines))
        line = lines[0]
        self.assertTrue(expect, line)

    def test_131(self):
        statement = '''SET Evidence = "3.1 Backward slash break test \\
second line"'''
        expect = '''SET Evidence = "3.1 Backward slash break test second line"'''
        lines = list(sanitize_file_lines(statement.split('\n')))
        self.assertEqual(1, len(lines))
        line = lines[0]
        self.assertEqual(expect, line)

    def test_132(self):
        statement = '''SET Evidence = "3.2 Backward slash break test with whitespace \\
second line"'''
        expect = '''SET Evidence = "3.2 Backward slash break test with whitespace second line"'''
        lines = list(sanitize_file_lines(statement.split('\n')))
        self.assertEqual(1, len(lines))
        line = lines[0]
        self.assertEqual(expect, line)

    def test_133(self):
        statement = '''SET Evidence = "3.3 Backward slash break test \\
second line \\
third line"'''
        expect = '''SET Evidence = "3.3 Backward slash break test second line third line"'''
        lines = list(sanitize_file_lines(statement.split('\n')))
        self.assertEqual(1, len(lines))
        line = lines[0]
        self.assertEqual(expect, line)

    def test_141(self):
        statement = '''SET Evidence = "4.1 Malformed line breakcase
second line"'''
        expect = '''SET Evidence = "4.1 Malformed line breakcase second line"'''
        lines = list(sanitize_file_lines(statement.split('\n')))
        self.assertEqual(1, len(lines))
        line = lines[0]
        self.assertEqual(expect, line)

    def test_142(self):
        statement = '''SET Evidence = "4.2 Malformed line breakcase
second line
third line"'''
        expect = '''SET Evidence = "4.2 Malformed line breakcase second line third line"'''
        lines = list(sanitize_file_lines(statement.split('\n')))
        self.assertEqual(1, len(lines))
        line = lines[0]
        self.assertEqual(expect, line)
