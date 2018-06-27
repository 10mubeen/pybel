# -*- coding: utf-8 -*-

"""This module contains the functions for decorating transformation functions.

A transformation function takes in a :class:`pybel.BELGraph` and either returns None (in-place) or a new
:class:`pybel.BELGraph` (out-of-place).
"""

import logging

from .exc import MissingPipelineFunctionError

try:
    from inspect import signature
except ImportError:
    from funcsigs import signature

__all__ = [
    'in_place_transformation',
    'uni_in_place_transformation',
    'uni_transformation',
    'transformation',
    'get_transformation',
    'mapped',
    'has_arguments_map',
    'no_arguments_map',
]

log = logging.getLogger(__name__)

mapped = {}
universe_map = {}
in_place_map = {}
has_arguments_map = {}
no_arguments_map = {}
deprecated = set()


def _has_arguments(func, universe):
    sig = signature(func)
    return (
            (universe and 3 <= len(sig.parameters)) or
            (not universe and 2 <= len(sig.parameters))
    )


def _register_function(name, func, universe, in_place):
    """Register a transformation function under the given name.

    :param str name: Name to register the function under
    :param func: A function
    :param bool universe:
    param bool in_place:
    :return: The same function, with additional properties added
    """
    if name in mapped:
        raise ValueError('can not re-map {}'.format(name))

    mapped[name] = func

    if universe:
        universe_map[name] = func

    if in_place:
        in_place_map[name] = func

    if _has_arguments(func, universe):
        has_arguments_map[name] = func
    else:
        no_arguments_map[name] = func

    return func


def _build_register_function(universe, in_place):
    """Build a decorator function to tag transformation functions.

    :param bool universe: Does the first positional argument of this function correspond to a universe graph?
    :param bool in_place: Does this function return a new graph, or just modify it in-place?
    """

    def register(func):
        """Tag a transformation function.

        :param func: A function
        :return: The same function, with additional properties added
        """
        return _register_function(func.__name__, func, universe, in_place)

    return register


#: A function decorator to inform the Pipeline how to handle a function
in_place_transformation = _build_register_function(universe=False, in_place=True)
#: A function decorator to inform the Pipeline how to handle a function
uni_in_place_transformation = _build_register_function(universe=True, in_place=True)
#: A function decorator to inform the Pipeline how to handle a function
uni_transformation = _build_register_function(universe=True, in_place=False)
#: A function decorator to inform the Pipeline how to handle a function
transformation = _build_register_function(universe=False, in_place=False)


class DeprecationMappingError(ValueError):
    pass


class MissingMappingError(ValueError):
    pass


def register_deprecated(deprecated_name):
    """Register a function as deprecated.

    :param str deprecated_name: The old name of the function
    :return: A decorator

    Usage:

    This function must be applied last, since it introspects on the definitions from before

    .. code-block::

        @register_deprecated('my_function')
        @transformation
        def my_old_function()
            pass
    """
    if deprecated_name in mapped:
        raise DeprecationMappingError('function name already mapped. can not register as deprecated name.')

    def register_deprecated_f(func):
        name = func.__name__

        log.warning('%s is deprecated. please migrate to %s', deprecated_name, name)

        if name not in mapped:
            raise MissingMappingError('function not mapped with transformation, uni_transformation, etc.')

        universe = name in universe_map
        in_place = name in in_place_map

        deprecated.add(deprecated_name)

        return _register_function(deprecated_name, func, universe, in_place)

    return register_deprecated_f


def get_transformation(name):
    """Get a transformation function and error if its name is not registered.

    :param str name:
    :return: A transformation function
    :raises: MissingPipelineFunctionError
    """
    func = mapped.get(name)

    if func is None:
        raise MissingPipelineFunctionError('{} is not registered as a pipeline function'.format(name))

    return func
