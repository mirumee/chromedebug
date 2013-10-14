from collections import defaultdict, namedtuple
import types
import weakref


properties = {}
groups = defaultdict(list)


Property = namedtuple('Property', 'name value bound enumerable descriptor')


def inspect(obj):
    if isinstance(obj, (frozenset, list, set, tuple)):
        for i, v in enumerate(obj):
            yield Property(unicode(i), v, True, False, False)
    elif isinstance(obj, dict):
        for k, v in obj.iteritems():
            yield Property(k, v, True, False, False)
    else:
        if hasattr(obj, '__slots__'):
            for k in obj.__slots__:
                if not k.startswith('_'):
                    yield Property(k, getattr(obj, k), True, True, False)
        if hasattr(obj, '__dict__'):
            for k, v in obj.__dict__.iteritems():
                if not k.startswith('_'):
                    yield Property(k, v, True, True, False)
        if isinstance(obj, object):
            for k, v in type(obj).__dict__.iteritems():
                if k.startswith('_'):
                    continue
                if hasattr(obj, '__dict__') and k in obj.__dict__:
                    continue
                if hasattr(obj, '__slots__') and k in obj.__slots__:
                    continue
                if isinstance(v, property):
                    yield Property(k, v, False, True, True)
                else:
                    yield Property(k, v, False, True, False)


def extract_properties(obj, accessors=False):
    for prop in inspect(obj):
        if bool(accessors) != bool(prop.descriptor):
            continue
        data = {'name': prop.name,
                'configurable': False,
                'enumerable': prop.enumerable,
                'wasThrown': False,
                'isOwn': prop.bound}
        if prop.descriptor:
            if prop.value.getter:
                data['get'] = encode(prop.value.fget)
            if prop.value.setter:
                data['set'] = encode(prop.value.fset)
            data['writable'] = prop.value.fset is not None
        else:
            data['value'] = encode(prop.value)
        yield data


def get_object(object_id):
    try:
        object_id = int(object_id)
        obj = properties[object_id]
    except Exception:
        return []
    if isinstance(obj, weakref.ref):
        obj = obj()
    return obj


def get_function_details(object_id):
    try:
        object_id = int(object_id)
        obj = properties[object_id]
    except Exception:
        return None
    if isinstance(obj, weakref.ref):
        obj = obj()
        code = obj.func_code
        return {
            'location': {'scriptId': obj.__module__,
                         'lineNumber': code.co_firstlineno - 1},
            'name': code.co_name,
            'displayName': obj.__name__}


def add_obj_to_group(obj, group):
    if not obj in groups[group]:
        groups[group].append(obj)
    save_properties(obj)


def save_properties(obj):
    object_id = id(obj)
    if object_id in properties:
        return str(object_id)
    try:
        data = weakref.ref(obj)
    except:
        data = obj
    properties[object_id] = data
    return str(object_id)


def get_type(obj):
    if isinstance(obj, bool):
        return 'boolean'
    elif isinstance(obj, (float, int)):
        return 'number'
    elif isinstance(obj, (str, unicode)):
        return 'string'
    elif isinstance(obj, (types.FunctionType, types.MethodType,
                          types.UnboundMethodType, classmethod, staticmethod)):
        return 'function'
    else:
        return 'object'


def get_subtype(obj):
    if isinstance(obj, (dict, frozenset, list, set, tuple)):
        return 'array'
    elif isinstance(obj, types.NoneType):
        return 'null'


def encode_property(prop):
    typ = get_type(prop.value)
    subtype = get_subtype(prop.value)
    data = {'name': prop.name, 'type': typ}
    if subtype:
        data['subtype'] = subtype
    if typ in ['boolean', 'number', 'string']:
        data['value'] = unicode(prop.value)
    else:
        data['valuePreview'] = repr(prop.value)
    return data


def preview_array(obj):
    preview = {'lossless': True}
    props = list(inspect(obj))[:11]
    if len(props) > 10:
        preview['overflow'] = True
        props = props[:10]
    else:
        preview['overflow'] = False
    preview['properties'] = [encode_property(prop) for prop in props]
    return preview


def encode_array(obj, preview=False, by_value=False):
    data = {}
    data['objectId'] = save_properties(obj)
    data['description'] = '%s() [%d]' % (type(obj).__name__, len(obj))
    if preview:
        data['preview'] = preview_array(obj)
    return data


def encode_function(obj, preview=False, by_value=False):
    data = {}
    data['objectId'] = save_properties(obj)
    prefix = ''
    if isinstance(obj, classmethod):
        prefix = '@classmethod '
        obj = obj.__func__
    if isinstance(obj, staticmethod):
        prefix = '@staticmethod '
        obj = obj.__func__
    if hasattr(obj, 'im_func'):
        obj = obj.im_func
    data['description'] = u'%(prefix)sdef %(name)s(%(params)s):' % {
        'prefix': prefix,
        'name': obj.__name__,
        'params': ', '.join(obj.func_code.co_varnames)
    }
    return data


def encode_none(obj, preview=False, by_value=False):
    return {'value': None, 'description': 'None'}


def encode_object(obj, preview=False, by_value=False):
    data = {}
    data['objectId'] = save_properties(obj)
    data['className'] = type(obj).__name__
    data['description'] = repr(obj)
    return data


def encode_value(obj, preview=False, by_value=False):
    return {'value': obj}


ENCODERS = [
    ('boolean', None, encode_value),
    ('function', None, encode_function),
    ('number', None, encode_value),
    ('object', 'array', encode_array),
    ('object', 'null', encode_none),
    ('object', None, encode_object),
    ('string', None, encode_value)]


def encode(obj, preview=False, by_value=False):
    data = {}
    typ = get_type(obj)
    subtype = get_subtype(obj)
    data['type'] = typ
    if subtype:
        data['subtype'] = subtype
    if by_value and isinstance(obj, dict):
            data['value'] = obj
    for data_type, data_subtype, encoder in ENCODERS:
        if typ == data_type and subtype == data_subtype:
            specialized = encoder(obj, preview=preview, by_value=by_value)
            data.update(specialized)
    return data


def release_group(group):
    if group in groups:
        for object_id in groups[group]:
            if object_id in properties:
                if not isinstance(properties[object_id], weakref.ref):
                    del properties[object_id]
        del groups[group]
