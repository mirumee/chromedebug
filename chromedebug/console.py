from functools import partial

from . import debugger
from . import inspector

__all__ = ['debug', 'error', 'log', 'warn']


def _log(level, *args):
    params = map(inspector.encode, args)
    debugger.console_log(
        {'level': level, 'type': 'log', 'parameters': params})

debug = partial(_log, 'debug')
error = partial(_log, 'error')
log = partial(_log, 'log')
warn = partial(_log, 'warning')
