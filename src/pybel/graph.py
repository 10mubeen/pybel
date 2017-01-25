# -*- coding: utf-8 -*-

import logging
import time
from collections import defaultdict, Counter

import networkx as nx
from pyparsing import ParseException

from .constants import FUNCTION, NAMESPACE
from .exceptions import PyBelWarning
from .manager.cache import CacheManager
from .parser import language
from .parser.parse_bel import BelParser
from .parser.parse_exceptions import MissingMetadataException
from .parser.parse_metadata import MetadataParser
from .parser.utils import split_file_to_annotations_and_definitions, subdict_matches
from .utils import expand_dict

try:
    import cPickle as pickle
except ImportError:
    import pickle

__all__ = ['BELGraph']

log = logging.getLogger('pybel')

REQUIRED_METADATA = [
    'name',
    'version',
    'description',
    'authors',
    'contact'
]


def build_metadata_parser(cache_manager):
    if isinstance(cache_manager, CacheManager):
        return MetadataParser(cache_manager)
    elif isinstance(cache_manager, str):
        return MetadataParser(CacheManager(connection=cache_manager))
    else:
        return MetadataParser(CacheManager())


class BELGraph(nx.MultiDiGraph):
    """An extension of a NetworkX MultiDiGraph to hold a BEL graph."""

    def __init__(self, lines=None, complete_origin=False, cache_manager=None, allow_naked_names=False,
                 allow_nested=False, *attrs, **kwargs):
        """Parses a BEL file from an iterable of strings. This can be a file, file-like, or list of strings.

        :param lines: iterable over lines of BEL data file
        :param cache_manager: database connection string to cache, pre-built cache manager,
                    or True to use the default
        :type cache_manager: str or pybel.manager.CacheManager
        :param log_stream: a stream to write debug logging to
        :param allow_naked_names: if true, turn off naked namespace failures
        :type allow_naked_names: bool
        :param allow_nested: if true, turn off nested statement failures
        :type allow_nested: bool
        :param \*attrs: arguments to pass to :py:meth:`networkx.MultiDiGraph`
        :param \**kwargs: keyword arguments to pass to :py:meth:`networkx.MultiDiGraph`
        """
        nx.MultiDiGraph.__init__(self, *attrs, **kwargs)

        self.metadata_parser = None
        self.bel_parser = None
        self.warnings = []

        if lines is not None:
            self.parse_lines(lines, complete_origin=complete_origin, cache_manager=cache_manager,
                             allow_naked_names=allow_naked_names, allow_nested=allow_nested)

    def parse_lines(self, lines, cache_manager=None,complete_origin=False,
                    allow_naked_names=False, allow_nested=False):
        """Parses an iterable of lines into this graph

        :param lines: iterable over lines of BEL data file
        :param cache_manager: database connection string to cache or pre-built namespace namspace_cache manager
        :type cache_manager: str or :class:`pybel.manager.cache.CacheManager`
        :param complete_origin: add corresponding DNA and RNA entities for all proteins
        :type complete_origin: bool
        :param allow_naked_names: if true, turn off naked namespace failures
        :type allow_naked_names: bool
        :param allow_nested: if true, turn off nested statement failures
        :type allow_nested: bool
        """

        docs, definitions, states = split_file_to_annotations_and_definitions(lines)

        self.metadata_parser = build_metadata_parser(cache_manager)

        self.parse_document(docs)

        self.parse_definitions(definitions)

        self.bel_parser = BelParser(
            graph=self,
            valid_namespaces=self.metadata_parser.namespace_dict,
            valid_annotations=self.metadata_parser.annotations_dict,
            complete_origin=complete_origin,
            allow_naked_names=allow_naked_names,
            allow_nested=allow_nested
        )

        self.streamline()

        self.parse_statements(states)

        log.info('Network has %d nodes and %d edges', self.number_of_nodes(), self.number_of_edges())

        counter = defaultdict(lambda: defaultdict(int))

        for n, d in self.nodes_iter(data=True):
            counter[d[FUNCTION]][d[NAMESPACE] if NAMESPACE in d else 'DEFAULT'] += 1

        for fn, nss in sorted(counter.items()):
            log.debug(' %s: %d', fn, sum(nss.values()))
            for ns, count in sorted(nss.items()):
                log.debug('   %s: %d', ns, count)

    def parse_document(self, document_metadata):
        t = time.time()

        for line_number, line in document_metadata:
            try:
                self.metadata_parser.parseString(line)
            except Exception as e:
                log.error('Line %07d - Critical Failure - %s', line_number, line)
                raise e

        for required in REQUIRED_METADATA:
            if required not in self.metadata_parser.document_metadata:
                self.warnings.append((0, '', MissingMetadataException(language.inv_document_keys[required])))
                log.error('Missing required document metadata: %s', language.inv_document_keys[required])
            elif not self.metadata_parser.document_metadata[required]:
                self.warnings.append((0, '', MissingMetadataException(language.inv_document_keys[required])))
                log.error('Missing required document metadata not filled: %s', language.inv_document_keys[required])

        self.graph['document_metadata'] = self.metadata_parser.document_metadata

        log.info('Finished parsing document section in %.02f seconds', time.time() - t)

    def parse_definitions(self, definitions):
        t = time.time()

        for line_number, line in definitions:
            try:
                self.metadata_parser.parseString(line)
            except Exception as e:
                log.exception('Line %07d - Critical Failure - %s', line_number, line)
                raise e

        self.graph['namespace_owl'] = self.metadata_parser.namespace_owl_dict
        self.graph['namespace_url'] = self.metadata_parser.namespace_url_dict
        self.graph['annotation_url'] = self.metadata_parser.annotation_url_dict
        self.graph['annotation_list'] = {e: self.metadata_parser.annotations_dict[e] for e in
                                         self.metadata_parser.annotation_list_list}

        log.info('Finished parsing definitions section in %.02f seconds', time.time() - t)

    def streamline(self):
        t = time.time()
        self.bel_parser.language.streamline()
        log.info('Finished streamlining BEL parser in %.02fs', time.time() - t)

    def parse_statements(self, statements):
        t = time.time()

        for line_number, line in statements:
            try:
                self.bel_parser.parseString(line)
            except ParseException as e:
                log.error('Line %07d - general parser failure: %s', line_number, line)
                self.warnings.append((line_number, line, e))
            except PyBelWarning as e:
                log.warning('Line %07d - %s', line_number, e)
                self.warnings.append((line_number, line, e))
            except Exception as e:
                log.exception('Line %07d - general failure: %s - %s: %s', line_number, line)
                self.warnings.append((line_number, line, e))

        log.info('Parsed statements section in %.02f seconds with %d warnings', time.time() - t, len(self.warnings))

        for k, v in sorted(Counter(e.__class__.__name__ for _, _, e in self.warnings).items(), reverse=True):
            log.debug('  %s: %d', k, v)

    def edges_iter(self, nbunch=None, data=False, keys=False, default=None, **kwargs):
        """Allows for filtering by checking keyword arguments are a subdictionary of each edges' data.
            See :py:meth:`networkx.MultiDiGraph.edges_iter`"""
        for u, v, k, d in nx.MultiDiGraph.edges_iter(self, nbunch=nbunch, data=True, keys=True, default=default):
            if not subdict_matches(d, kwargs):
                continue
            elif keys and data:
                yield u, v, k, d
            elif data:
                yield u, v, d
            elif keys:
                yield u, v, k
            else:
                yield u, v

    def nodes_iter(self, data=False, **kwargs):
        """Allows for filtering by checking keyword arguments are a subdictionary of each nodes' data.
            See :py:meth:`networkx.MultiDiGraph.edges_iter`"""
        for n, d in nx.MultiDiGraph.nodes_iter(self, data=True):
            if not subdict_matches(d, kwargs):
                continue
            elif data:
                yield n, d
            else:
                yield n

    @property
    def document(self):
        """A dictionary holding the metadata from the "Document" section of the BEL script. All keys are normalized
        according to :py:data:`pybel.parser.language.document_keys`

        :return: metadata derived from the BEL "Document" section
        :rtype: dict
        """
        return self.graph['document_metadata']

    @property
    def namespace_url(self):
        """A dictionary mapping the keywords used in the creation of this graph to the URLs of the BELNS file"""
        return self.graph['namespace_url']

    @property
    def namespace_owl(self):
        """A dictionary mapping the keywords used in the creation of this graph to the URLs of the OWL file"""
        return self.graph['namespace_owl']

    @property
    def annotation_url(self):
        """A dictionary mapping the keywords used in the creation of this graph to the URLs of the BELANNO file"""
        return self.graph['annotation_url']

    @property
    def annotation_list(self):
        """A dictionary mapping the keyword of locally defined annotations to a set of their values"""
        return self.graph['annotation_list']


def expand_edges(graph):
    """Returns a new graph with expanded edge data dictionaries

    :param graph: nx.MultiDiGraph
    :type graph: BELGraph
    :rtype: BELGraph
    """
    g = BELGraph()

    for node, data in graph.nodes(data=True):
        g.add_node(node, data)

    for u, v, key, data in graph.edges(data=True, keys=True):
        g.add_edge(u, v, key=key, attr_dict=expand_dict(data))

    return g
