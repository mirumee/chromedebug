import types

properties = {}


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


def save_properties(obj):
    object_id = str(id(obj))
    if object_id in properties:
        return object_id
    props = []
    for k, v in inspect(obj):
        props.append(
            {'name': k, 'value': encode(v),
             'configurable': False, 'enumerable': True, 'wasThrown': False,
             'writable': False})
    if props:
        properties[object_id] = props
        return object_id


def encode(obj):
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
    description = repr(obj) if typ != 'string' else obj
    data = {'className': klass, 'description': description, 'type': typ,
            'value': description}
    if typ == 'object':
        object_id = save_properties(obj)
        if object_id:
            data['objectId'] = object_id
    return data
