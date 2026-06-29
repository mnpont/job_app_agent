# job_app_agent

A minimal AI agent that reads a job posting plus your base resume/cover
letter PDFs, scores fit, and drafts a tailored cover letter using the
Claude API's tool-calling ("agent loop") pattern.

## Architecture

- `agent_loop.py` - the generic agent loop. Calls Claude, checks if it
  wants to use a tool, runs the tool, feeds the result back, repeats until
  Claude gives a final answer. **This file should never need to change
  when you add a new tool.**
- `tools/` - one file per tool. Auto-discovered at import time, so dropping
  in a new file is the entire integration step.
  - `tools/__init__.py` - the registry. Scans every `.py` file in this
    folder, collects each one's `SPEC` and `run`, and builds:
    - `TOOLS` - the list of tool descriptions sent to Claude
    - `execute_tool(name, tool_input)` - dispatches to the right tool's `run`
  - `tools/read_file.py` - example/reference tool: reads a local PDF's text.

## How to add a new tool

1. Create `tools/your_tool_name.py`.
2. In it, define exactly two things:

```python
SPEC = {
    "name": "your_tool_name",          # must match the filename's purpose,
                                         # this is what Claude calls it
    "description": (
        "Plain-English explanation of what this tool does and WHEN Claude "
        "should use it. This description is the only thing Claude sees - "
        "the better it is, the better Claude decides when to use the tool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "some_arg": {
                "type": "string",
                "description": "What this argument means.",
            },
        },
        "required": ["some_arg"],
    },
}


def run(tool_input):
    # tool_input is a dict matching input_schema, e.g. {"some_arg": "..."}.
    # Do the work here and return a STRING (or something that serializes
    # to text) - Claude only understands text, never Python objects.
    ...
    return result
```

3. Save the file. That's it - no edits to `agent_loop.py` or
   `tools/__init__.py`. The next time the script runs, `tools/__init__.py`
   will pick it up automatically and Claude will be told about it.

### Rules of thumb for new tools

- One tool = one file = one job. Don't put multiple unrelated tools in one
  file (the registry keys tools by `SPEC["name"]`, one per module is the
  convention this loop expects).
- `run()` must not crash on bad/missing input - catch expected failures
  (missing file, bad API response, etc.) and `return` an error message as
  a string instead of raising. The agent loop has no special error
  handling around tool calls; an uncaught exception in `run()` kills the
  whole script mid-conversation.
- `run()`'s return value is fed straight back to Claude as text - keep it
  plain text/JSON-serializable, not Python objects, file handles, etc.
- Keep `SPEC["description"]` specific about *when* to use the tool, not
  just *what* it does - this is the only signal Claude has for deciding
  whether to call it.
- If a tool needs API keys/secrets, load them with `os.environ` (and
  document them in `.env.example`), the same way `ANTHROPIC_API_KEY` is
  loaded via `.env` today. Don't hardcode secrets in the tool file.

## Running it

```
pip3 install anthropic pypdf python-dotenv
cp .env.example .env   # then paste your real ANTHROPIC_API_KEY in
python agent_loop.py
```

Requires `base_resume.pdf` and `base_cover_letter.pdf` in the project root.
