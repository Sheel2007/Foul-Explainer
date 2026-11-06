# AI VAR

An AI tool that watches a clip of a soccer tackle or handball and explains the call: foul or not, the restart, the card, and the exact rule behind it. It also shows how sure it is and why.

It is an explanation of how the rules apply to what the model saw, not an official ruling.

## What's in this repo

| Folder | What it is |
| --- | --- |
| [`foulcheck/`](foulcheck/) | The Foul Explainer app: Python backend, Next.js site, evaluation harness |
| [`docs/`](docs/) | The original build plan |

## How it works

1. **Watch.** A video model finds the moment of contact across every camera angle, records only what it sees, then zooms in on the boots.
2. **Look up the rule.** The facts select passages from the Laws of the Game 2026/27 and from Premier League and UEFA referee guidance.
3. **Decide.** A second model makes the call from those facts and passages. It never sees the video. A second independent run checks the result.
4. **Check.** Every quoted rule must match its source word for word, and confidence is lowered for anything unclear or disputed.

## Quick start

You need Python 3.12, [`uv`](https://docs.astral.sh/uv/), Node.js, `ffmpeg` and an API key from Gemini ([free tier](https://aistudio.google.com/apikey)), Anthropic or OpenAI. The command-line tools use Gemini by default; the web app accepts any of the three.

Create your settings file, then put your key in it:

```bash
cp foulcheck/.env.example foulcheck/.env
```

Build the rulebook. For the same calls as the examples, first run the referee guidance download described in `foulcheck/README.md`: without it, the AI only has the Laws, which don't cover details like contact at or above the ankle.

```bash
cd foulcheck/backend && uv run python -m foulcheck.laws.build
```

Start the API from `foulcheck/backend`:

```bash
uv run uvicorn foulcheck.api.app:app --port 8000
```

In a second terminal, start the site:

```bash
cd foulcheck/frontend && npm install && npm run dev
```

Open http://localhost:3000. The full guide, including the command-line pipeline and the optional referee guidance download, is in [`foulcheck/README.md`](foulcheck/README.md).

## Hosting the site

The site runs on Vercel and redeploys on every push, with **Root Directory** set to `foulcheck/frontend`. The example clips and frames are committed in `foulcheck/frontend/public/examples`, so a build from GitHub has everything it needs.

The backend isn't hosted, so the upload tool is replaced by a link here. To analyse your own clips, clone the repo and run it locally.

## What is not in git

These stay on your machine, so a fresh clone needs them added or rebuilt:

- **API keys:** `foulcheck/.env` only.
- **Rule text:** the Laws PDF, the saved referee guidance pages, and the parsed rulebook built from them. `foulcheck.laws.build` downloads the PDF and rebuilds the rulebook. Short rule quotes in `foulcheck/frontend/data/examples.json` are the exception.
- **Footage:** the source test clips and full explained videos. The silent copies the site shows are committed in `foulcheck/frontend/public/examples`, so re-running your own clips means adding your own source clips first.

## Tests

From `foulcheck/backend`. Tests that call real APIs are deselected by default.

```bash
uv run pytest
```
