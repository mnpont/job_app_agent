"""
A tool that lets Claude read the text contents of a local PDF file.

Every tool file in this folder follows the same shape:
    SPEC  - a dictionary describing the tool to Claude (name, description,
            and what arguments it expects)
    run() - the actual Python function that does the work when Claude
            asks for this tool

tools/__init__.py automatically finds every file in this folder and wires
up SPEC + run for you - you never need to register a tool by hand.
"""

from pypdf import PdfReader

SPEC = {
    "name": "read_file",
    "description": (
        "Read the full text contents of a local PDF file by name. Use "
        "this to load the user's base resume or base cover letter "
        "before tailoring them to a specific job posting."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "One of: base_resume.pdf, base_cover_letter.pdf",
            }
        },
        "required": ["filename"],
    },
}


def run(tool_input):
    filename = tool_input["filename"]
    try:
        reader = PdfReader(filename)
        return "\n".join(page.extract_text() for page in reader.pages)
    except FileNotFoundError:
        return f"Error: {filename} not found in the current folder."
