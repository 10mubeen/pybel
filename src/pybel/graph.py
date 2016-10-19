import json
import logging
import os
import sys
import time

import networkx as nx
import py2neo
import requests
from networkx.readwrite import json_graph
from pyparsing import ParseException
from requests_file import FileAdapter

from .exceptions import PyBelError
from .parser.parse_bel import BelParser
from pybel.exceptions import PyBelWarning
from .parser.parse_metadata import MetadataParser
from .parser.utils import split_file_to_annotations_and_definitions, flatten, flatten_edges

log = logging.getLogger('pybel')


def from_lines(it, lenient=False):
    """Loads BEL graph from an iterable of strings or file-like object

    :param it: an iterable of strings
    :return: a parsed BEL graph
    :rtype: BELGraph"""
    return BELGraph(lenient=lenient).parse_from_lines(it)


def from_url(url, lenient=False):
    """Loads a BEL graph from a URL resource

    :param url: a valid URL string
    :type url: str
    :return: a parsed BEL graph
    :rtype: BELGraph
    """
    log.info('Loading from url: {}'.format(url))
    return BELGraph(lenient=lenient).parse_from_url(url)


def from_path(path, lenient=False):
    """Loads a BEL graph from a file resource

    :param bel: a file path
    :type bel: str
    :return: a parsed BEL graph
    :rtype: BELGraph"""

    log.info('Loading from path: {}'.format(path))
    with open(os.path.expanduser(path)) as f:
        return from_lines(f, lenient=lenient)


def from_database(connection):
    """Loads a BEL graph from a database

    :param connection: The string form of the URL is dialect[+driver]://user:password@host/dbname[?key=value..], where dialect is a database name such as mysql, oracle, postgresql, etc., and driver the name of a DBAPI, such as psycopg2, pyodbc, cx_oracle, etc. Alternatively, the URL can be an instance of URL.
    :type connection: str
    :return: a BEL graph loaded from the database
    :rtype: BELGraph
    """
    raise NotImplementedError('Loading from database not yet implemented')


class BELGraph(nx.MultiDiGraph):
    """An extension of a NetworkX MultiDiGraph to hold a BEL graph."""

    def __init__(self, context=None, lenient=False, *attrs, **kwargs):
        """An extension of a NetworkX MultiDiGraph for holding BEL data

        :param context: disease context string
        :type context: str
        :param lenient: if true, allow naked namespaces
        :type lenient: bool
        """
        nx.MultiDiGraph.__init__(self, *attrs, **kwargs)

        self.bel_parser = None
        self.metadata_parser = None
        self.context = context
        self.lenient = lenient

    def clear(self):
        """Clears the content of the graph and its BEL parser"""
        self.bel_parser.clear()

    def parse_from_path(self, path):
        """Opens a BEL file from a given path and parses it

        :param path: path to BEL file
        :return: self
        :rtype: BELGraph
        """
        with open(os.path.expanduser(path)) as f:
            return self.parse_from_lines(f)

    def parse_from_url(self, url):
        """Parses a BEL file from URL resource and adds to graph

        :param url: URL to BEL Resource
        :return: self
        :rtype: BELGraph
        """

        session = requests.session()
        if url.startswith('file://'):
            session.mount('file://', FileAdapter())
        response = session.get(url)
        response.raise_for_status()

        return self.parse_from_lines(line.decode('utf-8') for line in response.iter_lines())

    def parse_from_lines(self, fl):
        """Parses a BEL file from an iterable of strings. This can be a file, file-like, or list of strings.

        :param fl: iterable over lines of BEL data file
        :return: self
        :rtype: BELGraph
        """
        t = time.time()

        docs, defs, states = split_file_to_annotations_and_definitions(fl)

        self.metadata_parser = MetadataParser()
        for line_number, line in docs:
            try:
                self.metadata_parser.parseString(line)
            except:
                log.error('Line {:07} - failed: {}'.format(line_number, line))

        log.info('Finished parsing document section in {:.02f} seconds'.format(time.time() - t))
        t = time.time()

        for line_number, line in defs:
            try:
                self.metadata_parser.parseString(line)
            except PyBelError as e:
                log.critical('Line {:07} - {}'.format(line_number, line))
                raise e
            except ParseException as e:
                log.error('Line {:07} - invalid statement: {}'.format(line_number, line))
            except PyBelWarning as e:
                log.warning('Line {:07} - {}: {}'.format(line_number, e, line))
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                log.error('Line {:07} - general failure: {} - {}: {}'.format(line_number, line, exc_type, exc_value))
                log.debug('Traceback: {}'.format(exc_traceback))

        log.info('Finished parsing definitions section in {:.02f} seconds'.format(time.time() - t))
        t = time.time()

        self.bel_parser = BelParser(graph=self,
                                    valid_namespaces=self.metadata_parser.namespace_dict,
                                    valid_annotations=self.metadata_parser.annotations_dict,
                                    lenient=self.lenient)

        for line_number, line in states:
            try:
                self.bel_parser.parseString(line)
            except PyBelError as e:
                log.critical('Line {:07} - {}'.format(line_number, line))
                raise e
            except ParseException as e:
                log.error('Line {:07} - general parser failure: {}'.format(line_number, line))
            except PyBelWarning as e:
                log.debug('Line {:07} - {}'.format(line_number, e, line))
            except:
                log.error('Line {:07} - general failure: {}'.format(line_number, line))

        log.info('Finished parsing statements section in {:.02f} seconds'.format(time.time() - t))

        return self

    def to_neo4j(self, neo_graph, context=None):
        """Uploads to Neo4J graph database usiny `py2neo`

        :param neo_graph:
        :type neo_graph: py2neo.Graph
        :param context: a disease context to allow for multiple disease models in one neo4j instance
        :type context: str
        """

        if context is not None:
            self.context = context

        node_map = {}
        for i, (node, data) in enumerate(self.nodes(data=True)):
            node_type = data['type']
            attrs = {k: v for k, v in data.items() if k not in ('type', 'name')}

            if 'name' in data:
                attrs['value'] = data['name']

            node_map[node] = py2neo.Node(node_type, name=str(i), **attrs)

        relationships = []
        for u, v, data in self.edges(data=True):
            neo_u = node_map[u]
            neo_v = node_map[v]
            rel_type = data['relation']
            attrs = flatten(data)
            if self.context is not None:
                attrs['pybel_context'] = str(self.context)
            rel = py2neo.Relationship(neo_u, rel_type, neo_v, **attrs)
            relationships.append(rel)

        tx = neo_graph.begin()
        for neo_node in node_map.values():
            tx.create(neo_node)

        for rel in relationships:
            tx.create(rel)
        tx.commit()

    def to_pickle(self, output):
        """Writes this graph to a pickle object with nx.write_gpickle

        :param output: a file or filename to write to
        """
        nx.write_gpickle(flatten_edges(self), output)

    def to_json(self, output):
        """Writes this graph to a node-link JSON object

        :param output: a write-supporting filelike object
        """
        data = json_graph.node_link_data(flatten_edges(self))
        json.dump(data, output, ensure_ascii=False)

    def to_graphml(self, output):
        """Writes this graph to GraphML file. Use .graphml extension so Cytoscape can recognize it

        :param output: a file or filelike object
        """
        nx.write_graphml(flatten_edges(self), output)

    def to_csv(self, output):
        """Writes graph to edge list csv

        :param output: a file or filelike object
        """

        nx.write_edgelist(flatten_edges(self), output, data=True)
