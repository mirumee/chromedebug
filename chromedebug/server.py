import json

from ws4py.websocket import WebSocket

from . import inspector
from . import profiler


class DebuggerWebSocket(WebSocket):
    console_enabled = False
    profiling_enabled = False

    def __init__(self, *args, **kwargs):
        super(DebuggerWebSocket, self).__init__(*args, **kwargs)
        self.console_messages = []
        self._call_stack = []

    def handle_method(self, method, params):
        resp = {}
        if method == 'Console.enable':
            self.console_enabled = True
            self.console_flush()
        elif method == 'Console.disable':
            self.console_enabled = False
        elif method == 'Runtime.getProperties':
            object_id = params.get('objectId')
            resp['result'] = {'result': inspector.get_properties(object_id)}
        elif method == 'Profiler.start':
            profiler.start_profiling()
            self.send_event('Profiler.setRecordingProfile', isProfiling=True)
        elif method == 'Profiler.stop':
            header = profiler.stop_profiling()
            self.send_event('Profiler.addProfileHeader', header=header)
            self.send_event('Profiler.setRecordingProfile', isProfiling=False)
        elif method == 'Profiler.getCPUProfile':
            profile = profiler.get_profile(params.get('uid'))
            resp['result'] = {'profile': profile}
        return resp

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
