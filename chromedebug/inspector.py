from collections import defaultdict
import types
import weakref


properties = {}
groups = defaultdict(set)


def inspect(obj):
    if isinstance(obj, dict):
        return obj.iteritems()
    if hasattr(obj, '__dict__'):
        if not isinstance(obj, type):
            if hasattr(obj, '__getstate__'):
                return inspect(obj.__getstate__())
        return obj.__dict__.iteritems()
    if hasattr(obj, '__slots__'):
        return ((k, getattr(obj, k)) for k in obj.__slots__)
    return []


def extract_properties(obj):
    props = []
    for k, v in inspect(obj):
        props.append(
            {'name': k, 'value': encode(v),
             'configurable': False, 'enumerable': True, 'wasThrown': False,
             'writable': False})
    return props


def get_properties(object_id):
    try:
        object_id = int(object_id)
        obj = properties[object_id]
    except Exception:
        return None
    if isinstance(obj, weakref.ref):
        obj = obj()
        return extract_properties(obj)
    return obj


def save_properties(obj, force=True):
    object_id = id(obj)
    if object_id in properties:
        return str(object_id)
    try:
        data = weakref.ref(obj)
    except:
        data = None
    if force or data is None:
        data = extract_properties(obj)
    properties[object_id] = data
    return str(object_id)


def encode(obj, preview=True):
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
        obj if typ == 'boolean' else
        repr(obj) if typ != 'string' else obj)
    description = repr(obj) if typ != 'string' else obj
    if len(description) > 50:
        description = description[:49] + '[...]'
    data = {'className': klass, 'type': typ, 'value': value}
    if preview:
        data['description'] = description
    data['objectId'] = None
    if typ in ['object', 'function'] and not isinstance(obj, types.ModuleType):
        object_id = save_properties(obj)
        if object_id:
            data['objectId'] = object_id
    return data


def release_group(group):
    if group in groups:
        for object_id in groups[group]:
            del properties[object_id]
        del groups[group]
