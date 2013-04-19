import inspect
import time

from . import debugger


_uid = 0
profilers = []
current_profiler = None


class Profiler(object):

    def __init__(self, title):
        global _uid
        _uid += 1
        self.uid = _uid
        self.title = title
        self.children = {}
        self.samples = []
        self.start_time = _get_timestamp()
        self.duration = None
        self.path = []
        self._id = 1

    def _is_own_frame(self, frame):
        if not inspect:  # terminating
            return True
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

    def trace_return(self):
        if self.path:
            self.path[-1].trace_return()
            self.path.pop()

    def generate_id(self):
        self._id += 1
        return self._id

    def get_profile(self):
        if not self.duration:
            self.duration = _get_timestamp() - self.start_time
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


class Trace(object):
    children = None
    in_call = False
    num_calls = 0

    def __init__(self, call_info, profiler):
        self.call_info = call_info
        self.profiler = profiler
        self.children = {}
        self.total_time = 0
        self.id = profiler.generate_id()

    def encode(self):
        function = self.call_info.function
        if self.in_call:
            function += ' (did not return)'
        return {
            'functionName': function,
            'url': self.call_info.module,
            'lineNumber': self.call_info.lineno,
            'totalTime': self.total_time,
            'selfTime': self.total_time - self.get_children_duration(),
            'numberOfCalls': self.num_calls,
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
        self.in_call = True
        self.num_calls += 1
        self.start_time = _get_timestamp()

    def trace_return(self):
        self.in_call = False
        self.total_time += _get_timestamp() - self.start_time


def start_profiling(name=None):
    next_num = _uid + 1
    name = name or 'Python %d' % (next_num,)
    global current_profiler
    current_profiler = Profiler(name)
    profilers.append(current_profiler)
    debugger.attach_profiler(current_profiler)


def stop_profiling():
    global current_profiler
    debugger.detach_profiler(current_profiler)
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
    if not time:  # terminating
        return 0
    return time.time() * 1000.0
