# job_app_agent

A minimal AI agent loop that reads your resume and cover letter, evaluates
fit against a job posting, and drafts a tailored cover letter using Claude.

## Setup

1. Install dependencies:

   ```
   pip3 install anthropic pypdf python-dotenv
   ```

2. Copy `.env.example` to `.env` and add your Anthropic API key:

   ```
   cp .env.example .env
   ```

   Then edit `.env` and paste your real key:

   ```
   ANTHROPIC_API_KEY=your-api-key-here
   ```

3. Put your resume and cover letter as PDFs in this same folder:

   ```
   base_resume.pdf
   base_cover_letter.pdf
   ```

   These files are gitignored and will never be committed.

## Usage

```
python3 agent_loop.py
```

Paste a job posting when prompted, then press Ctrl+D (Mac/Linux) or
Ctrl+Z then Enter (Windows) to submit it. The agent will print a match
score, key gaps, suggested resume adjustments, and a tailored cover letter.
