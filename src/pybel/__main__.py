import os

import click
import json
import networkx as nx
from py2neo import authenticate, Graph

from .graph import from_url, from_file


@click.group(help="PyBEL Command Line Utilities")
def cli():
    pass


def get_from_url_or_path(url=None, path=None):
    if url is not None:
        return from_url(url)
    elif path is not None:
        with open(os.path.expanduser(path)) as f:
            return from_file(f)
    raise ValueError('Missing both url and path arguments')


@cli.command()
@click.option('--url')
@click.option('--path')
@click.option('--neo-url', default='localhost')
@click.option('--neo-port', type=int, default=7474)
@click.option('--neo-user', default='neo4j')
@click.option('--neo-pass', default='neo4j')
def to_neo(url, path, neo_url, neo_port, neo_user, neo_pass):
    """Parses BEL file and uploads to Neo4J"""
    g = get_from_url_or_path(url, path)

    authenticate('{}:{}'.format(neo_url, neo_port), neo_user, neo_pass)
    p2n = Graph()

    g.to_neo4j(p2n)


@cli.command()
@click.option('--url')
@click.option('--path')
@click.option('--node-path')
@click.option('--edge-path')
def to_csv(url, path, node_path, edge_path):
    """Parses BEL file and exports as node/edge list files"""
    g = get_from_url_or_path(url, path)
    nx.write_edgelist(g, edge_path, data=True)

    with open(node_path, 'w') as f:
        json.dump(g.nodes(data=True), f)


if __name__ == '__main__':
    cli()
