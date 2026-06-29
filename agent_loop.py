"""
================================================================================
MINIMAL AI AGENT LOOP
================================================================================

1. You give it a job posting and ask it to tailor your resume/cover letter.
2. The AI model (Claude) reads your request and decides: "I need to read the
   user's resume file first before I can do this."
3. Our code notices the AI wants to use a "tool" (in this case, a function
   that reads a file), so it actually reads the file, and sends the contents
   back to the AI.
4. The AI now has the resume text, and uses it to write a tailored draft.
5. Our code notices the AI is NOT asking for any more tools - it's done - so
   we print its final answer.

This back-and-forth (AI asks for a tool -> our code runs it -> AI gets the
result -> repeat) is called "the agent loop". It's the heart of what makes
something an "AI agent" instead of just a single question-and-answer.

--------------------------------------------------------------------------------
SETUP (do this once):

    pip3 install anthropic pypdf python-dotenv

    Copy .env.example to .env and put your real API key in there:
        cp .env.example .env
        (then edit .env in a text editor and paste your key)

Then, in the SAME FOLDER as this script, put your resume and cover letter
as PDFs:
    base_resume.pdf          <- your real resume in here
    base_cover_letter.pdf    <- your real cover letter in here

Finally, paste a real job description into the JOB_POSTING variable near
the bottom of this file, and run:

    python agent_loop.py
================================================================================
"""

import sys

from dotenv import load_dotenv

load_dotenv()

import anthropic # pyright: ignore[reportMissingImports]
from pypdf import PdfReader

# This creates a "client" - think of it as a phone you can use to call
# Claude. Behind the scenes, it automatically looks for your API key in
# an environment variable called ANTHROPIC_API_KEY.
client = anthropic.Anthropic()

MODEL = "claude-haiku-4-5-20251001"


# ==============================================================================
# STEP 1: DESCRIBE OUR TOOL TO THE MODEL
# ==============================================================================
# Claude can't read your files by itself - it can only read and write text.
# So if we want it to be able to "use a tool", we have to:
#   (a) describe the tool to it in a very specific format (this section), and
#   (b) actually write the Python code that does the work (next section).
#
# TOOLS is a LIST (the square brackets [ ]) containing ONE tool description.
# Each tool description is a DICTIONARY (the curly braces { }) - a dictionary
# is just a collection of "key: value" pairs, a label and its contents.
#
# Claude will read this description and decide WHEN it wants to call this
# tool and WHAT arguments to call it with. Our code is the one that actually
# runs it - Claude only ever "asks".
TOOLS = [
    {
        # The name Claude will use to refer to this tool.
        "name": "read_file",

        # A plain-English explanation of what the tool does and when to use
        # it. This is the ONLY information Claude has about this tool - the
        # better this description is, the better Claude will use the tool.
        "description": (
            "Read the full text contents of a local PDF file by name. Use "
            "this to load the user's base resume or base cover letter "
            "before tailoring them to a specific job posting."
        ),

        # This describes what ARGUMENTS the tool needs, using a standard
        # format called "JSON Schema". Don't worry about memorizing this -
        # just know that it says: "this tool needs one argument, called
        # 'filename', and it must be text (a string)".
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
]


# ==============================================================================
# STEP 2: WRITE THE ACTUAL CODE THAT THE TOOL RUNS
# ==============================================================================
# Claude never sees this code and never runs it directly. When Claude asks
# for the "read_file" tool, OUR code (below) is what actually opens the file.

def read_file(filename):
    # "try" means: attempt to do the following, and if something goes wrong,
    # don't crash the whole program - instead, jump to the "except" part.
    try:
        # PdfReader opens the PDF and gives us access to its pages.
        reader = PdfReader(filename)
        # Each page's text comes out separately, so we extract it page
        # by page and glue the pieces together with newlines in between.
        return "\n".join(page.extract_text() for page in reader.pages)
    except FileNotFoundError:
        # This only runs if the file genuinely doesn't exist. Instead of
        # crashing, we return an error message AS TEXT - because we want
        # to feed this back to Claude later, and Claude only understands text.
        return f"Error: {filename} not found in the current folder."


def execute_tool(name, tool_input):
    # This function's job is simple: look at WHICH tool Claude asked for
    # (there's only one in this script, but you'll add more later), and
    # call the matching Python function.
    #
    # tool_input is a dictionary, e.g. {"filename": "base_resume.txt"}.
    # tool_input["filename"] grabs the value stored under the "filename" key.
    if name == "read_file":
        return read_file(tool_input["filename"])

    # If Claude somehow asks for a tool we don't recognize, say so instead
    # of crashing.
    return f"Error: unknown tool '{name}'"


# ==============================================================================
# STEP 3: THE AGENT LOOP ITSELF
# ==============================================================================
# This is the function that does the back-and-forth described at the very
# top of this file. Read the comments inside it slowly - this is the part
# that actually matters most.

def run_agent(user_message):
    # "messages" is the running history of the conversation: what the user
    # said, what Claude said, what tool results came back, etc. We start it
    # off with just the user's first message.
    #
    # Every single time we talk to Claude, we have to send this ENTIRE
    # history again - Claude itself does not remember anything between
    # calls. Our code is responsible for remembering.
    messages = [{"role": "user", "content": user_message}]

    # "while True:" starts a loop that repeats FOREVER, until something
    # inside it explicitly stops it (in our case, a "return" statement).
    # This is what makes it "the loop" - the model gets called again and
    # again until it has nothing left to do.
    while True:

        # This is the actual "phone call" to Claude. We send:
        #   - which model to use
        #   - max_tokens: the longest answer we'll allow it to write
        #   - system: instructions about HOW it should behave overall
        #   - tools: the tool description from Step 1
        #   - messages: the entire conversation so far
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=(
                "You are a careful career assistant helping evaluate fit and "
                "tailor application materials. The user reads your output in "
                "a plain terminal with no markdown rendering. Format your "
                "entire response as plain text only: do not use bold/italic "
                "markers (**, *, _), do not use markdown headers (#), do not "
                "use tables or pipe characters for layout, and no emojis. Use plain capital-"
                "letter section labels followed by a colon, and a simple "
                "dash (-) for list items.\n\n"
                "Before doing anything else, read the user's base resume and "
                "base cover letter using the read_file tool.\n\n"
                "Then structure your response in exactly this order:\n\n"
                "MATCH SCORE: a score out of 100 plus a one-word label, "
                "using this rubric -\n"
                "- Required qualifications met (up to 50 points): how many "
                "of the posting's must-have requirements the resume gives "
                "clear evidence for\n"
                "- Preferred qualifications met (up to 20 points): nice-to-"
                "have skills or experience mentioned in the posting\n"
                "- Seniority/experience level fit (up to 15 points): does "
                "the candidate's years of experience and past titles match "
                "the level implied by the posting (junior/mid/senior/lead)\n"
                "- Domain/industry alignment (up to 15 points): overlap "
                "between the candidate's industry background and the "
                "posting's domain\n"
                "Label the total as: 80-100 Strong match, 60-79 Good match, "
                "40-59 Stretch, below 40 Not aligned.\n\n"
                "KEY GAPS: a short list of the most important requirements "
                "the resume does not clearly demonstrate. Write 'None' if "
                "there aren't any meaningful gaps.\n\n"
                "RESUME ADJUSTMENTS: specific, concrete edits worth making "
                "to the resume for this role. Write 'No changes needed' if "
                "there genuinely aren't any.\n\n"
                "TAILORED COVER LETTER: the full text of a cover letter "
                "adapted to this specific role - keep the underlying facts "
                "from the base cover letter the same, just re-emphasize and "
                "reword for relevance to this posting."
            ),
            tools=TOOLS,
            messages=messages,
        )

        # Claude's reply is an object with several pieces of information.
        # response.content is a LIST of "blocks" - usually either a block
        # of plain text, or a block asking to use a tool. We add whatever
        # Claude just said to our running history, so it isn't forgotten.
        messages.append({"role": "assistant", "content": response.content})

        # response.stop_reason tells us WHY Claude stopped talking.
        # If it's "tool_use", Claude wants to call a tool and is waiting
        # for the result. Anything else (usually "end_turn") means Claude
        # is finished and has given us its final answer.
        if response.stop_reason != "tool_use":
            # Claude is done. Now we just need to pull the actual text out
            # of response.content and hand it back to whoever called
            # run_agent(...). We build it up piece by piece in a loop,
            # since response.content can technically contain more than
            # one block.
            final_text = ""
            for block in response.content:
                if block.type == "text":
                    final_text = final_text + block.text
            return final_text  # this exits the while loop AND the function

        # If we reach this point, Claude asked for one or more tools.
        # We need to run each one and collect the results.
        tool_results = []

        for block in response.content:
            # We only care about blocks where Claude is asking to use a tool.
            if block.type == "tool_use":
                # block.name is which tool it wants (e.g. "read_file").
                # block.input is the arguments dictionary it wants to use,
                # e.g. {"filename": "base_resume.txt"}.
                result = execute_tool(block.name, block.input)

                # We package the result in the exact format Claude expects,
                # so it knows which tool call this result belongs to
                # (tool_use_id is what matches answers to questions, in
                # case more than one tool was called at once).
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        # We add the tool result(s) to the conversation history as a new
        # "user" message (this is just the format the API expects - it
        # doesn't mean a human typed this).
        messages.append({"role": "user", "content": tool_results})

        # We do NOT return here - we let "while True" loop go around again.
        # This time, Claude will see the tool result in the conversation
        # and can decide what to do next.


# ==============================================================================
# STEP 4: ACTUALLY RUN IT
# ==============================================================================
# This special line means: "only run the code below if this file is being
# run directly (python agent_loop.py), not if it's being imported by some
# other file." For a script like this, you can mostly just think of it as
# "this is where the program starts."
if __name__ == "__main__":

    # Ask for the job posting each time the script runs. We use sys.stdin.read() instead of the
    # simpler input() because input() only grabs ONE line - if you paste a
    # whole job posting (many lines, maybe with stray text from the
    # webpage), input() would cut it off after the first line.
    #
    # sys.stdin.read() keeps reading everything you paste/type until it
    # sees an "EOF" (end-of-file) signal, which you send manually by
    # pressing Ctrl+D on Mac/Linux (or Ctrl+Z then Enter on Windows) once
    # you're done pasting. It's fine if the pasted text is messy - extra
    # blank lines, "Apply Now" buttons, nav menu text, etc. - Claude is
    # perfectly capable of ignoring the noise and finding the actual job
    # description within it.
    print("Paste the job posting below. When you're done, press Ctrl+D (Mac/Linux) or Ctrl+Z then Enter (Windows):")
    JOB_POSTING = sys.stdin.read()

    # We build the instruction we'll send to Claude.
    prompt = f"""
Here is a job posting:

{JOB_POSTING}

Evaluate my fit and tailor my application materials for this specific role,
exactly as instructed.
"""

    # Call our agent loop with that instruction, and print whatever it
    # eventually returns.
    print(run_agent(prompt))
