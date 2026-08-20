# Proxy conftest so fixtures in code/conftest.py are available to tests moved into tests/
import sys, os
this_dir = os.path.dirname(__file__)
code_dir = os.path.abspath(os.path.join(this_dir, "..", "code"))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)
# Import the original conftest module by file name
import importlib.util
spec = importlib.util.spec_from_file_location("project_code_conftest", os.path.join(code_dir, "conftest.py"))
code_conftest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(code_conftest)
# Re-export fixtures by copying attributes into this module's globals
for _k, _v in code_conftest.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v
