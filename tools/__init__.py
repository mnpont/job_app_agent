"""
This file turns the "tools/" folder into a plug-and-play tool registry.

To add a brand new tool, you do NOT need to touch this file or
agent_loop.py at all. Just drop a new file in this folder that defines:

    SPEC = {...}      <- describes the tool to Claude
    def run(tool_input): ...   <- the code that actually runs

and it will be picked up automatically the next time the script runs.

How: Python has a built-in helper, pkgutil.iter_modules(), that can look
inside a folder and list every .py file in it (without us having to name
them one by one). For each file it finds, we import it and grab its SPEC
and run().
"""

import importlib
import pkgutil

# TOOLS is the list of tool descriptions we send to Claude.
TOOLS = []

# _RUNNERS maps a tool's name (e.g. "read_file") to its run() function,
# so we know which code to call when Claude asks for a specific tool.
_RUNNERS = {}

# __path__ is the folder this __init__.py lives in (i.e. tools/).
# iter_modules looks inside it and yields info about every .py file there.
for _module_info in pkgutil.iter_modules(__path__):
    _module = importlib.import_module(f"{__name__}.{_module_info.name}")

    # A file only counts as a tool if it defines both SPEC and run.
    if hasattr(_module, "SPEC") and hasattr(_module, "run"):
        TOOLS.append(_module.SPEC)
        _RUNNERS[_module.SPEC["name"]] = _module.run


def execute_tool(name, tool_input):
    runner = _RUNNERS.get(name)
    if runner is None:
        return f"Error: unknown tool '{name}'"
    return runner(tool_input)
