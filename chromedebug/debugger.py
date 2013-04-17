import inspect
import sys

from . import thread

seen = set()


class ImportLoader(object):

    def load_module(self, full_name):
        module = sys.modules[full_name]
        if module and not module in seen:
            seen.add(module)
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


def attach():
    sys.meta_path.insert(0, ImportFinder())
    for name, module in sys.modules.iteritems():
        if module:
            seen.add(name)
