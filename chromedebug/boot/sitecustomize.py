import os
import sys

cur_path = os.path.dirname(__file__)
parent_path = os.path.join(cur_path, '..', '..')
if not parent_path in sys.path:
    sys.path.append(parent_path)

from chromedebug import debugger
from chromedebug import thread

debugger.attach()
thread.start()
