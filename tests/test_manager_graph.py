import os
import tempfile
import unittest

import sqlalchemy.exc

import pybel
from pybel.manager.graph_cache import GraphCacheManager
from tests.constants import BelReconstitutionMixin, test_bel, mock_bel_resources


class TestGraphCache(BelReconstitutionMixin, unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.dir, 'test.db')
        self.connection = 'sqlite:///' + self.db_path
        self.gcm = GraphCacheManager(connection=self.connection)

    def tearDown(self):
        os.remove(self.db_path)
        os.rmdir(self.dir)

    @mock_bel_resources
    def test_load_reload(self, mock_get):
        path, name, label = test_bel, 'PyBEL Test Document 1', '1.6'

        g = pybel.from_path(path, complete_origin=True)
        self.gcm.store_graph(g)

        x = self.gcm.ls()

        self.assertEqual(1, len(x))
        self.assertEqual((name, label), x[0])

        g2 = self.gcm.get_graph(name, label)
        self.bel_1_reconstituted(g2)

    @mock_bel_resources
    def test_integrity_failure(self, mock_get):
        """Tests that a graph with the same name and version can't be added twice"""
        g1 = pybel.from_path(test_bel)
        self.gcm.store_graph(g1)

        with self.assertRaises(sqlalchemy.exc.IntegrityError):
            self.gcm.store_graph(g1)

    @mock_bel_resources
    def test_get_versions(self, mock_get):
        TEST_NAME = 'TEST'
        TEST_V1 = '1.6'
        TEST_V2 = '1.7'

        g1 = pybel.from_path(test_bel)
        g1.document['name'] = TEST_NAME
        g1.document['version'] = TEST_V1

        self.gcm.store_graph(g1)

        g2 = pybel.from_path(test_bel)
        g2.document['name'] = TEST_NAME
        g2.document['version'] = TEST_V2

        self.gcm.store_graph(g2)

        self.assertEqual({'1.7', '1.6'}, set(self.gcm.get_graph_versions('TEST')))

        self.assertEqual('1.7', self.gcm.get_graph('TEST').document['version'])
