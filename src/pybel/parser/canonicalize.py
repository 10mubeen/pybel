from __future__ import print_function

import itertools as itt
import sys
from operator import itemgetter

from pybel.parser import language
from .language import rev_activity_labels
from .utils import ensure_quotes
from ..constants import GOCC_LATEST

# TODO extract from .parse_control
CITATION_ENTRIES = 'type', 'name', 'reference', 'date', 'authors', 'comments'


def write_bel_statement(tokens):
    return "{} {} {}".format(write_bel_term(tokens['subject']),
                             tokens['relation'],
                             write_bel_term(tokens['object']))


def postpend_location(s, location_model):
    """Rips off the closing parentheses and adds canonicalized modification.

    I did this because writing a whole new parsing model for the data would be sad and difficult

    :param s:
    :type s: BEL string representing node
    :param location_model:
    :return:
    """

    if all(k in location_model for k in {'namespace', 'name'}):
        return "loc({}:{})".format(location_model['namespace'], ensure_quotes(location_model['name']))
    raise ValueError('Confused! {}'.format(location_model))


def decanonicalize_edge_node(g, node, edge_data, node_position):
    node_str = decanonicalize_node(g, node)

    if node_position not in edge_data:
        return node_str

    node_edge_data = edge_data[node_position]

    if 'location' in node_edge_data:
        node_str = postpend_location(node_str, node_edge_data['location'])

    if 'modifier' in node_edge_data and 'Degredation' == node_edge_data['modifier']:
        node_str = "deg({})".format(node_str)
    elif 'modifier' in node_edge_data and 'Activity' == node_edge_data['modifier']:
        node_str = "act({}".format(node_str)
        # switch missing, default, and dict
        if 'effect' in node_edge_data and 'MolecularActivity' in node_edge_data['effect']:
            ma = node_edge_data['effect']['MolecularActivity']

            if isinstance(ma, str):
                node_str = "{}, ma({}))".format(node_str, rev_activity_labels[ma])
            elif isinstance(ma, dict):
                node_str = "{}, ma({}:{}))".format(node_str, ma['namespace'], ensure_quotes(ma['name']))
        else:
            node_str = "{})".format(node_str)

    elif 'modifier' in node_edge_data and 'Translocation' == node_edge_data['modifier']:
        fromLoc = "fromLoc("
        toLoc = "toLoc("

        if isinstance(node_edge_data['effect']['fromLoc'], dict):
            fromLoc += "{}:{})".format(node_edge_data['effect']['fromLoc']['namespace'],
                                       ensure_quotes(node_edge_data['effect']['fromLoc']['name']))
        else:
            raise ValueError()

        if isinstance(node_edge_data['effect']['toLoc'], dict):
            toLoc += "{}:{})".format(node_edge_data['effect']['toLoc']['namespace'],
                                     ensure_quotes(node_edge_data['effect']['toLoc']['name']))
        else:
            raise ValueError()

        node_str = "tloc({}, {}, {})".format(node_str, fromLoc, toLoc)

    return node_str


def decanonicalize_edge(g, u, v, k):
    """Takes two nodes and gives back a BEL string representing the statement

    :param g:
    :type g: BELGraph
    :param u:
    :param v:
    :return:
    """

    ed = g.edge[u][v][k]

    u_str = decanonicalize_edge_node(g, u, ed, node_position='subject')
    v_str = decanonicalize_edge_node(g, v, ed, node_position='object')

    return "{} {} {}".format(u_str, ed['relation'], v_str)


blacklist_features = ['relation', 'subject', 'object', 'citation', 'SupportingText']


def flatten_citation(citation):
    return ','.join('"{}"'.format(citation[x]) for x in CITATION_ENTRIES[:len(citation)])


def sort_edges(d):
    return (flatten_citation(d['citation']), d['SupportingText']) + tuple(
        itt.chain.from_iterable((k, v) for k, v in sorted(d.items(), key=itemgetter(0)) if k not in blacklist_features))


def decanonicalize_graph(g, file=sys.stdout):
    for k in sorted(g.document):
        print('SET DOCUMENT {} = "{}"'.format(k, g.document[k]), file=file)

    print('###############################################\n', file=file)

    if 'GOCC' not in g.namespace_url:
        g.namespace_url['GOCC'] = GOCC_LATEST

    for namespace, url in sorted(g.namespace_url.items(), key=itemgetter(0)):
        print('DEFINE NAMESPACE {} AS URL "{}"'.format(namespace, url), file=file)

    for namespace, url in sorted(g.namespace_owl.items(), key=itemgetter(0)):
        print('DEFINE NAMESPACE {} AS OWL "{}"'.format(namespace, url), file=file)

    for namespace, ns_list in sorted(g.namespace_list.items(), key=itemgetter(0)):
        ns_list_str = ', '.join('"{}"'.format(e) for e in ns_list)
        print('DEFINE NAMESPACE {} AS LIST {{{}}}'.format(namespace, ns_list_str), file=file)

    print('###############################################\n', file=file)

    for annotation, url in sorted(g.annotation_url.items(), key=itemgetter(0)):
        print('DEFINE ANNOTATION {} AS URL "{}"'.format(annotation, url), file=file)

    for annotation, an_list in sorted(g.annotation_list.items(), key=itemgetter(0)):
        an_list_str = ', '.join('"{}"'.format(e) for e in an_list)
        print('DEFINE ANNOTATION {} AS LIST {{{}}}'.format(annotation, an_list_str), file=file)

    print('###############################################\n', file=file)

    # sort by citation, then supporting text
    qualified_edges = filter(lambda u_v_k_d: 'citation' in u_v_k_d[3] and 'SupportingText' in u_v_k_d[3],
                             g.edges_iter(data=True, keys=True))
    qualified_edges = sorted(qualified_edges, key=lambda u_v_k_d: sort_edges(u_v_k_d[3]))

    for citation, citation_edges in itt.groupby(qualified_edges,
                                                key=lambda u_v_k_d: flatten_citation(u_v_k_d[3]['citation'])):
        print('SET Citation = {{{}}}'.format(citation), file=file)

        for evidence, evidence_edges in itt.groupby(citation_edges, key=lambda u_v_k_d: u_v_k_d[3]['SupportingText']):
            print('SET SupportingText = "{}"'.format(evidence), file=file)

            for u, v, k, d in evidence_edges:
                for dk in sorted(d):
                    if dk in blacklist_features:
                        continue
                    print('SET {} = "{}"'.format(dk, d[dk]), file=file)
                print(decanonicalize_edge(g, u, v, k), file=file)
            print('UNSET SupportingText', file=file)
        print('\n', file=file)


def write_variant(tokens):
    if isinstance(tokens, dict):
        if {'identifier', 'code', 'pos'} <= set(tokens):
            return 'pmod({}, {}, {})'.format(tokens['identifier'], tokens['code'], tokens['pos'])
        elif {'identifier', 'code'} <= set(tokens):
            return 'pmod({}, {})'.format(tokens['identifier'], tokens['code'])
        elif 'identifier' in tokens:
            return 'pmod({})'.format(tokens['identifier'])
        else:
            raise NotImplementedError('prob with {}'.format(tokens))

    elif tokens[0] == 'Variant':
        return 'var({})'.format(''.join(str(token) for token in tokens[1:]))
    elif tokens[0] == 'ProteinModification':
        return 'pmod({})'.format(','.join(tokens[1:]))
    elif tokens[0] == 'Fragment':
        r = '?' if 'missing' in tokens else '{}_{}'.format(tokens['start'], tokens['stop'])
        return 'frag({}, {})'.format(r, tokens['description']) if 'description' in tokens else 'frag({})'.format(r)
    else:
        raise NotImplementedError('prob with :{}'.format(tokens))


def write_bel_term(tokens):
    if 'function' in tokens and 'variants' in tokens:
        variants = ', '.join(write_variant(var) for var in tokens['variants'])
        return "{}({}:{}, {})".format(language.rev_abundance_labels[tokens['function']],
                                      tokens['identifier']['namespace'],
                                      ensure_quotes(tokens['identifier']['name']),
                                      variants)

    elif 'function' in tokens and 'members' in tokens:
        return '{}({})'.format(language.rev_abundance_labels[tokens['function']],
                               ', '.join(sorted(write_bel_term(member) for member in tokens['members'])))

    elif 'transformation' in tokens and 'Reaction' == tokens['transformation']:
        reactants = sorted(write_bel_term(reactant) for reactant in tokens['reactants'])
        products = sorted(write_bel_term(product) for product in tokens['products'])
        return 'rxn(reactants({}), products({}))'.format(", ".join(reactants), ", ".join(products))

    elif 'function' in tokens and tokens['function'] in ('Gene', 'RNA', 'Protein') and 'fusion' in tokens:
        f = tokens['fusion']
        return '{}(fus({}:{}, r.{}, {}:{}, r.{}))'.format(
            language.rev_abundance_labels[tokens['function']],
            f['partner_5p']['namespace'],
            f['partner_5p']['name'],
            f['range_5p'],
            f['partner_3p']['namespace'],
            f['partner_3p']['name'],
            tokens['fusion']['range_3p']
        )

    elif 'function' in tokens and tokens['function'] in ('Gene', 'RNA', 'miRNA', 'Protein', 'Abundance', 'Complex', 'Pathology', 'BiologicalProcess'):
        if 'identifier' in tokens:
            return '{}({}:{})'.format(language.rev_abundance_labels[tokens['function']],
                                      tokens['identifier']['namespace'],
                                      ensure_quotes(tokens['identifier']['name']))


def get_neighbors_by_path_type(g, v, relation):
    result = []
    for neighbor in g.edge[v]:
        for data in g.edge[v][neighbor].values():
            if data['relation'] == relation:
                result.append(neighbor)
    return set(result)

def decanonicalize_variant(tokens):
    if tokens[0] == 'ProteinModification':
        return 'pmod({})'.format(', '.join(tokens[1:]))
    elif tokens[0] == 'Variant':
        return 'var({})'.format(''.join(tokens[1:]))
    elif tokens[0] == 'Fragment':
        r = '?' if 'missing' in tokens else '{}_{}'.format(tokens['start'], tokens['stop'])
        return 'frag({}, {})'.format(r, tokens['description']) if 'description' in tokens else 'frag({})'.format(r)
    else:
        raise NotImplementedError('prob with :{}'.format(tokens))

def decanonicalize_node(g, v):
    """Returns a node from a graph as a BEL string
    """
    tokens = g.node[v]
    if tokens['function'] == 'Reaction':
        reactants = get_neighbors_by_path_type(g, v, 'hasReactant')
        reactants_canon = map(lambda n: decanonicalize_node(g, n), reactants)
        products = get_neighbors_by_path_type(g, v, 'hasProduct')
        products_canon = map(lambda n: decanonicalize_node(g, n), products)
        return 'rxn(reactants({}), products({}))'.format(', '.join(reactants_canon), ', '.join(products_canon))
    elif 'members' in tokens:
        members = get_neighbors_by_path_type(g, v, 'hasComponent')
        members_canon = map(lambda n: decanonicalize_node(g, n), members)
        return '{}({})'.format(language.rev_abundance_labels[tokens['function']], ', '.join(members_canon))

    if 'function' in tokens and 'variants' in tokens:
        variants = ', '.join(map(decanonicalize_variant, tokens['variants']))
        return "{}({}:{}, {})".format(language.rev_abundance_labels[tokens['function']],
                                      tokens['identifier']['namespace'],
                                      ensure_quotes(tokens['identifier']['name']),
                                      variants)