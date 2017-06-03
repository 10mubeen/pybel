# -*- coding: utf-8 -*-

"""This module contains IO functions for outputting BEL graphs to lossy formats, such as GraphML and CSV"""

from __future__ import print_function

import json
import logging

import networkx as nx

from ..constants import NAMESPACE, NAME
from ..graph import BELGraph
from ..utils import flatten_dict, flatten_graph_data

__all__ = [
    'to_graphml',
    'to_csv'
]

log = logging.getLogger(__name__)


def to_graphml(graph, file):
    """Writes this graph to GraphML XML file using :func:`networkx.write_graphml`. The .graphml file extension is
    suggested so Cytoscape can recognize it.

    :param BELGraph graph: A BEL graph
    :param file file: A file or file-like object
    """
    g = nx.MultiDiGraph()

    for node, data in graph.nodes(data=True):
        g.add_node(node, json=json.dumps(data))

    for u, v, key, data in graph.edges(data=True, keys=True):
        g.add_edge(u, v, key=key, attr_dict=flatten_dict(data))

    nx.write_graphml(g, file)


def to_csv(graph, file, delimiter='\t', data=True, encoding='utf-8'):
    """Writes the graph as an edge list using :func:`networkx.write_edgelist`

    :param BELGraph graph: A BEL graph
    :param file or str file: File or filename to write. If a file is provided, it must be opened in ‘wb’ mode.
                                Filenames ending in .gz or .bz2 will be compressed.
    :param bool or list data: If False write no edge data. If True write a string representation of the edge data
                                dictionary. If a list (or other iterable) is provided, write the keys specified in
                                the list.
    :param str delimiter: The delimiter to use in output
    :param str encoding: The encoding to write. Defaults to ``utf-8``.
    """
    nx.write_edgelist(flatten_graph_data(graph), file, data=data, delimiter=delimiter, encoding=encoding)


def to_gsea(graph, file):
    """Writes the genes/gene products to a *.grp file for use with GSEA gene set enrichment analysis
    
    :param BELGraph graph: A BEL graph 
    :param file file: A writeable file or file-like object
    """
    print('# {}'.format(graph.name), file=file)
    nodes = {d[NAME] for _, d in graph.nodes_iter(data=True) if NAMESPACE in d and d[NAMESPACE] == 'HGNC'}
    for node in sorted(nodes):
        print(node, file=file)
