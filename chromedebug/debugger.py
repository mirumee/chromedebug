import atexit
from collections import defaultdict, namedtuple
import fnmatch
from functools import wraps
import inspect
import sys
import threading

from . import inspector
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

    breakpoints_active = True
    profilers = None
    current_frame = None
    step_mode = None
    step_level = 0
    stop_module = None
    stop_lineno = None

    def __init__(self, skip=None):
        self.profilers = set()
        self.resume = threading.Event()
        self.skip = set(skip) if skip else None
        self.breaks = defaultdict(set)
        self.fncache = {}

    def trace_dispatch(self, frame, event, arg):
        if self.skip and self.is_skipped(frame):
            return
        if event == 'line':
            return self.dispatch_line(frame)
        if event == 'call':
            return self.dispatch_call(frame, arg)
        if event == 'return':
            return self.dispatch_return(frame, arg)

    def dispatch_line(self, frame):
        if not self.step_mode:
            if not self.breakpoints_active:
                return
        call_info = get_call_info(frame)
        if not self.step_mode:
            if not call_info.module in self.breaks:
                return
        if self.stop_here(call_info) or self.break_here(call_info):
            self.pause(frame)
        return self.trace_dispatch

    def dispatch_call(self, frame, arg):
        call_info = get_call_info(frame)
        if not self.profilers:
            if not self.step_mode:
                if not self.breakpoints_active:
                    return
                call_info = get_call_info(frame)
                if call_info.module in self.breaks:
                    return
        if self.step_mode in ['over', 'out']:
            self.step_level += 1
        for profiler in self.profilers:
            profiler.trace_call(call_info)
        return self.trace_dispatch

    def dispatch_return(self, frame, arg):
        if self.step_mode in ['over', 'out']:
            self.step_level -= 1
        if self.step_mode == 'out' and self.step_level < 0:
            self.pause(frame)
        for profiler in self.profilers:
            profiler.trace_return()

    def is_skipped(self, frame):
        if not fnmatch:
            return True
        while frame:
            module = frame.f_globals.get('__name__')
            if not module:
                return True
            for pattern in self.skip:
                if fnmatch.fnmatch(module, pattern):
                    return True
            frame = frame.f_back
        return False

    def stop_here(self, call_info):
        if self.step_mode == 'into':
            return True
        if self.step_mode == 'over' and self.step_level <= 0:
            return True
        if self.step_mode == 'out' and self.step_level < 0:
            return True
        if call_info.module == self.stop_module:
            if call_info.lineno >= self.stop_lineno:
                return True
        return False

    def break_here(self, call_info):
        if not call_info.module in self.breaks:
            return False
        if not call_info.lineno in self.breaks[call_info.module]:
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
        if frame.f_back and frame.f_back is not self.source_frame:
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
        if not self.breakpoints_active:
            return
        with debug_lock:
            if self.current_frame:
                return
            self.current_frame = frame
        self.resume.clear()
        info = self.get_pause_info()
        thread.debugger_paused(info)
        self.resume.wait()
        with debug_lock:
            self.current_frame = None

    def set_continue(self):
        self.step_mode = None
        self.stop_module = None
        self.stop_lineno = None
        thread.debugger_resumed()
        self.resume.set()

    def continue_to(self, module, lineno):
        self.step_mode = None
        self.stop_module = module
        self.stop_lineno = lineno
        thread.debugger_resumed()
        self.resume.set()

    def set_step(self, mode):
        self.step_mode = mode
        self.step_level = 0
        self.stop_module = None
        self.stop_lineno = None
        thread.debugger_resumed()
        self.resume.set()

    def set_break(self, module, lineno):
        self.breaks[module].add(lineno)

    def set_breakpoints_active(self, active):
        self.breakpoints_active = active

    def attach_profiler(self, profiler):
        self.profilers.add(profiler)

    def detach_profiler(self, profiler):
        self.profilers.remove(profiler)

    def clear_break(self, module, lineno):
        if module in self.breaks:
            if lineno in self.breaks[module]:
                self.breaks[module].remove(lineno)
        if not self.breaks[module]:
            del self.breaks[module]

    def attach(self):
        try:
            self.source_frame = sys._getframe(3)
        except ValueError:
            self.source_frame = None
        sys.settrace(self.trace_dispatch)

    def detach(self):
        sys.settrace(None)
        self.source_frame = None

    def set_trace(self):
        frame = sys._getframe().f_back
        while frame:
            frame.f_trace = debugger.trace_dispatch
            frame = frame.f_back
        if not sys.gettrace():
            self.attach()
        self.set_step('into')


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

debugger = Debugger(skip=['chromedebug', 'chromedebug.*', 'ws4py.*'])


def attach():
    debugger.attach()


def detach():
    debugger.detach()
atexit.register(detach)


def trace(func):
    @wraps(func)
    def inner(*args, **kwargs):
        attach()
        try:
            return func(*args, **kwargs)
        finally:
            detach()

    return inner


def exempt(func):
    @wraps(func)
    def inner(*args, **kwargs):
        old_trace = sys.gettrace()
        sys.settrace(None)
        try:
            return func(*args, **kwargs)
        finally:
            sys.settrace(old_trace)

    return inner


def add_breakpoint(url, lineno):
    debugger.set_break(url, lineno + 1)
    return {
        'breakpointId': '%s:%s' % (url, lineno),
        'locations': [{'scriptId': url, 'lineNumber': lineno}]}


def evaluate_on_frame(frame_id, expression, preview=False):
    try:
        obj = debugger.evaluate_on_frame(frame_id, expression)
        if preview:
            inspector.save_properties(obj, force=True)
        return {'result': inspector.encode(obj)}
    except Exception, e:
        return {
            'result': inspector.encode(e),
            'wasThrown': True}


def get_state():
    return debugger.get_pause_info()


def pause():
    debugger.set_step('into')


def remove_breakpoint(break_id):
    module, lineno = break_id.split(':', 1)
    debugger.clear_break(module, int(lineno) + 1)


def resume():
    debugger.set_continue()


def continue_to(url, lineno):
    debugger.continue_to(url, lineno)


def set_breakpoints_active(active):
    debugger.set_breakpoints_active(active)


def attach_profiler(profiler):
    debugger.attach_profiler(profiler)


def detach_profiler(profiler):
    debugger.detach_profiler(profiler)


def step_into():
    debugger.set_step('into')


def step_over():
    debugger.set_step('over')


def step_out():
    debugger.set_step('out')


def set_trace():
    debugger.set_trace()
