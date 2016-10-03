import logging

from pyparsing import Suppress, ZeroOrMore, White, dblQuotedString, removeQuotes, delimitedList, oneOf

from .baseparser import BaseParser

log = logging.getLogger(__name__)

W = Suppress(ZeroOrMore(White()))
WCW = W + Suppress(',') + W
q = dblQuotedString().setParseAction(removeQuotes)

citationSet = Suppress('{') + delimitedList(q)('values') + Suppress('}')


class ControlParser(BaseParser):
    def __init__(self, citation=None, annotations=None, custom_annotations=None):
        """Builds parser for BEL custom_annotations statements

        :param custom_annotations: A dictionary from {annotation: set of valid values} for parsing
        :type custom_annotations: dict
        :return:
        """

        self.citation = {} if citation is None else citation
        self.annotations = {} if annotations is None else annotations
        self.custom_annotations = dict() if custom_annotations is None else custom_annotations
        self.statement_group = None

        custom_annotations = oneOf(self.custom_annotations.keys())

        self.set_citation = Suppress('SET') + W + Suppress('Citation') + W + Suppress('=') + W + citationSet
        self.set_citation.setParseAction(self.handle_citation)

        self.set_evidence = Suppress('SET') + W + Suppress('Evidence') + W + Suppress('=') + W + q('value')
        self.set_evidence.setParseAction(self.handle_evidence)

        self.set_statement_group = Suppress('SET') + W + Suppress('STATEMENT_GROUP') + W + Suppress('=') + W + q(
            'group')
        self.set_statement_group.setParseAction(self.handle_statement_group)

        self.set_command = Suppress('SET') + W + custom_annotations('key') + W + Suppress('=') + W + q('value')
        self.set_command.setParseAction(self.handle_set_command)

        self.unset_command = Suppress('UNSET') + W + (custom_annotations | 'Evidence')('key')
        self.unset_command.setParseAction(self.handle_unset_command)

        self.unset_statement_group = Suppress('UNSET') + W + Suppress('STATEMENT_GROUP')
        self.unset_statement_group.setParseAction(self.handle_unset_statement_group)

        self.commands = (self.set_citation | self.unset_command | self.unset_statement_group |
                         self.set_statement_group | self.set_evidence | self.set_command)

    def handle_citation(self, s, l, tokens):
        self.citation.clear()
        self.annotations.clear()

        values = tokens['values']

        if 3 == len(values):
            self.citation = dict(zip(('type', 'name', 'reference'), values))
        elif 6 == len(values):
            self.citation = dict(zip(('type', 'name', 'reference', 'date', 'authors', 'comments'), values))
        else:
            raise Exception('PyBEL011 invalid citation: {}'.format(s))

        return tokens

    def handle_evidence(self, s, l, tokens):
        if 'value' not in tokens:
            log.error('ERROR {} {} {}'.format(s, l, tokens))
        value = tokens['value']
        self.annotations['Evidence'] = value
        return tokens

    def handle_statement_group(self, s, l, tokens):
        self.statement_group = tokens['group']
        return tokens

    def handle_set_command(self, s, l, tokens):
        key = tokens['key']
        value = tokens['value']

        if value not in self.custom_annotations[key]:
            raise Exception('PyBEL012 illegal annotation value')

        self.annotations[key] = value
        return tokens

    def handle_unset_statement_group(self):
        self.statement_group = None

    def handle_unset_command(self, s, l, tokens):
        key = tokens['key']
        del self.annotations[key]
        return tokens

    def get_language(self):
        return self.commands
