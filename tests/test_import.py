import os
import unittest

import networkx as nx

import pybel


class TestImport(unittest.TestCase):
    def setUp(self):
        self.graph = nx.MultiDiGraph()

        self.graph.add_node('TestValue1', namespace='TestNS1')
        self.graph.add_node('TestValue2', namespace='TestNS1')
        self.graph.add_node('TestValue3', namespace='TestNS1')
        self.graph.add_node('TestValue4', namespace='TestNS1')
        self.graph.add_node('TestValue5', namespace='TestNS1')

        self.graph.add_edge('TestValue1', 'TestValue2', attr_dict={
            'Citation': ("Pubmed", "That one article from last week", "123455"),
            'Evidence': "Evidence 1 w extra notes",
            'TESTAN1': 'TestAnnot1',
            'relation': 'increases'
        })
        self.graph.add_edge('TestValue2', 'TestValue3', attr_dict={
            'Citation': ("Pubmed", "That one article from last week", "123455"),
            'Evidence': "Evidence 1 w extra notes",
            'TESTAN1': 'TestAnnot1',
            'relation': 'decreases',
            'TESTAN2': 'B'
        })
        self.graph.add_edge('TestValue2', 'TestValue4', attr_dict={
            'Citation': ("Pubmed", "That one article from last week", "123455"),
            'Evidence': "Evidence 1 w extra notes",
            'TESTAN1': 'TestAnnot1',
            'relation': 'directlyDecreases',
            'TESTAN2': 'B'
        })
        self.graph.add_edge('TestValue4', 'TestValue5', attr_dict={
            'Citation': ("Pubmed", "That other article from last week", "123456"),
            'Evidence': "Evidence 3",
            'TESTAN1': 'TestAnnot2',
            'relation': 'association'
        })

    @unittest.skip('Only works on local')
    def test_parse(self):
        """Tests no exceptions thrown during parsing. Needs internet connection"""
        with open(os.path.expandvars('$PYBEL_BASE/tests/bel/small_corpus.bel')) as f:
            pybel.from_file(f)

    @unittest.skip('Only works on local')
    def test_load(self):
        """Test graph imports correct nodes and edges"""
        with open(os.path.expandvars('$PYBEL_BASE/tests/bel/test_bel_1.bel')) as f:
            result = pybel.from_file(f)
        self.assertSetEqual(set(self.graph.nodes()), set(result.nodes()))

    @unittest.skip('Takes too long to compile for now')
    def test_full(self):
        path = os.path.expandvars('$PYBEL_BASE/tests/bel/test_bel_1.bel')
        g = pybel.from_bel(path)

        expected_document_metadata = {
            'Name': "PyBEL Test Document",
            "Description": "Made for testing PyBEL parsing",
            'Version': "1.6",
            'Copyright': "Copyright (c) Charles Tapley Hoyt. All Rights Reserved.",
            'Authors': "Charles Tapley Hoyt",
            'Licenses': "Other / Proprietary",
            'ContactInfo': "charles.hoyt@scai.fraunhofer.de"
        }

        self.assertEqual(expected_document_metadata, g.mdp.document_metadata)
