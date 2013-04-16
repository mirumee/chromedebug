import contextlib
from functools import wraps
import inspect
import sys
import time


_uid = 0
profilers = []
current_profiler = None


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

    def trace_call(self, func_name, url, line_num):
        callee = func_name, url, line_num
        if not self.path:
            if not callee in self.children:
                self.children[callee] = Trace(func_name, url, line_num,
                                              profiler=self)
            tracer = self.children[callee]
        else:
            tracer = self.path[-1].add_child(func_name, url, line_num)
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

    def trace(self, frame, event, arg):
        if event == 'call':
            if self._is_own_frame(frame):
                return
            filename = inspect.getsourcefile(frame)
            self.trace_call(frame.f_code.co_name, filename, frame.f_lineno)
            return self.handle_return


class Trace(object):
    children = None

    def __init__(self, func_name, url, line_num, profiler):
        self.func_name, self.url, self.line_num = func_name, url, line_num
        self.profiler = profiler
        self.children = {}
        self.total_time = 0
        self.id = profiler.generate_id()

    def encode(self):
        return {
            'functionName': self.func_name,
            'url': self.url,
            'lineNumber': self.line_num,
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

    def add_child(self, func_name, url, line_num):
        callee = func_name, url, line_num
        if not callee in self.children:
            self.children[callee] = Trace(func_name, url, line_num,
                                          profiler=self.profiler)
        return self.children[callee]

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


def _get_timestamp():
    return time.time() * 1000.0
