# -*- coding: utf-8 -*-

"""

Location data also is added into the information in the edge for the node (subject or object) for which it was
annotated. :code:`p(HGNC:GSK3B, pmod(P, S, 9), loc(GOCC:lysozome)) pos act(p(HGNC:GSK3B), ma(kin))` becomes:

.. code::

    {
        pbc.SUBJECT: {
            pbc.LOCATION: {
                pbc.NAMESPACE: 'GOCC',
                pbc.NAME: 'lysozome'
            }
        },
        pbc.RELATION: 'positiveCorrelation',
        pbc.OBJECT: {
            pbc.MODIFIER: pbc.ACTIVITY,
            pbc.EFFECT: {
                pbc.NAMESPACE: pbc.BEL_DEFAULT_NAMESPACE
                pbc.NAME: 'kin',
            }
        },
        pbc.EVIDENCE: '...',
        pbc.CITATION: { ... }
    }


The addition of the :code:`location()` element in BEL 2.0 allows for the unambiguous expression of the differences
between the process of hypothetical :code:`HGNC:A` moving from one place to another and the existence of
hypothetical :code:`HGNC:A` in a specific location having different effects. In BEL 1.0, this action had its own node,
but this introduced unnecessary complexity to the network and made querying more difficult.
This calls for thoughtful consideration of the following two statements:

- :code:`tloc(p(HGNC:A), fromLoc(GOCC:intracellular), toLoc(GOCC:"cell membrane")) -> p(HGNC:B)`
- :code:`p(HGNC:A, location(GOCC:"cell membrane")) -> p(HGNC:B)`

.. seealso::

    BEL 2.0 specification on `cellular location (2.2.4) <http://openbel.org/language/web/version_2.0/bel_specification_version_2.0.html#_cellular_location>`_
"""

from pyparsing import Suppress, oneOf, Group

from ..baseparser import BaseParser, nest
from ..parse_identifier import IdentifierParser
from ...constants import LOCATION

location_tag = Suppress(oneOf(['loc', 'location']))


class LocationParser(BaseParser):
    def __init__(self, identifier_parser=None):
        """
        :param identifier_parser:
        :type identifier_parser: IdentifierParser
        :return:
        """
        self.identifier_parser = identifier_parser if identifier_parser is not None else IdentifierParser()
        identifier = self.identifier_parser.get_language()

        self.language = Group(location_tag + nest(identifier))(LOCATION)

    def get_language(self):
        return self.language
