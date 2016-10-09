import logging
import re

log = logging.getLogger(__name__)

re_match_bel_header = re.compile("(SET\s+DOCUMENT|DEFINE\s+NAMESPACE|DEFINE\s+ANNOTATION)")


def sanitize_file_lines(f):
    it = map(str.strip, f)
    it = filter(lambda i_l: i_l[1] and not i_l[1].startswith('#'), enumerate(it))
    it = iter(it)

    for line_number, line in it:
        if line.endswith('\\'):
            log.debug('Multiline quote starting on line:{}'.format(line_number))
            line = line.strip('\\').strip()
            next_line_number, next_line = next(it)
            while next_line.endswith('\\'):
                log.log(5, 'Extending line: {}'.format(next_line))
                line += " " + next_line.strip('\\').strip()
                next_line_number, next_line = next(it)
            line += " " + next_line.strip()
            log.debug('Final line: {}'.format(line))

        elif 1 == line.count('"'):
            log.debug('PyBEL013 Missing new line escapes [line:{}]'.format(line_number))
            next_line_number, next_line = next(it)
            next_line = next_line.strip()
            while not next_line.endswith('"'):
                log.log(5, 'Extending line: {}'.format(next_line))
                line = '{} {}'.format(line.strip(), next_line)
                next_line_number, next_line = next(it)
                next_line = next_line.strip()
            line = '{} {}'.format(line, next_line)
            log.debug('Final line: {}'.format(line))

        comment_loc = line.rfind(' //')
        if 0 <= comment_loc:
            line = line[:comment_loc]

        yield line


def split_file_to_annotations_and_definitions(file):
    content = list(sanitize_file_lines(file))

    end_document_section = 1 + max(i for i, l in enumerate(content) if l.startswith('SET DOCUMENT'))
    end_definitions_section = 1 + max(i for i, l in enumerate(content) if re_match_bel_header.match(l))

    log.info('File length: {} lines'.format(len(content)))
    documents = content[:end_document_section]
    definitions = content[end_document_section:end_definitions_section]
    statements = content[end_definitions_section:]

    return documents, definitions, statements


def subitergroup(iterable, key):
    poss = (i for i, v in enumerate(iterable) if key(v))
    res = []
    last = next(poss)
    for pos in poss:
        k = iterable[last]
        z = iterable[last + 1:pos]
        last = pos
        res.append((k, z))
    res.append((iterable[last], iterable[last + 1:]))
    return res


def check_stability(ns_dict, ns_mapping):
    """
    Check the stability of namespace mapping
    :param ns_dict: dict of {name: set of values}
    :param ns_mapping: dict of {name: {value: (other_name, other_value)}}
    :return: if the mapping is stable
    :rtype: Boolean
    """
    flag = True
    for ns, kv in ns_mapping.items():
        if ns not in ns_dict:
            log.warning('missing namespace {}'.format(ns))
            flag = False
        for k, (k_ns, v_val) in kv.items():
            if k not in ns_dict[ns]:
                log.warning('missing value {}'.format(k))
                flag = False
            if k_ns not in ns_dict:
                log.warning('missing namespace link {}'.format(k_ns))
                flag = False
            if v_val not in ns_dict[k_ns]:
                log.warning('missing value {} in namespace {}'.format(v_val, k_ns))
                flag = False
    return flag


def list2tuple(l):
    if not isinstance(l, list):
        return l
    else:
        return tuple(list2tuple(e) for e in l)


def subdict_matches(a, b):
    """
    Checks if all the keys in b are in a, and that their values match
    :param a: a dictionary
    :type a: dict
    :param b: a dictionary
    :type b: dict
    :return:
    """
    for k, v in b.items():
        if k not in a or a[k] != v:
            return False
    return True


def any_subdict_matches(a, b):
    """
    Checks that dictionary b matches one of the subdictionaries of a
    :param a: dictionary of dictionaries
    :param b: dictionary
    :return:
    """
    return any(subdict_matches(sd, b) for sd in a.values())

