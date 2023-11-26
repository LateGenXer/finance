import os.path
import sys


script = os.path.abspath("gilts/app.py")


sys.path.insert(0, os.path.dirname(script))
with open(script) as f:
    code = compile(f.read(), script, 'exec')
    glbls = globals().copy()
    glbls['__file__'] = script
    exec(code, glbls)
