import atexit
from collections import defaultdict, namedtuple
import fnmatch
import inspect
import sys
import threading

from . import inspector
from . import profiler
from . import thread

seen = set()

CallInfo = namedtuple('CallInfo', ['function', 'module', 'lineno'])
debug_lock = threading.Lock()


def get_call_info(frame):
    if not inspect:  # terminating
        return
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
    module = inspect.getmodule(frame)
    if module:
        module = module.__name__
    else:
        module = '(unknown)'
    return CallInfo(function, module, info.lineno)


class Debugger(object):

    current_frame = None
    stop_module = None
    stop_lineno = None

    def __init__(self, skip=None):
        self.resume = threading.Event()
        self.skip = set(skip) if skip else None
        self.breaks = defaultdict(set)
        self.fncache = {}

    def trace_dispatch(self, frame, event, arg):
        if event == 'line':
            return self.dispatch_line(frame)
        if event == 'call':
            return self.dispatch_call(frame, arg)
        if event == 'return':
            return self.dispatch_return(frame, arg)
        if event == 'exception':
            return self.dispatch_exception(frame, arg)
        if event == 'c_call':
            return self.trace_dispatch
        if event == 'c_exception':
            return self.trace_dispatch
        if event == 'c_return':
            return self.trace_dispatch
        return self.trace_dispatch

    def dispatch_line(self, frame):
        if self.stop_here(frame) or self.break_here(frame):
            self.user_line(frame)
        return self.trace_dispatch

    def dispatch_call(self, frame, arg):
        if (self.skip and
                self.is_skipped(frame)):
            return
        call_info = get_call_info(frame)
        if not profiler:  # terminating
            return
        profiler.profile_call(call_info)
        return self.trace_dispatch

    def dispatch_return(self, frame, arg):
        profiler.profile_return()
        return self.trace_dispatch

    def dispatch_exception(self, frame, arg):
        return self.trace_dispatch

    def is_skipped(self, frame):
        if not fnmatch:
            return True
        while frame:
            module = frame.f_globals.get('__name__')
            for pattern in self.skip:
                if fnmatch.fnmatch(module, pattern):
                    return True
            frame = frame.f_back
        return False

    def stop_here(self, frame):
        if self.stop_module:
            print self.stop_module, frame.f_code.co_name
        mod = inspect.getmodule(frame)
        if not mod:
            return False
        module = mod.__name__
        if module == self.stop_module:
            if frame.f_lineno >= self.stop_lineno:
                return True
        return False

    def break_here(self, frame):
        if not inspect:
            return False
        mod = inspect.getmodule(frame)
        if not mod:
            return False
        module = mod.__name__
        if not module in self.breaks:
            return False
        lineno = frame.f_lineno
        if not lineno in self.breaks[module]:
            return False
        return True

    def break_anywhere(self, frame):
        if not inspect:
            return False
        mod = inspect.getmodule(frame)
        if not mod:
            return False
        module = mod.__name__
        return module in self.breaks

    def _extract_frames(self, frame):
        info = get_call_info(frame)
        location = {
            'scriptId': info.module,
            'lineNumber': info.lineno - 1}
        scope_chain = [
            {'type': 'local',
             'object': inspector.encode(frame.f_locals, preview=False)},
            {'type': 'global',
             'object': inspector.encode(frame.f_globals, preview=False)}]
        frame_id = str(id(frame))
        frames = [{
            'callFrameId': frame_id,
            'functionName': info.function,
            'location': location,
            'scopeChain': scope_chain}]
        if frame.f_back:
            frames += self._extract_frames(frame.f_back)
        return frames

    def evaluate_on_frame(self, frame_id, expression):
        frame = self.current_frame
        while frame and str(id(frame)) != frame_id:
            frame = frame.f_back
        if not frame:
            return None
        return eval(expression, frame.f_globals, frame.f_locals)

    def get_pause_info(self):
        if not self.current_frame:
            return
        frames = self._extract_frames(self.current_frame)
        return {'callFrames': frames, 'reason': 'other'}

    def pause(self, frame):
        if not thread or not threading:  # terminating
            return
        if threading.current_thread().name == 'ChromeDebug':
            return
        with debug_lock:
            if self.current_frame:
                return
            self.current_frame = frame
        self.resume.clear()
        info = self.get_pause_info()
        thread.debugger_paused(info)
        self.resume.wait()
        self.set_continue()
        with debug_lock:
            self.current_frame = None

    def user_line(self, frame):
        """This method is called when we stop or break at this line."""
        self.pause(frame)

    def set_continue(self):
        self.stop_module = None
        self.stop_lineno = None

    def set_break(self, module, lineno):
        self.breaks[module].add(lineno)

    def continue_to(self, module, lineno):
        self.stop_module = module
        self.stop_lineno = lineno

    def clear_break(self, module, lineno):
        if module in self.breaks:
            if lineno in self.breaks[module]:
                self.breaks[module].remove(lineno)
        if not self.breaks[module]:
            del self.breaks[module]


class ImportLoader(object):

    def load_module(self, full_name):
        module = sys.modules[full_name]
        if module and not module in seen:
            seen.add(full_name)
            if thread:  # terminating?
                thread.debugger_script_parsed(full_name)
        return module


class ImportFinder(object):

    touched = None

    def __init__(self):
        self.touched = set()

    def find_module(self, full_name, path=None):
        if full_name in self.touched:
            return
        self.touched.add(full_name)
        try:
            __import__(full_name)
        finally:
            self.touched.remove(full_name)
        return ImportLoader()


def get_script_source(scriptId):
    module = sys.modules.get(scriptId)
    if not module:
        return '"Module not found"'
    try:
        return inspect.getsource(module)
    except IOError:
        return '"Source not available"'
    except TypeError:
        return '"Built-in module"'

debugger = None


def attach():
    global debugger
    sys.meta_path.insert(0, ImportFinder())
    for name, module in sys.modules.iteritems():
        if module:
            seen.add(name)
    debugger = Debugger(skip=['chromedebug', 'chromedebug.*', 'ws4py.*'])
    sys.settrace(debugger.trace_dispatch)
    threading.settrace(debugger.trace_dispatch)


def detach():
    sys.settrace(None)
    threading.settrace(None)
atexit.register(detach)


def add_breakpoint(url, lineno):
    if not debugger:
        return
    debugger.set_break(url, lineno + 1)
    return {
        'breakpointId': '%s:%s' % (url, lineno),
        'locations': [{'scriptId': url, 'lineNumber': lineno}]}


def evaluate_on_frame(frame_id, expression, group):
    if not debugger:
        return
    try:
        obj = debugger.evaluate_on_frame(frame_id, expression)
        return {'result': inspector.encode(obj, group=group)}
    except Exception, e:
        return {
            'result': inspector.encode(e, group=group),
            'wasThrown': True}


def get_state():
    if not debugger:
        return
    info = debugger.get_pause_info()
    return info


def remove_breakpoint(break_id):
    if not debugger:
        return
    module, lineno = break_id.split(':', 1)
    debugger.clear_break(module, int(lineno) + 1)


def resume():
    if not debugger:
        return
    thread.debugger_resumed()
    debugger.resume.set()


def continue_to(url, lineno):
    if not debugger:
        return
    thread.debugger_resumed()
    debugger.continue_to(url, lineno)
    debugger.resume.set()
