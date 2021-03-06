import json
import sys

from ws4py.websocket import WebSocket

from . import debugger
from . import inspector
from . import profiler


class DebuggerWebSocket(WebSocket):
    console_cache = None
    console_enabled = False
    debugger_enabled = False
    profiling_enabled = False

    def __init__(self, *args, **kwargs):
        super(DebuggerWebSocket, self).__init__(*args, **kwargs)
        self.console_messages = []
        self.console_cache = []
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
        elif method == 'Debugger.canSetScriptSource':
            resp['result'] = False
        elif method == 'Debugger.continueToLocation':
            location = params.get('location', {})
            debugger.continue_to(
                location.get('scriptId'),
                location.get('lineNumber'))
        elif method == 'Debugger.disable':
            self.debugger_enabled = False
        elif method == 'Debugger.enable':
            self.debugger_enabled = True
            for name, module in sys.modules.iteritems():
                if module:
                    self.debugger_script_parsed(name)
            info = debugger.get_state()
            if info:
                self.debugger_paused(info)
        elif method == 'Debugger.evaluateOnCallFrame':
            expression = params.get('expression', '')
            preview = params.get('generatePreview', False)
            object_group = params.get('objectGroup', None)
            result = debugger.evaluate_on_frame(
                params.get('callFrameId'), expression,
                group=object_group, preview=preview)
            resp['result'] = result
        elif method == 'Debugger.getFunctionDetails':
            object_id = params.get('functionId')
            props = inspector.get_function_details(object_id)
            resp['result'] = {'details': props}
        elif method == 'Debugger.getScriptSource':
            content = debugger.get_script_source(params.get('scriptId'))
            resp['result'] = {'scriptSource': content}
        elif method == 'Debugger.pause':
            debugger.pause()
        elif method == 'Debugger.removeBreakpoint':
            debugger.remove_breakpoint(params.get('breakpointId'))
        elif method == 'Debugger.setBreakpointByUrl':
            breakpoint = debugger.add_breakpoint(params.get('url'),
                                                 params.get('lineNumber'))
            resp['result'] = breakpoint
        elif method == 'Debugger.setBreakpointsActive':
            debugger.set_active(params.get('active'))
        elif method == 'Debugger.stepInto':
            debugger.step_into()
        elif method == 'Debugger.stepOver':
            debugger.step_over()
        elif method == 'Debugger.stepOut':
            debugger.step_out()
        elif method == 'Debugger.resume':
            debugger.resume()
        elif method == 'Debugger.setOverlayMessage':
            msg = params.get('message')
            if msg:
                sys.stderr.write('<< %s >>\n' % (msg,))
        elif method == 'Page.enable':
            resp['error'] = {}
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
        elif method == 'Runtime.callFunctionOn':
            # hacks!
            object_id = params.get('objectId')
            body = params.get('functionDeclaration', '')
            if body.startswith('function getCompletions(primitiveType)'):
                obj = inspector.get_object(object_id)
                props = inspector.extract_properties(obj)
                props = dict((p['name'], True) for p in props)
                resp['result'] = {
                    'result': inspector.encode(props, by_value=True)}
            elif body.startswith('function remoteFunction(arrayStr)'):
                props = params.get('arguments')
                if props:
                    props = props[0].get('value')
                if props:
                    props = json.loads(props)
                obj = inspector.get_object(object_id)
                for prop in props:
                    try:
                        obj = getattr(obj, prop)
                    except Exception:
                        break
                resp['result'] = {
                    'result': inspector.encode(obj, by_value=True)}
            else:
                resp['error'] = {
                    'message': '%s not supported' % (method,),
                    'data': {}}
        elif method == 'Runtime.getProperties':
            object_id = params.get('objectId')
            accessor = params.get('accessorPropertiesOnly', False)
            obj = inspector.get_object(object_id)
            props = inspector.extract_properties(obj, accessors=accessor)
            resp['result'] = {'result': list(props)}
        elif method == 'Runtime.releaseObjectGroup':
            object_group = params.get('objectGroup', None)
            inspector.release_group(object_group)
        else:
            resp['error'] = {
                'message': '%s not supported' % (method,),
                'data': {}}
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

    def console_log(self, level, typ, params, stack_trace):
        # hold a reference
        self.console_cache.append(params)
        params = map(inspector.encode, params)
        message = {
            'level': level,
            'type': typ,
            'parameters': params,
            'stackTrace': stack_trace}
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
