# -*- coding: utf-8 -*-

"""TSV conversion."""

import logging
from typing import List, Optional, TextIO, Tuple, Union

from networkx.utils import open_file
from tqdm import tqdm

from .converters import (
    AssociationConverter, CorrelationConverter, DecreasesAmountConverter, DrugIndicationConverter,
    DrugSideEffectConverter, EquivalenceConverter, IncreasesAmountConverter, IsAConverter,
    ListComplexHasComponentConverter, MiRNADecreasesExpressionConverter, MiRNADirectlyDecreasesExpressionConverter,
    NamedComplexHasComponentConverter, PartOfNamedComplexConverter, ProteinPartOfBiologicalProcess,
    RegulatesActivityConverter, RegulatesAmountConverter, SubprocessPartOfBiologicalProcess,
)
from ...dsl import BaseEntity
from ...struct import BELGraph

__all__ = [
    'to_tsv',
    'get_triples',
    'get_triple',
]

logger = logging.getLogger(__name__)


@open_file(1, mode='w')
def to_tsv(graph: BELGraph, path: Union[str, TextIO], *, use_tqdm: bool = True, sep='\t') -> None:
    """Write the graph as a TSV.

    :param graph: A BEL graph
    :param path: A path or file-like
    :param use_tqdm: Should a progress bar be shown?
    :param sep: The separator to use
    """
    for h, r, t in get_triples(graph, use_tqdm=use_tqdm):
        print(h, r, t, sep=sep, file=path)


def get_triples(graph: BELGraph, use_tqdm: bool = True) -> List[Tuple[str, str, str]]:
    """Get a non-redundant list of triples representing the graph.

    :param graph: A BEL graph
    :param use_tqdm: Should a progress bar be shown?
    """
    it = graph.edges(keys=True)

    if use_tqdm:
        it = tqdm(it, total=graph.number_of_edges(), desc=f'Preparing TSV')

    triples = (
        get_triple(graph, u, v, key)
        for u, v, key in it
    )

    # clean duplicates and Nones
    return list(sorted({
        triple
        for triple in triples
        if triple is not None
    }))


def get_triple(
    graph: BELGraph,
    u: BaseEntity,
    v: BaseEntity,
    key: str,
) -> Optional[Tuple[str, str, str]]:  # noqa: C901
    """Get the triples' strings that should be written to the file."""
    data = graph[u][v][key]

    # order is important
    converters = [
        NamedComplexHasComponentConverter,
        ListComplexHasComponentConverter,
        PartOfNamedComplexConverter,
        SubprocessPartOfBiologicalProcess,
        ProteinPartOfBiologicalProcess,
        RegulatesActivityConverter,
        MiRNADecreasesExpressionConverter,
        MiRNADirectlyDecreasesExpressionConverter,
        IsAConverter,
        EquivalenceConverter,
        CorrelationConverter,
        AssociationConverter,
        DrugIndicationConverter,
        DrugSideEffectConverter,
        RegulatesAmountConverter,
        IncreasesAmountConverter,
        DecreasesAmountConverter,
    ]

    for converter in converters:
        if converter.predicate(u, v, key, data):
            return converter.convert(u, v, key, data)

    logger.warning('unhandled: {}'.format(graph.edge_to_bel(u, v, data)))
