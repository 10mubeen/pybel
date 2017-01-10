import logging
import unittest
from io import StringIO

from requests.exceptions import ConnectionError

import pybel
from pybel.constants import GOCC_LATEST
from pybel.parser.canonicalize import to_bel
from tests.constants import test_bel, test_bel_4, mock_bel_resources

log = logging.getLogger('pybel')


class TestCanonicalize(unittest.TestCase):
    def canonicalize_helper(self, test_path):
        original = pybel.from_path(test_path)

        sio = StringIO()
        to_bel(original, sio)
        reloaded = pybel.BELGraph(lines=sio.getvalue().split('\n'))

        original.namespace_url['GOCC'] = GOCC_LATEST

        self.assertEqual(original.document, reloaded.document)
        self.assertEqual(original.namespace_owl, reloaded.namespace_owl)
        self.assertEqual(original.namespace_url, reloaded.namespace_url)
        self.assertEqual(original.annotation_url, reloaded.annotation_url)
        self.assertEqual(original.annotation_list, reloaded.annotation_list)

        self.assertEqual(set(original.nodes()), set(reloaded.nodes()))
        self.assertEqual(set(original.edges()), set(reloaded.edges()))

        # Really test everything is exactly the same, down to the edge data
        for u, v, d in original.edges_iter(data=True):
            if d['relation'] == 'hasMember':
                continue

            for d1 in original.edge[u][v].values():
                x = False

                for d2 in reloaded.edge[u][v].values():
                    if set(d1.keys()) == set(d2.keys()) and all(d1[k] == d2[k] for k in d1):
                        x = True

                self.assertTrue(x, msg="Nodes with problem: {}, {}".format(u, v))

    @mock_bel_resources
    def test_canonicalize_1(self, mock_get):
        self.canonicalize_helper(test_bel)

    def test_canonicalize_4(self):
        try:
            self.canonicalize_helper(test_bel_4)
        except ConnectionError as e:
            log.warning('Connection error: %s', e)
