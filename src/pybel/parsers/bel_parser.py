#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

import networkx as nx
from pyparsing import *

from . import language
from .hgvs_parser import hgvs, nucleotides
from .utils import list2tuple

log = logging.getLogger(__name__)

WS = Suppress(ZeroOrMore(White()))
LP = Suppress('(') + WS
RP = WS + Suppress(')')
CM = Suppress(',')
WCW = WS + CM + WS

# TODO rename this
d = {
    'GeneVariant': 'Gene',
    'RNAVariant': 'RNA',
    'ProteinVariant': 'Protein'
}


def command_rename_handler(command, loc=0):
    def handler(s, l, tokens):
        tokens[loc] = command
        return tokens

    return handler


class Parser:
    """
    Build a parser backed by a given dictionary of namespaces
    """

    def __init__(self, graph=None, annotations=None, namespaces=None, namespace_mapping=None, names=None):
        """
        :param namespaces: A dictionary of {namespace: set of members}
        :param annotations: initial annotation dictionary, containing BEL data like evidence, pathway, etc.
        :param graph: the graph to put the network in. Constructs new nx.MultiDiGrap if None
        :type graph: nx.MultiDiGraph
        :param namespace_mapping: a dict of {name: {value: (other_name, other_value)}}
        :param names: a list of valid, un-spaced names
        :type names: list
        """
        self.namespaces = namespaces
        self.namespace_mapping = namespace_mapping
        self.graph = graph if graph is not None else nx.MultiDiGraph()
        self.annotations = annotations if annotations is not None else {}
        self.names = names

        self.node_count = 0
        self.node_to_id = {}
        self.id_to_node = {}

        quoted_value = dblQuotedString().setParseAction(removeQuotes)

        ns_val = (Word(alphanums) + Suppress(':') + (Word(alphanums) | quoted_value))

        # TODO test listed namespace
        # TODO deal with quoted values
        if names is not None:
            blank_ns = oneOf(names).setParseAction(lambda s, l, tokens: ['', tokens[0]])
            ns_val = ns_val | blank_ns

        ns_val.setParseAction(self.validate_ns_pair)

        # 2.2 Abundance Modifier Functions

        # 2.2.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_protein_modifications
        aa_single = oneOf(language.amino_acid_dict)
        aa_triple = oneOf(language.amino_acid_dict.values())
        amino_acids = aa_triple | aa_single

        pmod_tag = oneOf(['pmod', 'proteinModification'])
        pmod_default = oneOf(language.pmod_namespace) | oneOf(language.pmod_legacy)

        pmod_val = Group(ns_val) | pmod_default

        pmod_option_1 = pmod_tag + LP + pmod_val + WCW + amino_acids + WCW + pyparsing_common.integer() + RP
        pmod_option_2 = pmod_tag + LP + pmod_val + WCW + amino_acids + RP
        pmod_option_3 = pmod_tag + LP + pmod_val + RP

        pmod = pmod_option_1 | pmod_option_2 | pmod_option_3

        self.pmod = pmod

        def handle_pmod(s, l, tokens):
            tokens[0] = 'ProteinModification'
            return tokens

        pmod.setParseAction(handle_pmod)

        # 2.2.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_variant_var
        # TODO see spec at http://www.hgvs.org/mutnomen/recs.html
        variant_tags = ['var', 'variant']
        variant = oneOf(variant_tags) + LP + hgvs + RP

        def handle_variant(s, loc, tokens):
            tokens[0] = 'Variant'
            return tokens

        variant.setParseAction(handle_variant)

        # 2.2.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_proteolytic_fragments
        fragment_range = (pyparsing_common.integer() | '?') + Suppress('_') + (pyparsing_common.integer() | '?' | '*')
        fragment_tags = ['frag', 'fragment']
        fragment_1 = oneOf(fragment_tags) + LP + fragment_range + WCW + Word(alphanums) + RP
        fragment_2 = oneOf(fragment_tags) + LP + fragment_range + RP
        fragment_3 = oneOf(fragment_tags) + LP + '?' + Optional(WCW + Word(alphanums)) + RP

        fragment = fragment_3 | fragment_1 | fragment_2

        def handle_fragment(s, l, tokens):
            tokens[0] = 'Fragment'
            return tokens

        fragment.setParseAction(handle_fragment)

        # 2.2.4 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_cellular_location
        location_tags = ['loc', 'location']
        location = oneOf(location_tags) + LP + Group(ns_val) + RP

        def handle_location(s, l, tokens):
            tokens[0] = 'Location'
            return tokens

        location.setParseAction(handle_location)

        # deprecated substitution function
        sub_tags = ['sub', 'substitution']
        psub = oneOf(sub_tags) + LP + amino_acids + WCW + pyparsing_common.integer() + WCW + amino_acids + RP

        def handle_psub(s, l, tokens):
            tokens[0] = 'Variant'
            log.debug('PyBEL006 deprecated protein substitution function. User variant() instead. {}'.format(s))
            return tokens

        psub.setParseAction(handle_psub)
        self.psub = psub

        gsub = oneOf(sub_tags) + LP + nucleotides + WCW + pyparsing_common.integer() + WCW + nucleotides + RP

        def handle_gsub(s, l, tokens):
            log.debug('PyBEL009 old SNP annotation. Use variant() instead: {}'.format(s))
            tokens[0] = 'Variant'
            return tokens

        gsub.setParseAction(handle_gsub)

        # 2.6 Other Functions

        # 2.6.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_fusion_fus

        # sequence coordinates?
        range_coordinate = Group(oneOf(['r', 'p']) + Suppress('.') + pyparsing_common.integer() + Suppress(
            '_') + pyparsing_common.integer()) | '?'

        fusion_tags = ['fus', 'fusion']
        fusion = oneOf(fusion_tags) + LP + Group(ns_val) + WCW + range_coordinate + WCW + Group(
            ns_val) + WCW + range_coordinate + RP

        def handle_fusion(s, l, tokens):
            tokens[0] = 'Fusion'
            return tokens

        fusion.setParseAction(handle_fusion)

        # 2.1 Abundance Functions

        # 2.1.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XcomplexA
        general_abundance_tags = ['a', 'abundance']
        general_abundance = oneOf(general_abundance_tags) + LP + Group(ns_val) + RP

        def handle_general_abundance(s, l, tokens):
            cls = tokens[0] = 'Abundance'
            ns, val = tokens[1]
            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, type=cls, namespace=ns, value=val)
            return tokens

        general_abundance.addParseAction(handle_general_abundance)

        # 2.1.4 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XgeneA
        gene_tags = ['g', 'geneAbundance']

        gene_simple = oneOf(gene_tags) + LP + Group(ns_val) + Optional(WCW + Group(location)) + RP

        def handle_gene_simple(s, location, tokens):
            cls = tokens[0] = 'Gene'
            ns, val = tokens[1]

            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, type=cls, namespace=ns, value=val)

            return tokens

        gene_simple.addParseAction(handle_gene_simple)

        gene_modified = oneOf(gene_tags) + LP + Group(ns_val) + OneOrMore(WCW + Group(variant | gsub)) + Optional(
            WCW + Group(location)) + RP

        def handle_gene_modified(s, l, tokens):
            cls = tokens[0] = 'GeneVariant'
            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, type=cls)

            gcls = 'Gene'
            gns, gval = tokens[1]
            gname = gcls, gns, gval
            if gname not in self.graph:
                self.graph.add_node(gname, type=gcls)

            self.graph.add_edge(name, gname)

            return tokens

        gene_modified.setParseAction(handle_gene_modified)

        gene_fusion = oneOf(gene_tags) + LP + Group(fusion) + Optional(WCW + Group(location)) + RP

        def handle_gene_fusion(s, l, tokens):
            cls = tokens[0] = 'GeneFusion'

            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, type=cls)

            return tokens

        gene_fusion.setParseAction(handle_gene_fusion)

        gene = gene_modified | gene_simple | gene_fusion

        # 2.1.5 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XmicroRNAA
        mirna_tags = ['m', 'microRNAAbundance']
        mirna_simple = oneOf(mirna_tags) + LP + Group(ns_val) + Optional(WCW + Group(location)) + RP

        def handle_mirna_simple(s, l, tokens):
            cls = tokens[0] = 'miRNA'
            ns, val = tokens[1]
            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, type=cls, namespace=ns, value=val)
            return tokens

        mirna_simple.setParseAction(handle_mirna_simple)

        mirna_modified = oneOf(mirna_tags) + LP + ns_val + OneOrMore(WCW + variant) + Optional(WCW + location) + RP

        def handle_mirna_modified(s, l, tokens):
            cls = tokens[0] = 'miRNAVariant'
            # TODO fill this in
            return tokens

        mirna_modified.setParseAction(handle_mirna_modified)

        mirna = mirna_modified | mirna_simple

        # 2.1.6 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XproteinA
        protein_tag = oneOf(['p', 'proteinAbundance'])
        protein_simple = protein_tag + LP + Group(ns_val) + Optional(WCW + Group(location)) + RP

        def handle_protein_simple(s, l, tokens):
            cls = tokens[0] = 'Protein'
            ns, val = tokens[1]
            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, type=cls, namespace=ns, value=val)
            return tokens

        protein_simple.setParseAction(handle_protein_simple)

        protein_modified = protein_tag + LP + Group(ns_val) + OneOrMore(
            WCW + Group(pmod | variant | fragment | psub)) + Optional(WCW + Group(location)) + RP

        def handle_protein_modified(s, l, tokens):
            cls = tokens[0] = 'ProteinVariant'

            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, type=cls)

            pcls = 'Protein'
            pns, pval = tokens[1]
            pname = pcls, pns, pval
            if pname not in self.graph:
                self.graph.add_node(pname, type=pcls, namespace=pns, value=pval)

            self.graph.add_edge(name, pname)

            return tokens

        protein_modified.setParseAction(handle_protein_modified)

        protein_fusion = protein_tag + LP + Group(fusion) + Optional(WCW + Group(location)) + RP

        def handle_protein_fusion(s, l, tokens):
            cls = tokens[0] = 'ProteinFusion'
            return tokens

        protein_fusion.setParseAction(handle_protein_fusion)

        protein = protein_modified | protein_simple | protein_fusion

        # 2.1.7 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XrnaA
        rna_tags = ['r', 'rnaAbundance']
        rna_simple = oneOf(rna_tags) + LP + Group(ns_val) + Optional(WCW + Group(location)) + RP

        def handle_rna_simple(s, l, tokens):
            cls = tokens[0] = 'RNA'
            ns, val = tokens[1]
            name = self.canonicalize_node(tokens)

            if name not in self.graph:
                self.graph.add_node(name, type=cls, namespace=ns, value=val)

            return tokens

        rna_simple.setParseAction(handle_rna_simple)

        rna_modified = oneOf(rna_tags) + LP + Group(ns_val) + OneOrMore(WCW + Group(variant)) + Optional(
            WCW + Group(location)) + RP

        def handle_rna_modified(s, l, tokens):
            cls = tokens[0] = 'RNAVariant'

            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, type=cls)

            rcls = 'RNA'
            rns, rval = tokens[1]
            rname = rcls, rns, rval
            if name not in self.graph:
                self.graph.add_node(rname, type=cls, namespace=rns, value=rval)

            self.graph.add_edge(name, rname)

            return tokens

        rna_modified.setParseAction(handle_rna_modified)

        rna_fusion = oneOf(rna_tags) + LP + Group(fusion) + Optional(WCW + Group(location)) + RP

        def handle_rna_fusion(s, l, tokens):
            tokens[0] = 'RNA'
            return tokens

        rna_fusion.setParseAction(handle_rna_fusion)

        rna = rna_modified | rna_simple | rna_fusion

        single_abundance = general_abundance | gene | mirna | protein | rna

        # 2.1.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XcomplexA
        complex_tags = ['complex', 'complexAbundance']
        complex_singleton_1 = oneOf(complex_tags) + LP + Group(ns_val) + RP

        def handle_complex_singleton_1(s, l, tokens):
            cls = tokens[0] = 'Complex'
            ns, val = tokens[1]
            n = self.canonicalize_node(tokens)
            if n not in self.graph:
                self.graph.add_node(n, type=cls, namespace=ns, value=val)
            return tokens

        complex_singleton_1.setParseAction(handle_complex_singleton_1)

        complex_singleton_2 = oneOf(complex_tags) + LP + ns_val + WCW + location + RP

        complex_partial = single_abundance | complex_singleton_1 | complex_singleton_2

        complex_list_1 = oneOf(complex_tags) + LP + Group(complex_partial) + OneOrMore(
            WCW + Group(complex_partial)) + RP

        def handle_complex_list_1(s, l, tokens):
            cls = tokens[0] = 'ComplexList'

            name = self.canonicalize_node(tokens)

            if name not in self.graph:
                self.graph.add_node(name, type=cls)

            for token in tokens[1:]:
                v_name = self.canonicalize_node(token)
                self.graph.add_edge(name, v_name, relation='hasComponent', attr_dict=self.annotations.copy())

            return tokens

        complex_list_1.setParseAction(handle_complex_list_1)

        complex_list_2 = oneOf(complex_tags) + LP + Group(complex_partial) + OneOrMore(
            WCW + Group(complex_partial)) + WCW + location + RP

        complex_abundances = complex_list_2 | complex_list_1 | complex_singleton_2 | complex_singleton_1

        simple_abundance = complex_abundances | single_abundance

        # 2.1.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XcompositeA
        composite_abundance_tags = ['composite', 'compositeAbundance']
        composite_abundance = oneOf(composite_abundance_tags) + LP + Group(simple_abundance) + OneOrMore(
            WCW + Group(simple_abundance)) + RP

        def handle_composite_abundance(s, loc, tokens):
            cls = tokens[0] = 'Composite'

            name = self.canonicalize_node(tokens)

            if name not in self.graph:
                self.graph.add_node(name, type=cls)

            for token in tokens[1:]:
                v_cls = token[0]
                v_ns, v_val = token[1]
                v = v_cls, v_ns, v_val
                self.graph.add_edge(name, v, relation='hasComponent', attr_dict=self.annotations.copy())

            return tokens

        composite_abundance.setParseAction(handle_composite_abundance)

        abundance = simple_abundance | composite_abundance

        # 2.4 Process Modifier Function

        # 2.4.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XmolecularA

        molecular_activity_tags = ['ma', 'molecularActivity']

        molecular_activities_default_ns = oneOf(language.activities)

        def handle_molecular_activities_default_ns(s, l, tokens):
            tokens[0] = language.activity_labels[tokens[0]]
            return tokens

        molecular_activities_default_ns.setParseAction(handle_molecular_activities_default_ns)

        # backwards compatibility with BEL v1.0
        molecular_activity_default_ns = oneOf(molecular_activity_tags) + LP + molecular_activities_default_ns + RP
        molecular_activity_custom_ns = oneOf(molecular_activity_tags) + LP + Group(ns_val) + RP

        molecular_activity = molecular_activity_default_ns | molecular_activity_custom_ns

        def handle_molecular_activity(s, l, tokens):
            tokens[0] = 'MolecularActivity'
            return tokens

        molecular_activity.setParseAction(handle_molecular_activity)

        # 2.3 Process Functions

        # 2.3.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_biologicalprocess_bp
        biological_process_tags = ['bp', 'biologicalProcess']
        biological_process = oneOf(biological_process_tags) + LP + Group(ns_val) + RP

        def handle_biological_process(s, l, tokens):
            cls = tokens[0] = 'BiologicalProcess'
            ns, val = tokens[1]
            n = cls, ns, val
            if n not in self.graph:
                self.graph.add_node(n, type=cls, namespace=ns, value=val)
            return tokens

        biological_process.setParseAction(handle_biological_process)

        # 2.3.2
        pathology_tags = ['path', 'pathology']
        pathology = oneOf(pathology_tags) + LP + Group(ns_val) + RP

        def handle_pathology(s, l, tokens):
            cls = tokens[0] = 'Pathology'
            ns, val = tokens[1]
            n = self.canonicalize_node(tokens)
            if n not in self.graph:
                self.graph.add_node(n, type=cls, namespace=ns, value=val)
            return tokens

        pathology.setParseAction(handle_pathology)

        # 2.3.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#Xactivity
        activity_tags = ['act', 'activity']

        activity_modified_default_ns = oneOf(activity_tags) + LP + Group(abundance) + WCW + Group(
            molecular_activity) + RP

        def handle_activity_modified_default_ns(s, l, tokens):
            tokens[0] = 'Activity'
            return tokens

        activity_modified_default_ns.setParseAction(handle_activity_modified_default_ns)

        activity_standard = oneOf(activity_tags) + LP + Group(abundance) + RP

        def handle_activity_standard(s, l, tokens):
            tokens[0] = 'Activity'
            return tokens

        activity_standard.setParseAction(handle_activity_standard)

        activity_legacy_tags = list(language.activities)
        activity_legacy = oneOf(activity_legacy_tags) + LP + Group(abundance) + RP

        def handle_activity_legacy(s, l, tokens):
            log.debug('PyBEL001 legacy activity statement. Use activity() instead. {}'.format(s))
            legacy_cls = language.activity_labels[tokens[0]]
            tokens[0] = 'Activity'
            tokens.append(['MolecularActivity', legacy_cls])
            return tokens

        activity_legacy.setParseAction(handle_activity_legacy)

        activity = activity_modified_default_ns | activity_standard | activity_legacy

        process = biological_process | pathology | activity

        # 2.5 Transformation Functions

        # 2.5.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_translocations

        from_loc = Suppress('fromLoc') + LP + ns_val + RP
        to_loc = Suppress('toLoc') + LP + ns_val + RP

        cell_secretion_tags = ['sec', 'cellSecretion']
        cell_secretion = oneOf(cell_secretion_tags) + LP + Group(simple_abundance) + RP

        def handle_cell_secretion(s, l, tokens):
            tokens[0] = 'CellSecretion'
            return tokens

        cell_secretion.setParseAction(handle_cell_secretion)

        cell_surface_expression_tags = ['surf', 'cellSurfaceExpression']
        cell_surface_expression = oneOf(cell_surface_expression_tags) + LP + Group(simple_abundance) + RP

        def handle_cell_surface_expression(s, l, tokens):
            tokens[0] = 'CellSurfaceExpression'
            return tokens

        cell_surface_expression.setParseAction(handle_cell_surface_expression)

        translocation_tags = ['translocation', 'tloc']
        translocation_standard = oneOf(translocation_tags) + LP + Group(simple_abundance) + WCW + Group(
            from_loc) + WCW + Group(
            to_loc) + RP

        def translocation_standard_handler(s, l, tokens):
            cls = tokens[0] = 'Translocation'

            ab_ns, ab_val = tokens[1][1]

            from_loc_ns, from_loc_val = tokens[2]
            to_loc_ns, to_loc_val = tokens[3]

            name = self.canonicalize_node(tokens)

            if name not in self.graph:
                self.graph.add_node(name, type=cls, namespace=ab_ns, value=ab_val, attr_dict={
                    'from_ns': from_loc_ns,
                    'from_value': from_loc_val,
                    'to_ns': to_loc_ns,
                    'to_value': to_loc_val
                })

            return tokens

        translocation_standard.setParseAction(translocation_standard_handler)

        translocation_legacy = oneOf(translocation_tags) + LP + Group(simple_abundance) + WCW + Group(
            ns_val) + WCW + Group(
            ns_val) + RP

        def translocation_legacy_handler(s, l, token):
            log.debug('PyBEL005 legacy translocation statement. use fromLoc() and toLoc(). {}'.format(s))
            return translocation_standard_handler(s, l, token)

        translocation_legacy.setParseAction(translocation_legacy_handler)

        translocation_legacy_singleton = oneOf(translocation_tags) + LP + Group(simple_abundance) + RP

        def handle_translocation_legacy_singleton(s, l, tokens):
            log.debug('PyBEL008 legacy translocation + missing arguments: {}'.format(s))
            tokens[0] = 'Translocation'
            return tokens

        translocation_legacy_singleton.setParseAction(handle_translocation_legacy_singleton)

        translocation = translocation_legacy | translocation_standard | translocation_legacy_singleton

        # 2.5.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_degradation_deg

        degradation_tags = ['deg', 'degradation']
        degradation = oneOf(degradation_tags) + LP + Group(simple_abundance) + RP

        def handle_degredation(s, l, tokens):
            tokens[0] = 'Degradation'
            return tokens

        degradation.setParseAction(handle_degredation)

        # 2.5.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_reaction_rxn
        reactants = Suppress('reactants') + LP + Group(simple_abundance) + ZeroOrMore(
            WCW + Group(simple_abundance)) + RP
        products = Suppress('products') + LP + Group(simple_abundance) + ZeroOrMore(WCW + Group(simple_abundance)) + RP

        reaction_tags = ['reaction', 'rxn']
        reaction = oneOf(reaction_tags) + LP + Group(reactants) + WCW + Group(products) + RP

        def handle_reaction(s, l, tokens):
            cls = tokens[0] = 'Reaction'
            name = self.canonicalize_node(tokens)

            if name not in self.graph:
                self.graph.add_node(name, type=cls)

            for reactant_tokens in tokens[1]:
                reactant_name = self.canonicalize_node(reactant_tokens)
                self.graph.add_edge(name, reactant_name, relation='hasReactant')

            for product_tokens in tokens[2]:
                product_name = self.canonicalize_node(product_tokens)
                self.graph.add_edge(name, product_name, relation='hasProduct')

            return tokens

        reaction.setParseAction(handle_reaction)

        transformation = cell_secretion | cell_surface_expression | translocation | degradation | reaction

        # 3 BEL Relationships

        bel_term = abundance | process | transformation

        # TODO finish all handlers for relationships

        # 3.1 Causal relationships

        causal_relationship = Forward()

        # 3.1.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#Xincreases
        increases_tags = ['->', '→', 'increases']
        increases = Group(bel_term) + WS + oneOf(increases_tags) + WS + (
            Group(bel_term) | (LP + causal_relationship + RP))

        def handle_increases(s, l, tokens):
            tokens[1] = 'increases'
            return tokens

        increases.setParseAction(handle_increases)

        # 3.1.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XdIncreases
        directly_increases_tags = ['=>', '⇒', 'directlyIncreases']
        directly_increases = Group(bel_term) + WS + oneOf(directly_increases_tags) + WS + (
            Group(bel_term) | (LP + causal_relationship + RP))

        def handle_directly_increases(s, l, tokens):
            tokens[1] = 'directlyIncreases'
            return tokens

        directly_increases.setParseAction(handle_directly_increases)

        # 3.1.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#Xdecreases
        decreases_tags = ['-|', 'decreases']
        decreases = Group(bel_term) + WS + oneOf(decreases_tags) + WS + (
            Group(bel_term) | (LP + causal_relationship + RP))

        def handle_decreases(s, l, tokens):
            tokens[1] = 'decreases'
            return tokens

        decreases.setParseAction(handle_decreases)

        # 3.1.4 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XdDecreases
        directly_decreases_tags = ['=|', '→', 'directlyDecreases']
        directly_decreases = Group(bel_term) + WS + oneOf(directly_decreases_tags) + WS + (
            Group(bel_term) | (LP + causal_relationship + RP))

        def handle_directly_decreases(s, l, tokens):
            tokens[1] = 'directlyDecreases'
            return tokens

        directly_decreases.setParseAction(handle_directly_decreases)

        # 3.1.5 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_ratelimitingstepof
        rate_limit_tags = ['rateLimitingStepOf']
        rate_limit = Group(biological_process | activity | transformation) + WS + oneOf(
            rate_limit_tags) + WS + Group(biological_process)

        # 3.1.6 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#Xcnc
        causes_no_change_tags = ['cnc', 'causesNoChange']
        causes_no_change = Group(bel_term) + WS + oneOf(causes_no_change_tags) + WS + Group(bel_term)

        def handle_causes_no_change(s, l, tokens):
            tokens[1] = 'causesNoChange'
            return tokens

        causes_no_change.setParseAction(handle_causes_no_change)

        # 3.1.7 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_regulates_reg
        regulates_tags = ['reg', 'regulates']
        regulates = Group(bel_term) + WS + oneOf(regulates_tags) + WS + Group(bel_term)

        def handle_regulates(s, l, tokens):
            tokens[1] = 'regulates'
            return tokens

        regulates.setParseAction(handle_regulates)

        causal_relationship << (
            increases | directly_increases | decreases | directly_decreases | rate_limit | causes_no_change | regulates)

        # 3.2 Correlative Relationships

        # 3.2.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XnegCor
        negative_correlation_tags = ['neg', 'negativeCorrelation']
        negative_correlation = Group(bel_term) + WS + oneOf(negative_correlation_tags) + WS + Group(bel_term)

        def handle_negative_correlation(s, l, tokens):
            tokens[1] = 'negativeCorrelation'
            return tokens

        negative_correlation.setParseAction(handle_negative_correlation)

        # 3.2.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XposCor
        positive_correlation_tags = ['pos', 'positiveCorrelation']
        positive_correlation = Group(bel_term) + WS + oneOf(positive_correlation_tags) + WS + Group(bel_term)

        def handle_positive_correlation(s, l, tokens):
            tokens[1] = 'positiveCorrelation'
            return tokens

        positive_correlation.setParseAction(handle_positive_correlation)

        # 3.2.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#Xassociation
        association_tags = ['--', 'association']
        association = Group(bel_term) + WS + oneOf(association_tags) + WS + Group(bel_term)

        def handle_association(s, l, tokens):
            tokens[1] = 'association'
            return tokens

        association.setParseAction(handle_association)

        correlative_relationships = negative_correlation | positive_correlation | association

        # 3.3 Genomic Relationships

        # 3.3.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_orthologous
        orthologous_tags = ['orthologous']
        orthologous = Group(bel_term) + WS + oneOf(orthologous_tags) + WS + Group(bel_term)

        # 3.3.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_transcribedto
        transcribed_tags = [':>', 'transcribedTo']
        transcribed = Group(gene) + WS + oneOf(transcribed_tags) + WS + Group(rna)

        def handle_transcribed(s, loc, tokens):
            tokens[1] = 'transcribedTo'
            return tokens

        transcribed.setParseAction(handle_transcribed)

        # 3.3.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_translatedto
        translated_tags = ['>>', 'translatedTo']
        translated = Group(rna) + WS + oneOf(translated_tags) + WS + Group(protein)

        def handle_translated(s, loc, tokens):
            tokens[1] = 'translatedTo'
            return tokens

        translated.setParseAction(handle_translated)

        genomic_relationship = orthologous | transcribed | translated

        # 3.4 Other Relationships

        # 3.4.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_hasmember
        has_member_tags = ['hasMember']
        has_member = Group(abundance) + WS + oneOf(has_member_tags) + WS + Group(abundance)

        # 3.4.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_hasmembers
        abundance_list = Suppress('list') + LP + Group(abundance) + OneOrMore(WCW + Group(abundance)) + RP

        has_members_tags = ['hasMembers']
        has_members = Group(abundance) + WS + oneOf(has_members_tags) + WS + Group(abundance_list)

        def handle_has_members(s, l, tokens):
            # TODO implement
            return tokens

        has_members.setParseAction(handle_has_members)

        # 3.4.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_hascomponent
        has_component_tags = ['hasComponent']
        has_component = Group(complex_abundances | composite_abundance) + WS + oneOf(has_component_tags) + WS + Group(
            abundance)

        # 3.4.5 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_isa
        is_a_tags = ['isA']
        is_a = Group(bel_term) + WS + oneOf(is_a_tags) + WS + Group(bel_term)

        # 3.4.6 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_subprocessof
        subprocess_of_tags = ['subProcessOf']
        subprocess_of = Group(process | activity | transformation) + WS + oneOf(subprocess_of_tags) + WS + Group(
            process)

        other_relationships = has_member | has_members | has_component | is_a | subprocess_of

        # 3.5 Deprecated

        # 3.5.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_analogous
        analogous_tags = ['analogousTo']
        analogous = Group(bel_term) + WS + oneOf(analogous_tags) + WS + Group(bel_term)

        # 3.5.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_biomarkerfor
        biomarker_tags = ['biomarkerFor']
        biomarker = Group(bel_term) + WS + oneOf(biomarker_tags) + Group(process)

        # 3.5.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_prognosticbiomarkerfor
        prognostic_biomarker_tags = ['prognosticBiomarkerFor']
        prognostic_biomarker = Group(bel_term) + WS + oneOf(prognostic_biomarker_tags) + WS + Group(process)

        deprecated_relationships = analogous | biomarker | prognostic_biomarker

        relation = (causal_relationship | correlative_relationships | genomic_relationship |
                    other_relationships | deprecated_relationships)

        def handle_relation(s, l, tokens):
            sub = self.ensure_node(tokens[0])
            pre = tokens[1]
            obj = self.ensure_node(tokens[2])
            self.graph.add_edge(sub, obj, relation=pre)
            return tokens

        relation.setParseAction(handle_relation)

        self.statement = relation | bel_term

    # TODO canonicalize order of fragments, protein modifications, etc with alphabetization

    def canonicalize_node(self, tokens):
        """Given tokens, returns node name"""
        command, *args = tokens.asList() if hasattr(tokens, 'asList') else tokens
        if command in ('Protein', 'Gene', 'Abundance', 'miRNA', 'RNA', 'Complex', 'Pathology', 'BiologicalProcess'):
            ns, val = args[0]
            return command, ns, val
        elif command in ('ComplexList', 'Composite', 'List', 'Reaction'):
            t = list2tuple(args[0])
            if t not in self.node_to_id:
                self.node_count += 1
                self.node_to_id[t] = self.node_count
            return command, self.node_to_id[t]
        elif command in ('Activity', 'Degradation', 'Translocation', 'CellSecretion', 'CellSurfaceExpression'):
            return self.canonicalize_node(args[0])
        elif command in ('GeneVariant', 'RNAVariant', 'ProteinVariant'):
            ns, val = args[0]
            # mod_title, *mod_params = args[1]
            mod = list2tuple(args[1])
            # todo: flatten then splat sorted(args[1:], key=itemgetter(0))
            name = (command, ns, val, *mod)
            return name
        else:
            raise NotImplementedError("Haven't written canonicalization for {}".format(command))

    def ensure_node(self, tokens, **kwargs):
        """Turns parsed tokens into canonical node names"""
        command, *args = tokens

        if command in ('GeneVariant', 'RNAVariant', 'ProteinVariant'):
            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name)

            parent_name = self.ensure_node([d[command], tokens[1]])
            self.graph.add_edge(name, parent_name)
            return name
        elif command == 'Protein':
            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, **kwargs)

            rna_tokens = tokens.copy()
            rna_tokens[0] = 'RNA'
            rna_name = self.ensure_node(rna_tokens)

            self.graph.add_edge(rna_name, name, relation='translatedTo')
        elif command == 'RNA':
            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, **kwargs)

            gene_tokens = tokens.copy()
            gene_tokens[0] = 'Gene'
            gene_name = self.ensure_node(gene_tokens)

            self.graph.add_edge(gene_name, name, relation='transcribedTo')
        else:
            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, **kwargs)
            return name

    def canonicalize_modifier(self, tokens):
        """Get activity, transformation, or transformation"""
        pass

    def validate_ns_pair(self, s, location, tokens):
        # TODO test listed namespace
        # if len(tokens) == 1:
        #    if tokens[0] in self.names:
        #        return tokens
        #    else:
        #        log.warning('PyBEL007 Name Exception: no namespace {}'.format(tokens))
        #        raise Exception()

        ns, val = tokens

        if self.namespaces is None:
            pass
        elif ns not in self.namespaces:
            log.warning('PyBEL003 Namespace Exception: invalid namespace: {}'.format(ns))
            raise Exception()
        elif val not in self.namespaces[ns]:
            log.warning('PyBEL004 Namespace Exception: {} is not a valid member of {}'.format(val, ns))
            raise Exception()

        if self.namespace_mapping is None:
            pass
        elif ns in self.namespace_mapping and val in self.namespace_mapping[ns]:
            return self.namespace_mapping[ns][val]

        return tokens

    def parse(self, s):
        try:
            return self.statement.parseString(s).asList()
        except Exception as e:
            log.warning('PyBEL000 general parser failure: {}'.format(s))

    def reset_metadata(self):
        self.annotations = {}

    def set_metadata(self, key, value):
        self.annotations[key] = value

    def unset_metadata(self, key):
        if key in self.annotations:
            del self.annotations[key]

    def set_citation(self, citation):
        # TODO implement
        pass
