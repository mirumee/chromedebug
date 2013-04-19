from functools import partial
import sys

from . import debugger
from . import thread

__all__ = ['debug', 'error', 'log', 'warn']


def _get_trace():
    frame = sys._getframe(2)
    trace = []
    while frame:
        info = debugger.get_call_info(frame)
        trace.append({
            'functionName': info.function,
            'url': info.module,
            'lineNumber': info.lineno,
            'columnNumber': 0})
        frame = frame.f_back
    return trace


def _log(level, *args):
    thread.console_log(level=level, typ='log', params=args,
                       stack_trace=_get_trace())

debug = partial(_log, 'debug')
error = partial(_log, 'error')
log = partial(_log, 'log')
warn = partial(_log, 'warning')
