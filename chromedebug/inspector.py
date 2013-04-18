# coding: utf-8

from collections import defaultdict
import types


properties = {}
groups = defaultdict(set)


def inspect(obj):
    if isinstance(obj, dict):
        return obj.iteritems()
    if hasattr(obj, '__dict__'):
        if hasattr(obj, '__getstate__'):
            return inspect(obj.__getstate__())
        return obj.__dict__.iteritems()
    if hasattr(obj, '__slots__'):
        return ((k, getattr(obj, k)) for k in obj.__slots__)
    return []


def get_properties(object_id):
    return properties.get(object_id, [])


def save_properties(obj, group):
    object_id = str(id(obj))
    if object_id in properties:
        return object_id
    props = []
    for k, v in inspect(obj):
        props.append(
            {'name': k, 'value': encode(v, group=group),
             'configurable': False, 'enumerable': True, 'wasThrown': False,
             'writable': False})
    if props:
        properties[object_id] = props
        if group:
            groups[group].add(object_id)
        return object_id


def encode(obj, group=None, preview=True):
    klass = type(obj).__name__
    if isinstance(obj, bool):
        typ = 'boolean'
    elif isinstance(obj, (float, int)):
        typ = 'number'
    elif isinstance(obj, (list, tuple)):
        typ = 'array'
    elif isinstance(obj, (str, unicode)):
        typ = 'string'
    elif isinstance(obj, (types.FunctionType, types.MethodType,
                          types.UnboundMethodType)):
        typ = 'function'
    elif isinstance(obj, types.NoneType):
        typ = 'undefined'
    else:
        typ = 'object'
    value = (
        None if typ == 'object' else
        repr(obj) if typ != 'string' else obj)
    description = repr(obj) if typ != 'string' else obj
    if len(description) > 50:
        description = description[:49] + u'…'
    data = {'className': klass, 'type': typ, 'value': value}
    if preview:
        data['description'] = description
    if typ == 'object' and not isinstance(obj, types.ModuleType):
        object_id = save_properties(obj, group=group)
        if object_id:
            data['objectId'] = object_id
    return data


def release_group(group):
    if group in groups:
        for object_id in groups[group]:
            del properties[object_id]
        del groups[group]
