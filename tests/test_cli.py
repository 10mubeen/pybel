import json
import logging
import os
import unittest

import networkx as nx
from click.testing import CliRunner

from pybel import cli

log = logging.getLogger(__name__)
dir_path = os.path.dirname(os.path.realpath(__file__))


class TestCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_path = os.path.join(dir_path, 'bel', 'test_bel_1.bel')

    def test_pickle(self):
        test_file = 'mygraph.gpickle'

        with self.runner.isolated_filesystem():
            abs_test_file = os.path.abspath(test_file)
            result = self.runner.invoke(cli.main, ['to_pickle', '--path', self.test_path, '--output', abs_test_file])
            log.info('File path: {}'.format(abs_test_file))
            self.assertEqual(0, result.exit_code)
            self.assertTrue(os.path.exists(abs_test_file))
            g = nx.read_gpickle(abs_test_file)
            self.assertTrue(isinstance(g, nx.MultiDiGraph))

    def test_graphml(self):
        test_file = 'mygraph.graphml'

        with self.runner.isolated_filesystem():
            abs_test_file = os.path.abspath(test_file)
            result = self.runner.invoke(cli.main, ['to_graphml', '--path', self.test_path, '--output', abs_test_file])
            log.info('File path: {}'.format(abs_test_file))
            self.assertEqual(0, result.exit_code)
            self.assertTrue(os.path.exists(abs_test_file))
            g = nx.read_graphml(abs_test_file)
            self.assertTrue(isinstance(g, (nx.MultiDiGraph, nx.DiGraph)))

    def test_json(self):
        test_file = 'mygraph.json'

        with self.runner.isolated_filesystem():
            abs_test_file = os.path.abspath(test_file)
            result = self.runner.invoke(cli.main, ['to_json', '--path', self.test_path, '--output', abs_test_file])
            log.info('File path: {}'.format(abs_test_file))
            self.assertEqual(0, result.exit_code, msg=result.exc_info)
            self.assertTrue(os.path.exists(abs_test_file))

            with open(abs_test_file) as f:
                loaded = json.load(f)
                self.assertIsNotNone(loaded)

    @unittest.skip
    def test_csv(self):
        test_edge_file = 'myedges.csv'

        with self.runner.isolated_filesystem():
            abs_test_edge_file = os.path.abspath(test_edge_file)
            result = self.runner.invoke(cli.main,
                                        ['to_csv', '--path', self.test_path, '--edge-path', abs_test_edge_file])
            log.info('File paths: {}'.format(abs_test_edge_file))
            self.assertEqual(0, result.exit_code, msg=result.exc_info)
            self.assertTrue(os.path.exists(abs_test_edge_file))

            with open(abs_test_edge_file) as f:
                loaded = json.load(f)
                self.assertIsNotNone(loaded)
