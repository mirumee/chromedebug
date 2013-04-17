from collections import namedtuple
import contextlib
from functools import wraps
import inspect
import sys
import time


_uid = 0
profilers = []
current_profiler = None

CallInfo = namedtuple('CallInfo', ['function', 'module', 'lineno'])


def traced(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        if not current_profiler:
            return func(*args, **kwargs)
        with current_profiler:
            return func(*args, **kwargs)
    return wrapped


@contextlib.contextmanager
def tracer():
    if current_profiler:
        with current_profiler:
            yield
    else:
        yield


class Profiler(object):

    def __init__(self, title):
        global _uid
        _uid += 1
        self.uid = _uid
        self.title = title
        self.children = {}
        self.samples = []
        self.start_time = time.time()
        self.duration = None
        self.path = []
        self._id = 1

    def __enter__(self):
        self._old_trace = sys.gettrace()
        sys.settrace(self.trace)

    def __exit__(self, ext_type, exc_value, exc_tb):
        sys.settrace(self._old_trace)

    def _is_own_frame(self, frame):
        filename = inspect.getsourcefile(frame)
        # skip self
        filename_base = filename.rsplit('.', 1)[0]
        local_base = __file__.rsplit('.', 1)[0]
        if filename_base == local_base:
            return True
        return False

    def trace_call(self, call_info):
        if not self.path:
            if not call_info in self.children:
                self.children[call_info] = Trace(call_info, profiler=self)
            tracer = self.children[call_info]
        else:
            tracer = self.path[-1].add_child(call_info)
        self.samples.append(tracer.id)
        tracer.trace_call()
        self.path.append(tracer)

    def trace_return(self, frame, event, arg):
        if self.path:
            self.path[-1].trace_return()
        self.path.pop()

    def generate_id(self):
        self._id += 1
        return self._id

    def get_profile(self):
        if not self.duration:
            self.duration = (time.time() - self.start_time) * 1000
        return {
            'head': {
                'functionName': '(root)',
                'url': '',
                'lineNumber': 0,
                'totalTime': self.duration,
                'selfTime': 0,
                'numberOfCalls': 0,
                'visible': True,
                'callUID': id(self),
                'children': [c.encode() for c in self.children.values()],
                'id': 1},
            'idleTime': self.duration - self.get_children_duration(),
            'samples': self.samples}

    def get_header(self):
        return {'typeId': 'CPU', 'uid': self.uid, 'title': self.title}

    def get_children_duration(self):
        return sum(c.total_time for c in self.children.values())

    def handle_return(self, frame, event, arg):
        if event == 'return':
            self.trace_return(frame, event, arg)

    def _get_call_info(self, frame):
            info = inspect.getframeinfo(frame)
            values = inspect.getargvalues(frame)
            function = info.function
            if values.args and values.args[0] == 'self':
                klass = type(values.locals[values.args[0]])
                function = '%s.%s' % (klass.__name__, function)
            elif function == '__new__' and values.args:
                klass = values.locals[values.args[0]]
                if isinstance(klass, type):
                    function = '%s.%s' % (klass.__name__, function)
            module = inspect.getmodule(frame).__name__
            return CallInfo(function, module, info.lineno)

    def trace(self, frame, event, arg):
        if event == 'call':
            if self._is_own_frame(frame):
                return
            call_info = self._get_call_info(frame)
            self.trace_call(call_info)
            return self.handle_return


class Trace(object):
    children = None

    def __init__(self, call_info, profiler):
        self.call_info = call_info
        self.profiler = profiler
        self.children = {}
        self.total_time = 0
        self.id = profiler.generate_id()

    def encode(self):
        return {
            'functionName': self.call_info.function,
            'url': self.call_info.module,
            'lineNumber': self.call_info.lineno,
            'totalTime': self.total_time,
            'selfTime': self.total_time - self.get_children_duration(),
            'numberOfCalls': 0,
            'visible': True,
            'callUID': id(self),
            'children': [c.encode() for c in self.children.values()],
            'id': self.id}

    def get_samples(self):
        return sum((c.get_samples() for c in self.children.values()), [id(self)])

    def get_children_duration(self):
        return sum(c.total_time for c in self.children.values())

    def add_child(self, call_info):
        if not call_info in self.children:
            self.children[call_info] = Trace(call_info, profiler=self.profiler)
        return self.children[call_info]

    def trace_call(self):
        self.start_time = time.time()

    def trace_return(self):
        self.total_time += (time.time() - self.start_time) * 1000


def start_profiling(name=None):
    next_num = _uid + 1
    name = name or 'Python %d' % (next_num,)
    global current_profiler
    current_profiler = Profiler(name)
    profilers.append(current_profiler)


def stop_profiling():
    global current_profiler
    header = current_profiler.get_header()
    current_profiler = None
    return header


def get_profile(uid):
    ps = [p for p in profilers if p.uid == uid]
    if ps:
        return ps[0].get_profile()


def get_profile_headers():
    return [p.get_header() for p in profilers if p != current_profiler]


def _get_timestamp():
    return time.time() * 1000.0
