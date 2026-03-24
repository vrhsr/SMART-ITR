import importlib
import sys
import os

modules = []
for file in os.listdir("tests"):
    if file.endswith(".py") and not file.startswith("conftest"):
        modules.append(f"tests.{file[:-3]}")

print("Starting tests module imports...")
for mod in modules:
    print(f"Loading {mod}...", flush=True)
    try:
        importlib.import_module(mod)
        print(f"Loaded {mod}", flush=True)
    except Exception as e:
        print(f"Error {mod}: {e}", flush=True)
        sys.exit(1)
print("Done")
