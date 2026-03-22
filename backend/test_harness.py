import importlib
import sys

modules = [
    "core.settings",
    "db",
    "main",
]

import os
for root, dirs, files in os.walk("."):
    for d in [".venv", "__pycache__", ".pytest_cache", ".git", "tests"]:
        if d in dirs: dirs.remove(d)
    
    for file in files:
        if file.endswith(".py") and file != "test_harness.py":
            modpath = os.path.relpath(os.path.join(root, file), ".").replace(os.path.sep, ".")[:-3]
            modules.append(modpath)

print("Starting tests...")
for mod in modules:
    print(f"Loading {mod}...", flush=True)
    try:
        importlib.import_module(mod)
        print(f"Loaded {mod}", flush=True)
    except Exception as e:
        print(f"Error {mod}: {e}", flush=True)
        sys.exit(1)
print("Done")
