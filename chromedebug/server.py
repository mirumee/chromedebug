# coding: utf-8

import json
import sys

from ws4py.websocket import WebSocket

from . import debugger
from . import inspector
from . import profiler


class DebuggerWebSocket(WebSocket):
    console_enabled = False
    debugger_enabled = False
    profiling_enabled = False

    def __init__(self, *args, **kwargs):
        super(DebuggerWebSocket, self).__init__(*args, **kwargs)
        self.console_messages = []
        self._call_stack = []

    def handle_method(self, method, params):
        resp = {}
        if not debugger or not inspector or not profiler:  # terminating
            return
        if method == 'Console.disable':
            self.console_enabled = False
        elif method == 'Console.enable':
            self.console_enabled = True
            self.console_flush()
        elif method == 'Debugger.continueToLocation':
            location = params.get('location', {})
            debugger.continue_to(
                location.get('scriptId'),
                location.get('lineNumber'))
        elif method == 'Debugger.disable':
            self.debugger_enabled = False
        elif method == 'Debugger.enable':
            self.debugger_enabled = True
            for script in debugger.seen:
                self.debugger_script_parsed(script)
            info = debugger.get_state()
            if info:
                self.debugger_paused(info)
        elif method == 'Debugger.evaluateOnCallFrame':
            result = debugger.evaluate_on_frame(
                params.get('callFrameId'), params.get('expression'),
                group=params.get('objectGroup'))
            resp['result'] = result
        elif method == 'Debugger.getScriptSource':
            content = debugger.get_script_source(params.get('scriptId'))
            resp['result'] = {'scriptSource': content}
        elif method == 'Debugger.removeBreakpoint':
            debugger.remove_breakpoint(params.get('breakpointId'))
        elif method == 'Debugger.setBreakpointByUrl':
            breakpoint = debugger.add_breakpoint(params.get('url'),
                                                 params.get('lineNumber'))
            resp['result'] = breakpoint
        elif method == 'Debugger.resume':
            debugger.resume()
        elif method == 'Debugger.setOverlayMessage':
            msg = params.get('message')
            if msg:
                sys.stderr.write(u'«%s»\n' % (msg,))
        elif method == 'Profiler.start':
            profiler.start_profiling()
            self.send_event('Profiler.setRecordingProfile', isProfiling=True)
        elif method == 'Profiler.stop':
            header = profiler.stop_profiling()
            self.send_event('Profiler.addProfileHeader', header=header)
            self.send_event('Profiler.setRecordingProfile', isProfiling=False)
        elif method == 'Profiler.getProfileHeaders':
            headers = profiler.get_profile_headers()
            resp['result'] = {'headers': headers}
        elif method == 'Profiler.getCPUProfile':
            profile = profiler.get_profile(params.get('uid'))
            resp['result'] = {'profile': profile}
        elif method == 'Runtime.getProperties':
            object_id = params.get('objectId')
            resp['result'] = {'result': inspector.get_properties(object_id)}
        elif method == 'Runtime.releaseObjectGroup':
            inspector.release_group(params.get('objectGroup'))
        return resp

    def debugger_paused(self, stack):
        if not debugger:  # terminating
            return
        if not self.debugger_enabled:
            debugger.resume()
        self.send_event('Debugger.paused', **stack)

    def debugger_resumed(self):
        self.send_event('Debugger.resumed')

    def debugger_script_parsed(self, name):
        if not self.debugger_enabled:
            return
        self.send_event('Debugger.scriptParsed', scriptId=name,
                        url=name, startLine=0, startColumn=0,
                        endLine=0, endColumn=0)

    def console_log(self, message):
        self.console_messages.append(message)
        self.console_flush()

    def console_flush(self):
        if not self.console_enabled:
            return
        msgs = self.console_messages
        self.console_messages = []
        for msg in msgs:
            self.send_event('Console.messageAdded', message=msg)

    def timeline_log(self, record):
        if not self.tracing_enabled:
            return
        self.send_event('Timeline.eventRecorded', record=record)

    def send_event(self, method, **kwargs):
        self.send(json.dumps({'method': method, 'params': kwargs}))

    def received_message(self, message):
        try:
            msg = json.loads(message.data)
        except Exception:
            return
        response = self.handle_method(
            msg['method'], msg.get('params', {}))
        response.update(id=msg['id'])
        self.send(json.dumps(response))
