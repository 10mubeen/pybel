#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from copy import deepcopy

import networkx as nx
from pyparsing import Suppress, delimitedList, oneOf, Optional, Group, replaceWith

from . import language
from .baseparser import BaseParser, W, WCW, nest, one_of_tags
from .parse_abundance_modifier import VariantParser, PsubParser, GsubParser, FragmentParser, FusionParser, \
    LocationParser
from .parse_control import ControlParser
from .parse_identifier import IdentifierParser
from .parse_pmod import PmodParser
from .utils import list2tuple

log = logging.getLogger(__name__)


def triple(subject, relation, obj):
    return Group(subject)('subject') + W + relation('relation') + W + Group(obj)('object')


def handle_warning(fmt):
    def handle(s, l, t):
        log.warning(fmt.format(s=s, location=l, tokens=t))
        return t

    return handle


class BelParser(BaseParser):
    """
    Build a parser backed by a given dictionary of namespaces
    """

    def __init__(self, graph=None, namespace_dict=None, namespace_mapping=None, custom_annotations=None):
        """
        :param namespace_dict: A dictionary of {namespace: set of members}
        :param graph: the graph to put the network in. Constructs new nx.MultiDiGrap if None
        :type graph: nx.MultiDiGraph
        :param namespace_mapping: a dict of {name: {value: (other_namepace, other_name)}}
        """

        self.graph = graph if graph is not None else nx.MultiDiGraph()

        self.control_parser = ControlParser(custom_annotations=custom_annotations)
        self.identifier_parser = IdentifierParser(namespace_dict=namespace_dict, mapping=namespace_mapping)

        self.node_count = 0
        self.node_to_id = {}
        self.id_to_node = {}

        identifier = Group(self.identifier_parser.get_language())('identifier')

        # 2.2 Abundance Modifier Functions

        # 2.2.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_protein_modifications
        self.pmod = PmodParser(namespace_parser=self.identifier_parser).get_language()

        # 2.2.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_variant_var
        self.variant = VariantParser().get_language()

        # 2.2.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_proteolytic_fragments
        self.fragment = FragmentParser().get_language()

        # 2.2.4 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_cellular_location
        self.location = LocationParser(self.identifier_parser).get_language()

        # 2.2.X Deprecated substitution function from BEL 1.0
        self.psub = PsubParser().get_language()
        self.gsub = GsubParser().get_language()

        # 2.6 Other Functions

        # 2.6.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_fusion_fus
        self.fusion = FusionParser(self.identifier_parser).get_language()

        # 2.1 Abundance Functions

        # 2.1.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XcomplexA
        general_abundance_tags = one_of_tags(['a', 'abundance'], 'Abundance', 'function')
        self.general_abundance = general_abundance_tags + nest(identifier)
        self.general_abundance.addParseAction(self.handle)

        # 2.1.4 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XgeneA
        gene_tag = one_of_tags(['g', 'geneAbundance'], 'Gene', 'function')
        self.gene_simple = gene_tag + nest(identifier + Optional(WCW + self.location))
        self.gene_simple.addParseAction(self.handle)

        self.gene_modified = gene_tag + nest(identifier, delimitedList(Group(self.variant | self.gsub))('variants') +
                                             Optional(WCW + self.location))
        self.gene_modified.setParseAction(self.handle)

        self.gene_fusion = gene_tag + nest(Group(self.fusion)('fusion') + Optional(WCW + self.location))
        self.gene_fusion.setParseAction(self.handle)

        self.gene = self.gene_modified | self.gene_simple | self.gene_fusion

        # 2.1.5 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XmicroRNAA
        mirna_tag = one_of_tags(['m', 'microRNAAbundance'], 'miRNA', 'function')
        self.mirna_simple = mirna_tag + nest(identifier + Optional(WCW + self.location))
        self.mirna_simple.setParseAction(self.handle)

        self.mirna_modified = mirna_tag + nest(identifier, delimitedList(Group(self.variant))('variants') + Optional(
            WCW + self.location))
        self.mirna_modified.setParseAction(self.handle)

        self.mirna = self.mirna_modified | self.mirna_simple

        # 2.1.6 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XproteinA
        protein_tag = one_of_tags(['p', 'proteinAbundance'], 'Protein', 'function')
        self.protein_simple = protein_tag + nest(identifier + Optional(WCW + self.location))
        self.protein_simple.setParseAction(self.handle)

        self.protein_modified = protein_tag + nest(
            identifier, delimitedList(Group(self.pmod | self.variant | self.fragment | self.psub))(
                'variants') + Optional(WCW + self.location))

        self.protein_modified.setParseAction(self.handle)

        self.protein_fusion = protein_tag + nest(Group(self.fusion)('fusion') + Optional(WCW + self.location))
        self.protein_fusion.setParseAction(self.handle)

        self.protein = self.protein_fusion | self.protein_modified | self.protein_simple

        # 2.1.7 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XrnaA
        rna_tag = one_of_tags(['r', 'rnaAbundance'], 'RNA', 'function')
        self.rna_simple = rna_tag + nest(identifier + Optional(WCW + self.location))
        self.rna_simple.setParseAction(self.handle)

        self.rna_modified = rna_tag + nest(identifier, delimitedList(Group(self.variant))('variants') + Optional(
            WCW + self.location))
        self.rna_modified.setParseAction(self.handle)

        self.rna_fusion = rna_tag + nest(Group(self.fusion)('fusion') + Optional(WCW + self.location))
        self.rna_fusion.setParseAction(self.handle)

        self.rna = self.rna_fusion | self.rna_modified | self.rna_simple

        self.single_abundance = self.general_abundance | self.gene | self.mirna | self.protein | self.rna

        # 2.1.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XcomplexA
        complex_tag = one_of_tags(['complex', 'complexAbundance'], 'Complex', 'function')
        self.complex_singleton = complex_tag + nest(identifier + Optional(WCW + self.location))
        self.complex_singleton.setParseAction(self.handle)

        # complex_list_tag = one_of_tags(['complex', 'complexAbundance'], 'ComplexList', 'function')
        self.complex_list = complex_tag + nest(
            delimitedList(Group(self.single_abundance | self.complex_singleton))('members') + Optional(
                WCW + self.location))
        self.complex_list.setParseAction(self.handle)

        self.complex_abundances = self.complex_list | self.complex_singleton

        # Definition of all simple abundances that can be used in a composite abundance
        self.simple_abundance = self.complex_abundances | self.single_abundance

        # 2.1.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XcompositeA
        composite_abundance_tag = one_of_tags(['composite', 'compositeAbundance'], 'Composite', 'function')
        self.composite_abundance = composite_abundance_tag + nest(
            delimitedList(Group(self.simple_abundance))('members') + Optional(WCW + self.location))
        self.composite_abundance.setParseAction(self.handle)

        self.abundance = self.simple_abundance | self.composite_abundance

        # 2.4 Process Modifier Function

        # 2.4.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XmolecularA

        molecular_activity_tags = oneOf(['ma', 'molecularActivity']).setParseAction(replaceWith('MolecularActivity'))

        self.molecular_activities_default_ns = oneOf(language.activities)
        self.molecular_activities_default_ns.setParseAction(lambda s, l, t: [language.activity_labels[t[0]]])

        # backwards compatibility with BEL v1.0
        molecular_activity_default_ns = molecular_activity_tags + nest(self.molecular_activities_default_ns)
        molecular_activity_custom_ns = molecular_activity_tags + nest(identifier)

        self.molecular_activity = molecular_activity_default_ns | molecular_activity_custom_ns

        # 2.3 Process Functions

        # 2.3.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_biologicalprocess_bp
        biological_process_tag = one_of_tags(['bp', 'biologicalProcess'], 'BiologicalProcess', 'function')
        self.biological_process = biological_process_tag + nest(identifier)
        self.biological_process.setParseAction(self.handle)

        # 2.3.2
        pathology_tag = one_of_tags(['path', 'pathology'], 'Pathology', 'function')
        self.pathology = pathology_tag + nest(identifier)
        self.pathology.setParseAction(self.handle)

        # 2.3.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#Xactivity
        activity_tags = one_of_tags(['act', 'activity'], 'Activity', 'modifier')

        self.activity_modified_default_ns = activity_tags + nest(Group(self.abundance)('target') + WCW + Group(
            self.molecular_activity)('activity'))
        self.activity_standard = activity_tags + nest(Group(self.abundance)('target'))  # TODO compress with 'Optional'

        activity_legacy_tags = oneOf(language.activities)('modifier')
        self.activity_legacy = activity_legacy_tags + nest(Group(self.abundance)('target'))

        def handle_activity_legacy(s, l, tokens):
            log.debug('PyBEL001 legacy activity statement. Use activity() instead. {}'.format(s))
            legacy_cls = language.activity_labels[tokens['modifier']]
            tokens['modifier'] = 'Activity'
            tokens['activity'] = {
                'MolecularActivity': legacy_cls
            }
            return tokens

        self.activity_legacy.setParseAction(handle_activity_legacy)

        self.activity = self.activity_modified_default_ns | self.activity_standard | self.activity_legacy

        self.process = self.biological_process | self.pathology | self.activity

        # 2.5 Transformation Functions

        # 2.5.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_translocations

        from_loc = Suppress('fromLoc') + nest(identifier)
        to_loc = Suppress('toLoc') + nest(identifier)

        cell_secretion_tags = one_of_tags(['sec', 'cellSecretion'], 'CellSecretion', 'modifier')
        self.cell_secretion = cell_secretion_tags + nest(Group(self.simple_abundance)('target'))
        self.cell_secretion.setParseAction(self.handle)

        cell_surface_expression_tags = one_of_tags(['surf', 'cellSurfaceExpression'], 'CellSurfaceExpression',
                                                   'modifier')
        self.cell_surface_expression = cell_surface_expression_tags + nest(Group(self.simple_abundance)('target'))
        self.cell_surface_expression.setParseAction(self.handle)

        translocation_tags = one_of_tags(['translocation', 'tloc'], 'Translocation', 'modifier')
        self.translocation_standard = translocation_tags + nest(Group(self.simple_abundance)('target'),
                                                                from_loc('fromLoc'),
                                                                to_loc('toLoc'))

        self.translocation_standard.setParseAction(self.handle)
        self.translocation_legacy = translocation_tags + nest(Group(self.simple_abundance)('target'), identifier,
                                                              identifier)
        self.translocation_legacy.setParseAction(self.handle)
        self.translocation_legacy.addParseAction(
            handle_warning('PyBEL005 legacy translocation statement. use fromLoc() and toLoc(). {s}'))

        self.translocation_legacy_singleton = translocation_tags + nest(Group(self.simple_abundance))
        self.translocation_legacy_singleton.setParseAction(self.handle)
        self.translocation_legacy_singleton.addParseAction(
            handle_warning('PyBEL008 legacy translocation + missing arguments: {s}'))

        self.translocation = (self.translocation_standard | self.translocation_legacy |
                              self.translocation_legacy_singleton)

        # 2.5.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_degradation_deg

        degradation_tags = one_of_tags(['deg', 'degradation'], 'Degradation', 'modifier')
        self.degradation = degradation_tags + nest(Group(self.simple_abundance)('target'))
        self.degradation.setParseAction(self.handle)

        # 2.5.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_reaction_rxn
        self.reactants = Suppress('reactants') + nest(delimitedList(Group(self.simple_abundance)))
        self.products = Suppress('products') + nest(delimitedList(Group(self.simple_abundance)))

        reaction_tags = one_of_tags(['reaction', 'rxn'], 'Reaction', 'transformation')
        self.reaction = reaction_tags + nest(Group(self.reactants)('reactants'), Group(self.products)('products'))
        self.reaction.setParseAction(self.handle)

        self.transformation = (self.cell_secretion | self.cell_surface_expression |
                               self.translocation | self.degradation | self.reaction)

        # 3 BEL Relationships

        self.bel_term = self.transformation | self.process | self.abundance

        # 3.1 Causal relationships

        # 3.1.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#Xincreases
        increases_tag = oneOf(['->', '→', 'increases']).setParseAction(replaceWith('increases'))
        increases = triple(self.bel_term, increases_tag, self.bel_term)

        # 3.1.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XdIncreases
        directly_increases_tag = oneOf(['=>', '⇒', 'directlyIncreases']).setParseAction(
            replaceWith('directlyIncreases'))
        directly_increases = triple(self.bel_term, directly_increases_tag, self.bel_term)

        # 3.1.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#Xdecreases
        decreases_tag = oneOf(['-|', 'decreases']).setParseAction(replaceWith('decreases'))
        decreases = triple(self.bel_term, decreases_tag, self.bel_term)

        # 3.1.4 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XdDecreases
        directly_decreases_tag = oneOf(['=|', '→', 'directlyDecreases']).setParseAction(
            replaceWith('directlyDecreases'))
        directly_decreases = triple(self.bel_term, directly_decreases_tag, self.bel_term)

        # 3.1.5 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_ratelimitingstepof
        rate_limit_tag = oneOf(['rateLimitingStepOf'])
        rate_limit = triple(self.biological_process | self.activity | self.transformation, rate_limit_tag,
                            self.biological_process)

        # 3.1.6 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#Xcnc
        causes_no_change_tag = oneOf(['cnc', 'causesNoChange']).setParseAction(replaceWith('causesNoChange'))
        causes_no_change = triple(self.bel_term, causes_no_change_tag, self.bel_term)

        # 3.1.7 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_regulates_reg
        regulates_tag = oneOf(['reg', 'regulates']).setParseAction(replaceWith('regulates'))
        regulates = triple(self.bel_term, regulates_tag, self.bel_term)

        causal_relationship = (increases | directly_increases | decreases |
                               directly_decreases | rate_limit | causes_no_change | regulates)

        # 3.1 Causal Relationships - nested
        # TODO should this feature be discontinued?

        increases_nested = triple(self.bel_term, increases_tag, nest(causal_relationship))
        decreases_nested = triple(self.bel_term, decreases_tag, nest(causal_relationship))
        directly_increases_nested = triple(self.bel_term, directly_increases_tag, nest(causal_relationship))
        directly_decreases_nested = triple(self.bel_term, directly_decreases_tag, nest(causal_relationship))

        nested_causal_relationship = (
            increases_nested | decreases_nested | directly_increases_nested | directly_decreases_nested)

        # 3.2 Correlative Relationships

        # 3.2.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XnegCor
        negative_correlation_tag = oneOf(['neg', 'negativeCorrelation']).setParseAction(
            replaceWith('negativeCorrelation'))
        negative_correlation = triple(self.bel_term, negative_correlation_tag, self.bel_term)

        # 3.2.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#XposCor
        positive_correlation_tag = oneOf(['pos', 'positiveCorrelation']).setParseAction(
            replaceWith('positiveCorrelation'))
        positive_correlation = triple(self.bel_term, positive_correlation_tag, self.bel_term)

        # 3.2.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#Xassociation
        association_tag = oneOf(['--', 'association']).setParseAction(replaceWith('association'))
        association = triple(self.bel_term, association_tag, self.bel_term)

        correlative_relationships = negative_correlation | positive_correlation | association

        # 3.3 Genomic Relationships

        # 3.3.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_orthologous
        orthologous_tag = oneOf(['orthologous'])
        orthologous = triple(self.bel_term, orthologous_tag, self.bel_term)

        # 3.3.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_transcribedto
        transcribed_tag = oneOf([':>', 'transcribedTo']).setParseAction(replaceWith('transcribedTo'))
        transcribed = triple(self.gene, transcribed_tag, self.rna)

        # 3.3.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_translatedto
        translated_tag = oneOf(['>>', 'translatedTo']).setParseAction(replaceWith('translatedTo'))
        translated = triple(self.rna, translated_tag, self.protein)

        genomic_relationship = orthologous | transcribed | translated

        # 3.4 Other Relationships

        # 3.4.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_hasmember
        has_member_tag = oneOf(['hasMember'])
        has_member = triple(self.abundance, has_member_tag, self.abundance)

        # 3.4.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_hasmembers
        self.abundance_list = Suppress('list') + nest(delimitedList(Group(self.abundance)))

        has_members_tag = oneOf(['hasMembers'])
        has_members = triple(self.abundance, has_members_tag, self.abundance_list)

        def handle_has_members(s, l, tokens):
            parent = self.ensure_node(s, l, tokens[0])
            for child_tokens in tokens[2]:
                child = self.ensure_node(s, l, child_tokens)
                self.graph.add_edge(parent, child, relation='hasMember')
            return tokens

        has_members.setParseAction(handle_has_members)

        # 3.4.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_hascomponent
        has_component_tag = oneOf(['hasComponent'])
        has_component = triple(self.complex_abundances | self.composite_abundance, has_component_tag, self.abundance)

        # 3.4.5 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_isa
        is_a_tag = oneOf(['isA'])
        is_a = triple(self.bel_term, is_a_tag, self.bel_term)

        # 3.4.6 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_subprocessof
        subprocess_of_tag = oneOf(['subProcessOf'])
        subprocess_of = triple(self.process | self.activity | self.transformation, subprocess_of_tag, self.process)

        other_relationships = has_member | has_component | is_a | subprocess_of

        # 3.5 Deprecated

        # 3.5.1 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_analogous
        analogous_tag = oneOf(['analogousTo'])
        analogous = triple(self.bel_term, analogous_tag, self.bel_term)

        # 3.5.2 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_biomarkerfor
        biomarker_tag = oneOf(['biomarkerFor'])
        biomarker = triple(self.bel_term, biomarker_tag, self.process)

        # 3.5.3 http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_prognosticbiomarkerfor
        prognostic_biomarker_tag = oneOf(['prognosticBiomarkerFor'])
        prognostic_biomarker = triple(self.bel_term, prognostic_biomarker_tag, self.process)

        deprecated_relationships = analogous | biomarker | prognostic_biomarker

        relation = (causal_relationship | correlative_relationships | genomic_relationship |
                    other_relationships | deprecated_relationships)

        def handle_relation(s, l, tokens):
            sub = self.ensure_node(s, l, tokens[0])
            obj = self.ensure_node(s, l, tokens[2])

            attrs = {
                'relation': tokens[1]
            }

            sub_mod = self.canonicalize_modifier(tokens[0])
            if sub_mod:
                attrs['subject'] = sub_mod

            obj_mod = self.canonicalize_modifier(tokens[2])
            if obj_mod:
                attrs['object'] = obj_mod

            attrs.update(self.get_annotations())

            self.graph.add_edge(sub, obj, attr_dict=attrs)
            return tokens

        relation.setParseAction(handle_relation)

        def handle_nested_relation(s, l, tokens):
            # TODO tests
            subject = self.ensure_node(s, l, tokens['subject'])
            relation_1 = tokens['relation']
            nested = self.ensure_node(s, l, tokens['object'])

            handle_relation(s, l, nested)  # ensure the nested relationship

            nested_relation = tokens['object']['relation']
            nested_object = self.ensure_node(s, l, tokens['object']['object'])

            attrs = {
                'relation': language.compound_relation_dict[relation_1, nested_relation]
            }

            sub_mod = self.canonicalize_modifier(tokens['subject'])
            if sub_mod:
                attrs['subject'] = sub_mod

            attrs.update(self.get_annotations())
            self.graph.add_edge(subject, nested_object, attr_dict=attrs)

            return tokens

        nested_causal_relationship.setParseAction(handle_nested_relation)

        # has_members is handled differently from all other relations becuase it gets distrinbuted
        relation = has_members | nested_causal_relationship | relation

        self.statement = relation | self.bel_term
        self.language = self.control_parser.get_language() | self.statement

    def get_language(self):
        """Get language defined by this parser"""
        return self.language

    def get_annotations(self):
        """Get current annotations in this parser"""
        return self.control_parser.get_annotations()

    def handle(self, s, l, tokens):
        name = self.ensure_node(s, l, tokens)
        log.info('handled node: {}'.format(name))
        return tokens

    def add_unqualified_edge(self, u, v, relation):
        """Adds unique edge that has no annotations
        :param u: source node
        :param v: target node
        :param relation: relationship label
        """
        if not self.graph.has_edge(u, v, relation):
            self.graph.add_edge(u, v, key=relation, relation=relation)

    def canonicalize_node(self, tokens):
        """Given tokens, returns node name"""
        if 'function' in tokens and 'variants' in tokens:
            if tokens['function'] not in ('Gene', 'miRNA', 'Protein', 'RNA'):
                raise NotImplementedError()

            type_name = '{}Variant'.format(tokens['function'])
            name = type_name, tokens['identifier']['namespace'], tokens['identifier']['name']
            variants = list2tuple(sorted(tokens['variants'].asList()))
            return name + variants

        elif 'function' in tokens and 'members' in tokens:
            t = (tokens['function'],) + tuple(sorted(list2tuple(tokens['members'].asList())))

            if t in self.node_to_id:
                return tokens['function'], self.node_to_id[t]

            self.node_count += 1
            self.node_to_id[t] = self.node_count
            self.id_to_node[self.node_count] = t

            return tokens['function'], self.node_count

        elif 'transformation' in tokens and tokens['transformation'] == 'Reaction':
            reactants = tuple(sorted(list2tuple(tokens['reactants'].asList())))
            products = tuple(sorted(list2tuple(tokens['products'].asList())))
            t = (tokens['transformation'],) + reactants + products

            if t in self.node_to_id:
                return tokens['transformation'], self.node_to_id[t]

            self.node_count += 1
            self.node_to_id[t] = self.node_count
            self.id_to_node[self.node_count] = t
            return tokens['transformation'], self.node_count

        elif 'function' in tokens and tokens['function'] in ('Gene', 'RNA', 'Protein') and 'fusion' in tokens:
            f = tokens['fusion']
            return (tokens['function'], f['partner_5p']['namespace'], f['partner_5p']['name']) + tuple(
                f['range_5p']) + (f['partner_3p']['namespace'], f['partner_3p']['name']) + tuple(
                tokens['fusion']['range_3p'])

        elif 'function' in tokens and tokens['function'] in (
                'Gene', 'RNA', 'miRNA', 'Protein', 'Abundance', 'Complex', 'Pathology', 'BiologicalProcess'):
            if 'identifier' in tokens:
                return tokens['function'], tokens['identifier']['namespace'], tokens['identifier']['name']

        print('LOST', tokens)

        if 'modifier' in tokens and tokens['modifier'] in (
                'Activity', 'Degradation', 'Translocation', 'CellSecretion', 'CellSurfaceExpression'):
            print('modifier tokens:', tokens)
            return self.canonicalize_node(tokens['target'])

        raise NotImplementedError('canonicalize_node not implemented for: {}'.format(tokens))

    def ensure_node(self, s, l, tokens):
        """Turns parsed tokens into canonical node name and makes sure its in the graph"""

        print('ensuring tokens', tokens)

        if 'modifier' in tokens and tokens['modifier'] in (
                'Translocation', 'Degradation', 'CellSecretion', 'CellSurfaceExpression'):
            return self.ensure_node(s, l, tokens['target'])

        if 'transformation' in tokens:
            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, type=tokens['transformation'])

            for reactant_tokens in tokens['reactants']:
                reactant_name = self.ensure_node(s, l, reactant_tokens)
                self.add_unqualified_edge(name, reactant_name, relation='hasReactant')

            for product_tokens in tokens['products']:
                product_name = self.ensure_node(s, l, product_tokens)
                self.add_unqualified_edge(name, product_name, relation='hasProduct')

            return name

        if 'function' in tokens and 'members' in tokens:
            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name, type=tokens['function'])

            for token in tokens['members']:
                member_name = self.ensure_node(s, l, token)
                self.add_unqualified_edge(name, member_name, relation='hasComponent')
            return name

        if 'function' in tokens and 'variants' in tokens:
            name = self.canonicalize_node(tokens)
            if name not in self.graph:
                self.graph.add_node(name)

            c = {
                'function': tokens['function'],
                'identifier': tokens['identifier']
            }

            parent = self.canonicalize_node(c)
            self.add_unqualified_edge(parent, name, relation='hasVariant')
            return name

        elif 'function' in tokens and 'fusion' in tokens:
            name = self.canonicalize_node(tokens)
            cls = '{}Fusion'.format(tokens['function'])
            if name not in self.graph:
                self.graph.add_node(name, type=cls)
            return name

        elif 'function' in tokens and 'identifier' in tokens:
            if tokens['function'] in ('Gene', 'miRNA', 'Pathology', 'BiologicalProcess', 'Abundance', 'Complex'):
                name = self.canonicalize_node(tokens)
                if name not in self.graph:
                    self.graph.add_node(name,
                                        type=tokens['function'],
                                        namespace=tokens['identifier']['namespace'],
                                        name=tokens['identifier']['name'])
                return name

            elif tokens['function'] == 'RNA':
                name = self.canonicalize_node(tokens)

                if name not in self.graph:
                    self.graph.add_node(name,
                                        type=tokens['function'],
                                        namespace=tokens['identifier']['namespace'],
                                        name=tokens['identifier']['name'])

                gene_tokens = deepcopy(tokens)
                gene_tokens['function'] = 'Gene'
                gene_name = self.ensure_node(s, l, gene_tokens)

                self.add_unqualified_edge(gene_name, name, relation='transcribedTo')
                return name

            elif tokens['function'] == 'Protein':
                print('protein time!')
                name = self.canonicalize_node(tokens)

                if name not in self.graph:
                    self.graph.add_node(name,
                                        type=tokens['function'],
                                        namespace=tokens['identifier']['namespace'],
                                        name=tokens['identifier']['name'])

                rna_tokens = deepcopy(tokens)
                rna_tokens['function'] = 'RNA'
                rna_name = self.ensure_node(s, l, rna_tokens)

                self.add_unqualified_edge(rna_name, name, relation='translatedTo')
                return name

        raise NotImplementedError("ensure_node not implemented for: {}".format(tokens))


    def canonicalize_modifier(self, tokens):
        """
        Get activity, transformation, or transformation information as a dictionary
        :param tokens:
        :return:
        """

        command, *args = list2tuple(tokens.asList() if hasattr(tokens, 'asList') else tokens)

        if command not in ('Activity', 'Degradation', 'Translocation', 'CellSecretion', 'CellSurfaceExpression'):
            return {}

        res = {
            'modification': command,
            'params': {}
        }

        if command == 'Activity':
            if len(args) > 1:  # has molecular activity annotation
                res['params'] = {
                    'molecularActivity': args[1][1]
                }
            # TODO switch between legacy annotation and namespace:name annotation
            return res
        elif command == 'Degradation':
            return res
        elif command == 'Translocation':
            res['params'] = {
                'fromLoc': {
                    'namespace': args[1][0],
                    'name': args[1][1]
                },
                'toLoc': {
                    'namespace': args[2][0],
                    'name': args[2][1]
                }
            }
            return res
        elif command == 'CellSecretion':
            res['params'] = {
                'fromLoc': dict(namespace='GOCC', name='intracellular'),
                'toLoc': dict(namespace='GOCC', name='extracellular space')
            }
            return res
        elif command == 'CellSurfaceExpression':
            res['params'] = {
                'fromLoc': dict(namespace='GOCC', name='intracellular'),
                'toLoc': dict(namespace='GOCC', name='cell surface')
            }
            return res


def flatten_modifier_dict(d, prefix=''):
    command = d['modification']
    res = {
        '{}_modification'.format(prefix): command
    }

    if command == 'Activity':
        if 'params' in d and 'activity' in d['params']:
            if isinstance(d['params']['activity'], (list, tuple)):
                res['{}_params_activity_namespace'.format(prefix)] = d['params']['activity']['namespace']
                res['{}_params_activity_value'.format(prefix)] = d['params']['activity']['name']
            else:
                res['{}_params_activity'.format(prefix)] = d['params']['activity']
    elif command in ('Translocation', 'CellSecretion', 'CellSurfaceExpression'):
        res['{}_params_fromLoc_namespace'.format(prefix)] = d['params']['fromLoc']['namespace']
        res['{}_params_fromLoc_value'.format(prefix)] = d['params']['fromLoc']['name']
        res['{}_params_toLoc_namespace'.format(prefix)] = d['params']['toLoc']['namespace']
        res['{}_params_toLoc_value'.format(prefix)] = d['params']['toLoc']['name']
    elif command == 'Degradation':
        pass
    return res
