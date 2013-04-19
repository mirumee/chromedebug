import sys
import threading
from wsgiref.simple_server import make_server

from ws4py.server.wsgirefserver import WSGIServer, WebSocketWSGIRequestHandler
from ws4py.server.wsgiutils import WebSocketWSGIApplication

__all__ = ['start']


class ServerThread(threading.Thread):
    daemon = True
    name = 'ChromeDebug'
    server = None

    def run(self):
        from . import server
        self.server = make_server(
            '', 9222, server_class=WSGIServer,
            handler_class=WebSocketWSGIRequestHandler,
            app=WebSocketWSGIApplication(handler_cls=server.DebuggerWebSocket))
        sys.stderr.write(
            'Navigate to chrome://devtools/devtools.html?ws=0.0.0.0:9222\n')
        self.server.initialize_websockets_manager()
        self.server.serve_forever()

thread = ServerThread()


def start():
    thread.start()


def console_log(level, typ, params, stack_trace):
    if not thread.server:
        return
    for ws in thread.server.manager:
        ws.console_log(level=level, typ=typ, params=params,
                       stack_trace=stack_trace)


def timeline_log(message):
    if not thread.server:
        return
    for ws in thread.server.manager:
        ws.timeline_log(message)


def debugger_paused(stack):
    if not thread.server:
        return
    for ws in thread.server.manager:
        ws.debugger_paused(stack)


def debugger_resumed():
    if not thread.server:
        return
    for ws in thread.server.manager:
        ws.debugger_resumed()


def debugger_script_parsed(name):
    if not thread.server:
        return
    for ws in thread.server.manager:
        ws.debugger_script_parsed(name)
