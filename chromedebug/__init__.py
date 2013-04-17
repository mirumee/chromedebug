import os
import sys

__all__ = ['console', 'profiler']


def main():
    cur_path = os.path.dirname(__file__)
    boot_path = os.path.join(cur_path, 'boot')
    if 'PYTHONPATH' in os.environ:
        os.environ['PYTHONPATH'] = '%s:%s' % (
            boot_path, os.environ['PYTHONPATH'])
    else:
        os.environ['PYTHONPATH'] = boot_path
    os.execl(sys.executable, sys.executable, *sys.argv[1:])
