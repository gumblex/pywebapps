#!/usr/bin/python
import os
import sys

sys.path.insert(0, os.path.dirname(__file__) or '.')

virtenv = os.path.join(os.environ['OPENSHIFT_DEPENDENCIES_DIR'], "python")

PY_CACHE = os.path.join(virtenv, 'lib', 'python3.4', 'site-packages')

os.environ['PYTHON_EGG_CACHE'] = os.path.join(PY_CACHE)
virtualenv = os.path.join(virtenv, 'bin', 'activate_this.py')

try:
    exec(open(virtualenv).read(), dict(__file__=virtualenv))
except IOError:
    pass

from main import app as application

