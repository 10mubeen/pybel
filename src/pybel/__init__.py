"""Parsing, validation, and analysis of of BEL graphs"""

import os
from pkg_resources import iter_entry_points
import types
import warnings

from . import cli
from . import graph
from .constants import LARGE_CORPUS_URL, SMALL_CORPUS_URL, PYBEL_DIR
from .graph import *
from .manager.graph_cache import to_database, from_database

__all__ = ['SMALL_CORPUS_URL', 'LARGE_CORPUS_URL', 'to_database', 'from_database'] + graph.__all__

__version__ = '0.3.2-dev'

__title__ = 'PyBEL'
__description__ = 'Parsing, validation, and analysis of BEL graphs'
__url__ = 'https://github.com/pybel/pybel'

__author__ = 'Charles Tapley Hoyt, Andrej Konotopez, Christian Ebeling'
__email__ = 'charles.hoyt@scai.fraunhofer.de'

__license__ = 'Apache 2.0 License'
__copyright__ = 'Copyright (c) 2016 Charles Tapley Hoyt, Andrej Konotopez, Christian Ebeling'

ext = types.ModuleType('ext', 'PyBEL extensions')
for entry_point in iter_entry_points(group='pybel.ext', name=None):
    name = entry_point.name
    if name in ext.__dict__:
        warnings.warn('An extension named `{}` has already been imported. Alert the author of `{}` about this collision.'.format(name, entry_point.module_name))
    else:
        ext.__dict__[name] = entry_point.load()


def get_large_corpus(force_reload=False, **kwargs):
    """Gets the example large corpus"""
    path = os.path.join(PYBEL_DIR, 'large_corpus.gpickle')
    if os.path.exists(path) and not force_reload:
        return from_pickle(path)
    g = from_url(LARGE_CORPUS_URL, **kwargs)
    to_pickle(g, path)
    return g


def get_small_corpus(force_reload=False, **kwargs):
    """Gets the example small corpus"""
    path = os.path.join(PYBEL_DIR, 'small_corpus.gpickle')
    if os.path.exists(path) and not force_reload:
        return from_pickle(path)
    g = from_url(SMALL_CORPUS_URL, **kwargs)
    to_pickle(g, path)
    return g
