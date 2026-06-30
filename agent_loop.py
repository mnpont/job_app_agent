"""
================================================================================
MINIMAL AI AGENT LOOP
================================================================================

1. You give it a job posting and ask it to tailor your resume/cover letter.
2. The AI model (Claude) reads your request and decides: "I need to read the
   user's resume file first before I can do this."
3. Our code notices the AI wants to use a "tool" and actually runs it - the
   tool's code lives in its own file under the tools/ folder, not in this
   file (see tools/read_file.py and tools/__init__.py) - and sends the
   result back to the AI.
4. The AI now has the resume text, and uses it to write a tailored draft.
5. Our code notices the AI is NOT asking for any more tools - it's done - so
   we print its final answer.

This back-and-forth (AI asks for a tool -> our code runs it -> AI gets the
result -> repeat) is called "the agent loop". It's the heart of what makes
something an "AI agent" instead of just a single question-and-answer.

This file only contains the loop itself - it has no idea how many tools
exist or what they do. Every tool is its own plug-and-play file inside
tools/. See CLAUDE.md for the blueprint to follow when adding a new one.
================================================================================
"""

import sys
import time

from dotenv import load_dotenv

load_dotenv()

import anthropic # pyright: ignore[reportMissingImports]

from tools import TOOLS, execute_tool

# This creates a "client" - think of it as a phone you can use to call
# Claude. Behind the scenes, it automatically looks for your API key in
# an environment variable called ANTHROPIC_API_KEY.
client = anthropic.Anthropic()

MODEL = "claude-haiku-4-5-20251001"


# ==============================================================================
# SYSTEM PROMPTS
# ==============================================================================
# The agent runs in two phases. Each phase gets its own system prompt so
# Claude knows exactly what to output and when to stop.
#
# Phase 1: read the files, score the fit, list key gaps.
# Phase 2: using the context already in the conversation, write the resume
#          adjustments and tailored cover letter. No file reads needed.

_SYSTEM_BASE = (
    "You are a careful career assistant helping evaluate fit and "
    "tailor application materials. The user reads your output in "
    "a plain terminal with no markdown rendering. Format your "
    "entire response as plain text only: do not use bold/italic "
    "markers (**, *, _), do not use markdown headers (#), and no "
    "emojis. Use plain capital-letter section labels followed by "
    "a colon, and a simple dash (-) for list items.\n\n"
)

SYSTEM_PHASE_1 = _SYSTEM_BASE + (
    "Before doing anything else, read the user's base resume and "
    "base cover letter using the read_file tool. If the user "
    "provided a job posting URL instead of pasted text, also use "
    "the fetch_job_posting tool to retrieve the job description "
    "before proceeding.\n\n"
    "Then output exactly two sections in this order:\n\n"
    "MATCH SCORE: one line with the total score out of 100 and "
    "its label (see rubric below). Immediately after that line, "
    "print this exact table using pipe characters - fill in the "
    "Score column with the points you awarded in each category:\n\n"
    "CATEGORY                          | POSSIBLE | SCORE\n"
    "----------------------------------|----------|------\n"
    "Required qualifications           |       50 |    ??\n"
    "Preferred qualifications          |       20 |    ??\n"
    "Seniority/experience level fit    |       15 |    ??\n"
    "Domain/industry alignment         |       15 |    ??\n"
    "----------------------------------|----------|------\n"
    "TOTAL                             |      100 |    ??\n\n"
    "Rubric for the scores above:\n"
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
    "there aren't any meaningful gaps."
)

SYSTEM_PHASE_2 = _SYSTEM_BASE + (
    "The conversation history already contains the user's resume, "
    "cover letter, and job posting - do not call any tools.\n\n"
    "Output exactly two sections in this order:\n\n"
    "RESUME ADJUSTMENTS: specific, concrete edits worth making "
    "to the resume for this role. Write 'No changes needed' if "
    "there genuinely aren't any.\n\n"
    "TAILORED COVER LETTER: the full text of a cover letter "
    "adapted to this specific role - keep the underlying facts "
    "from the base cover letter the same, just re-emphasize and "
    "reword for relevance to this posting."
)


# ==============================================================================
# THE AGENT LOOP
# ==============================================================================
# This is the function that does the back-and-forth described at the very
# top of this file. Read the comments inside it slowly - this is the part
# that actually matters most.
#
# It now accepts two optional parameters:
#   system   - the system prompt to use for this run
#   messages - existing conversation history to continue from (used in phase 2
#              so Claude already has the resume/job posting in context and
#              doesn't need to re-read any files)

def run_agent(user_message, system, messages=None):
    # Start a fresh conversation, or continue an existing one.
    if messages is None:
        messages = [{"role": "user", "content": user_message}]
    else:
        # Append the new user turn to the history we received.
        messages = messages + [{"role": "user", "content": user_message}]

    start_time = time.time()

    # "while True:" starts a loop that repeats FOREVER, until something
    # inside it explicitly stops it (in our case, a "return" statement).
    # This is what makes it "the loop" - the model gets called again and
    # again until it has nothing left to do.
    while True:

        print("Thinking...", flush=True)

        # This is the actual "phone call" to Claude. We send:
        #   - which model to use
        #   - max_tokens: the longest answer we'll allow it to write
        #   - system: instructions about HOW it should behave overall
        #   - tools: the tool descriptions auto-collected from tools/
        #   - messages: the entire conversation so far
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=system,
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
            #
            # We also return the messages history so the caller can pass it
            # into a follow-up run_agent call (phase 2) without losing context.
            elapsed = time.time() - start_time
            final_text = ""
            for block in response.content:
                if block.type == "text":
                    final_text += block.text
            return elapsed, final_text, messages  # exits the while loop AND the function

        # If we reach this point, Claude asked for one or more tools.
        # We need to run each one and collect the results.
        tool_results = []

        for block in response.content:
            # We only care about blocks where Claude is asking to use a tool.
            if block.type == "tool_use":
                # block.name is which tool it wants (e.g. "read_file").
                # block.input is the arguments dictionary it wants to use,
                # e.g. {"filename": "base_resume.txt"}.
                print(f"Using tool: {block.name}...", flush=True)
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
# TERMINAL INPUT HELPERS
# ==============================================================================
# sys.stdin.read() exhausts stdin on the first Ctrl+D, so any subsequent
# reads (yes/no answers, next job posting) must go through /dev/tty instead,
# which always points to the user's actual terminal regardless of stdin state.

def _tty_confirm(prompt):
    """Ask a yes/no question; return True if the user answers y/Y."""
    print(f"\n{prompt} (y/n): ", end="", flush=True)
    try:
        with open("/dev/tty") as tty:
            answer = tty.readline().strip().lower()
    except OSError:
        answer = input().strip().lower()
    return answer == "y"

def _tty_read_job_posting():
    """Read a job posting URL or pasted text from the terminal."""
    print("Enter a job posting URL, or paste the full job description.")
    print("Press Ctrl+D when done (Mac/Linux) or Ctrl+Z then Enter (Windows):")
    try:
        with open("/dev/tty") as tty:
            return tty.read().strip()
    except OSError:
        return sys.stdin.read().strip()


# ==============================================================================
# ENTRY POINT
# ==============================================================================
# This special line means: "only run the code below if this file is being
# run directly (python agent_loop.py), not if it's being imported by some
# other file." For a script like this, you can mostly just think of it as
# "this is where the program starts."
if __name__ == "__main__":

    # The outer loop lets the user process multiple job postings back-to-back
    # without restarting the script. Each iteration is one full job evaluation.
    #
    # The very first posting reads from sys.stdin (so the user can pipe input
    # or paste freely). Every subsequent posting and all yes/no prompts use
    # /dev/tty via the helpers above, since stdin is exhausted after the first
    # Ctrl+D.
    first_run = True

    while True:

        # ── Get job posting ────────────────────────────────────────────────
        if first_run:
            print("Enter a job posting URL, or paste the full job description.")
            print("Press Ctrl+D when done (Mac/Linux) or Ctrl+Z then Enter (Windows):")
            user_input = sys.stdin.read().strip()
            first_run = False
        else:
            print()
            user_input = _tty_read_job_posting()

        # Detect whether the user gave us a URL or raw text, and build the
        # appropriate prompt so Claude knows what to do with the input.
        if user_input.startswith(("http://", "https://")):
            prompt = (
                "Fetch the job posting from this URL and then evaluate my fit, "
                "exactly as instructed.\n\nURL: " + user_input
            )
        else:
            prompt = (
                "Here is a job posting:\n\n"
                + user_input
                + "\n\nEvaluate my fit exactly as instructed."
            )

        # ── Phase 1: match score + key gaps ───────────────────────────────
        print()
        elapsed, phase1_text, messages = run_agent(prompt, system=SYSTEM_PHASE_1)

        print("\n" + "-" * 72)
        print(phase1_text)
        print("-" * 72)
        print(f"Done in {elapsed:.1f}s")

        # ── Gate: ask before spending tokens on adjustments + cover letter ─
        if not _tty_confirm("Generate resume adjustments and cover letter?"):
            if not _tty_confirm("Process another job posting?"):
                break
            continue

        # ── Phase 2: resume adjustments + tailored cover letter ───────────
        # We pass the messages history from phase 1 so Claude already has
        # the resume and job posting in context - no file re-reads needed.
        print()
        elapsed2, phase2_text, _ = run_agent(
            "Now generate the resume adjustments and tailored cover letter as instructed.",
            system=SYSTEM_PHASE_2,
            messages=messages,
        )

        print("\n" + "-" * 72)
        print(phase2_text)
        print("-" * 72)
        print(f"Done in {elapsed2:.1f}s")

        # ── Loop: offer to process another posting ─────────────────────────
        if not _tty_confirm("Process another job posting?"):
            break
