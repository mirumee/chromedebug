import sys
import threading
from wsgiref.simple_server import make_server

from ws4py.server.wsgirefserver import WSGIServer, WebSocketWSGIRequestHandler
from ws4py.server.wsgiutils import WebSocketWSGIApplication

__all__ = ['debugger', 'start']


class ServerThread(threading.Thread):
    daemon = True
    name = 'ChromeDebug'
    server = None

    def run(self):
        from . import debugger
        from . import server
        debugger.attach()
        self.server = make_server(
            '', 9222, server_class=WSGIServer,
            handler_class=WebSocketWSGIRequestHandler,
            app=WebSocketWSGIApplication(handler_cls=server.DebuggerWebSocket))
        sys.stderr.write(
            'Navigate to chrome://devtools/devtools.html?ws=0.0.0.0:9222\n')
        self.server.initialize_websockets_manager()
        self.server.serve_forever()

debugger = ServerThread()


def start():
    debugger.start()


def console_log(message):
    if not debugger.server:
        return
    for ws in debugger.server.manager:
        ws.console_log(message)


def timeline_log(message):
    if not debugger.server:
        return
    for ws in debugger.server.manager:
        ws.timeline_log(message)


def debugger_script_parsed(name):
    if not debugger.server:
        return
    for ws in debugger.server.manager:
        ws.debugger_script_parsed(name)
