# Foul Explainer: Build Plan

Oct 20, 2026 · @Sheel

## Overview

The tool takes a short clip of a soccer incident, returns a call (foul or no foul, handball or not, and the card if any), and shows the exact Law text that supports it. It is a teaching tool for fans, not a replacement for a referee, so every answer must show its reasoning and say how sure it is.

A good answer has four parts:

1. **The call:** for example "Direct free kick, yellow card (reckless challenge)."
2. **What the model saw:** a short, timestamped description of the key moment (who touched whom, which body part, where on the pitch).
3. **The rule:** the Law number and section from the Laws of the Game 2026/27, with the matching passage shown next to the call.
4. **Confidence and the gray area:** how sure the model is, and what a referee could reasonably see differently.

The main design idea: split the job in two. A video model only describes facts. A separate reasoning step applies the rules to those facts, using retrieved Law text. This keeps the rule citations honest and makes each step testable on its own.

## Scope for v1

v1 handles one short clip (5 to 30 seconds) of one incident and judges it under Law 12 (Fouls and Misconduct). That covers most of what fans argue about. Everything else waits for later versions.

| Decision type | v1 | Why |
| --- | --- | --- |
| Foul or no foul (careless, reckless, excessive force) | In | Core use case; Law 12 has clear categories |
| Handball | In | Very common fan question; Law 12 has a specific section |
| Card: none, yellow, red | In | Comes out of the same Law 12 reasoning |
| DOGSO and SPA (denying a goal chance, stopping a promising attack) | In, low confidence | Needs pitch context the clip may not show |
| Penalty vs. free kick (inside or outside the box) | In | Needs location; ask the user if the clip is unclear |
| Offside | Out | Needs exact player positions and line tech, not a fit for one broadcast angle |
| Goal-line and ball-out decisions | Out | Same reason |
| Multi-angle input | Later | Single clip first; multiple angles improve accuracy a lot (see Video understanding) |

The user can also add optional context in a text box, such as "this was in the penalty area" or "the defender was the last man." The app treats this as a hint, not a fact, and says so in the answer.

## Architecture

Two halves joined by one JSON hand-off. The top row runs on a video model and outputs facts only; the bottom row never sees video and turns those facts plus retrieved Law text into a cited ruling.

&#91;embedded content: pipeline · video side, rules side\]

The decision engine receives both the observations and the retrieved chunks. If the citation guard finds a quote that is not in the Laws, the decision step reruns once, then falls back to section references only. The backend runs each upload as a background job so the frontend can show live progress.

## Rulebook knowledge base

Use the [Laws of the Game 2026/27](https://downloads.theifab.com/downloads/laws-of-the-game-202627-double-pages?l=en) from The IFAB, which took effect on 1 July 2026. Pin the edition in config so every answer says which version it cites, and so a 2027/28 update is a data swap, not a code change.

**Licensing (check before going public).** The IFAB's books state that the Laws may not be reproduced in whole or in part without their permission. For a personal prototype or hackathon demo, store the text locally for retrieval and show short excerpts with a clear citation and link. Before any public launch, either get written permission from The IFAB or switch the UI to show a plain-language summary plus a link to the official section.

**Ingestion steps**

1. Download the official PDF and extract text with `pdfplumber` or `pymupdf`. Keep page numbers.
2. Split by structure, not by fixed size: Law number, then section (for example "12.1 Direct free kick", "12.3 Disciplinary action"), then sub-heading or bullet group. One chunk is one rule idea.
3. Store each chunk with metadata: `law`, `section`, `title`, `page`, `edition`, `text`, `tags` (for example `handball`, `reckless`, `dogso`).
4. Hand-write a small tag map for Law 12 so retrieval does not depend only on embeddings. Example: a "reckless" observation must always pull the careless/reckless/excessive force definitions.
5. Embed chunks with any embedding model and store them in a local vector store (SQLite with `sqlite-vec`, or Chroma). The whole book is small, so no hosted database is needed.

**Retrieval:** hybrid. First, rule-based lookup from the observation tags (handball, tackle type, card signals). Second, vector search over the observation text. Merge, dedupe, and cap at about 8 chunks. Always include the Law 12 definitions section so the model has the base terms.

**Citation guard:** after the decision step, check that every quoted passage appears word for word in a stored chunk. If not, drop the quote and show the section reference only. This stops the model from inventing rule text.

## Video understanding

Use a hosted video model through an adapter, starting with the Gemini API, because it takes video files directly and lets you set the frame rate. The biggest risk is frame rate: [Gemini samples video at 1 frame per second by default](https://ai.google.dev/gemini-api/docs/generate-content/video-understanding), and a tackle or handball happens in a fraction of a second. Always set a higher rate.

**Two-pass approach**

1. **Locate pass:** send the whole clip at a low rate (about 2 fps) and ask only for the timestamp of the key contact moment, plus a list of players involved by shirt color and number.
2. **Inspect pass:** clip to about 1.5 seconds before and after that moment with `videoMetadata` start and end offsets, and resend at a high rate (10 to 15 fps) with high media resolution. Ask for the structured observations below.

Use static processing, not the newer agentic mode. Google's docs say agentic mode is meant for long videos and can add cost and delay on short clips.

**Fallback path (model-agnostic):** use `ffmpeg` to cut the same window and pull frames at 10 to 15 fps, then send the frames as an image sequence to any vision model (for example Claude). Keep both paths behind one `VideoAnalyzer` interface so you can compare models in the eval harness.

**Observation schema (facts only, no rulings):**

```json
{
  "contact_time": "00:07.4",
  "players": [{"id": "A", "team": "red", "number": "4", "role": "defender"}],
  "contact": {"made": true, "by": "A", "on": "B", "body_part_used": "studs/sole", "body_part_hit": "ankle"},
  "ball_played_first": false,
  "challenge_type": "sliding tackle",
  "speed_and_force": "high",
  "handball": {"touched": false, "arm_position": null, "deliberate_movement": null},
  "location": "outside penalty area",
  "attack_context": "attacker running toward goal, one defender behind",
  "view_quality": "contact partly blocked by another player",
  "uncertain_fields": ["ball_played_first"]
}
```

The prompt must tell the model to describe what it sees and mark anything it cannot see as unknown. It must not use words like "foul" or "reckless" here; those are the decision engine's job.

**Later upgrade:** the [SoccerNet-MVFoul dataset](https://github.com/SoccerNet/sn-mvfoul) has 3,901 fouls labeled by a professional referee, with multiple camera angles each. The [VARS paper](https://arxiv.org/abs/2304.04617) found multi-view input clearly beats a single view. It is a good source for a fine-tuned classifier or for multi-angle support in v2.

## Decision engine

A text-only LLM call takes the observation JSON, the user's optional context, and the retrieved Law chunks, and returns a ruling in a fixed JSON schema. It may only cite chunks it was given, by chunk ID.

**Prompt rules**

- Reason in the order a referee would: was there an offence? Which category (careless, reckless, excessive force, or handball)? Where (restart type)? Is there extra misconduct (DOGSO, SPA)? Then the card.
- Every claim in the explanation must point to an observation field or a cited chunk.
- If a key observation is in `uncertain_fields`, lower confidence and name it in `gray_areas`.
- If view quality is too poor to decide, return `verdict: "cannot_determine"` instead of guessing.

**Output schema**

```json
{
  "verdict": "foul",
  "offence_type": "reckless challenge",
  "restart": "direct free kick",
  "card": "yellow",
  "confidence": 0.72,
  "explanation": "The red defender slid in late and caught the attacker's ankle with his studs without playing the ball...",
  "citations": [{"chunk_id": "L12-1-def-reckless", "why": "defines reckless as acting with disregard for danger to an opponent"}],
  "gray_areas": ["Replay does not clearly show whether the ball was touched first."],
  "key_moment": "00:07.4"
}
```

Validate the output with Pydantic. Run the citation guard from the rulebook section. If validation fails, retry once with the error message, then return an error to the UI.

**Confidence:** do not trust the model's number alone. Combine it with simple checks: lower it when `uncertain_fields` is non-empty, when view quality is poor, or when two runs at different temperatures disagree. Show it to users as High, Medium, or Low, not a raw percentage.

## Frontend

One page: upload a clip, wait about 20 to 40 seconds, see the verdict next to the video. Build it in Next.js with Tailwind, talking to the Python backend over REST.

**Screens and parts**

- **Upload panel:** drag-and-drop for MP4, MOV, or WebM, max 100 MB and 60 seconds. Optional text box for context. Client-side check of length and type before upload.
- **Progress state:** show real stages from the backend ("Finding the key moment", "Looking closely", "Checking the Laws") using server-sent events or polling.
- **Video player:** a marker on the timeline at `key_moment`, a "Jump to contact" button, and 0.25x playback.
- **Verdict card:** big label (Foul, No foul, Handball, Cannot tell), card icon, restart type, and a High/Medium/Low confidence badge.
- **Explanation:** 3 to 5 plain sentences.
- **Rule panel:** each citation as an expandable box with Law number, section title, the passage (or summary, see licensing), and a link to the official PDF page.
- **Gray areas:** a short "A referee could also see it this way" list.
- **Feedback:** thumbs up or down plus "What would you have called?" Save these to build the eval set over time.

## Evaluation

Build the test set before tuning prompts, or there is no way to tell if a change helped. Target 50 clips for v1.

**Sources for labeled clips**

- [SoccerNet-MVFoul](https://huggingface.co/datasets/SoccerNet/SN-MVFouls-2025): professional referee labels for foul type, offence, and card. The videos need a signed SoccerNet NDA, so use it for internal testing only.
- Your own clips with official outcomes, for example incidents where the league or PGMOL-style review panels published a final ruling.
- A mix by design: about 20 clear fouls, 10 clear non-fouls, 10 handball calls (both ways), 10 hard or split decisions.

**Label format:** one JSON per clip with the expected `verdict`, `card`, `restart`, and the Law sections a correct answer should cite.

**Metrics**

| Metric | What it checks | v1 target |
| --- | --- | --- |
| Verdict accuracy | Foul / no foul / handball matches label | 75% or better on clear cases |
| Card accuracy | None / yellow / red matches | 60% or better |
| Citation recall | Required Law sections appear in citations | 90% or better |
| Citation precision | Quoted text exists word for word in the Laws | 100% (enforced by guard) |
| Honest uncertainty | Hard clips get Medium/Low or "cannot determine" | Most hard clips |
| Latency | Upload to verdict | Under 45 seconds |

**Harness:** a CLI command (`python -m foulcheck.eval`) runs every clip, caches video-model outputs so decision-prompt changes can be re-tested cheaply, and writes a results table to `eval/results/<date>.csv`.

## Milestones

Five phases, each ending in something you can run. Hand the coding agent one phase at a time and check the "done when" line before moving on.

**Phase 1: Rulebook pipeline**

- [ ] Script to download and parse the 2026/27 PDF into structured chunks with page numbers
- [ ] Law 12 tag map (handball, careless, reckless, excessive force, DOGSO, SPA, restarts)
- [ ] Embeddings and local vector store
- [ ] `retrieve(observation) -> list[Chunk]` with hybrid lookup
- [ ] Done when: a test for "sliding tackle, studs on ankle, ball not played" returns the reckless and excessive force definitions

**Phase 2: Video analyzer**

- [ ] `VideoAnalyzer` interface with Gemini and frame-sequence implementations
- [ ] Locate pass and inspect pass with custom fps and clipping
- [ ] Pydantic observation schema and validation
- [ ] Done when: 5 sample clips produce valid observation JSON with sensible contact times

**Phase 3: Decision engine**

- [ ] Decision prompt and Pydantic ruling schema
- [ ] Citation guard and retry-on-invalid
- [ ] Confidence adjustment rules
- [ ] `analyze_clip(path, context) -> Ruling` end to end from the CLI
- [ ] Done when: the CLI prints a full ruling with valid citations for all 5 sample clips

**Phase 4: Web app**

- [ ] FastAPI backend: upload, job status stream, result endpoint
- [ ] Next.js frontend with all parts from the Frontend section
- [ ] Done when: a clip can be uploaded and the verdict, key-moment marker, and rule panel all show in the browser

**Phase 5: Evaluation and tuning**

- [ ] Collect and label 50 clips
- [ ] Eval CLI with cached video outputs
- [ ] Compare at least two video models and two fps settings
- [ ] Done when: results table meets or explains each v1 target

## Instructions for the coding agent

Paste this section into the agent's project instructions file (for example `CLAUDE.md`) at the start.

**Stack:** Python 3.12, FastAPI, Pydantic v2, `uv` for packages, `pytest`. Frontend: Next.js, TypeScript, Tailwind. `ffmpeg` installed on the system.

**Repo layout**

```
foulcheck/
  backend/
    foulcheck/
      laws/          # PDF parsing, chunking, tag map, retrieval
      video/         # VideoAnalyzer interface + implementations
      decision/      # prompts, ruling schema, citation guard
      api/           # FastAPI routes and job runner
      eval/          # eval CLI and metrics
    data/laws/2026-27/   # parsed chunks + vector store (gitignored if licensing requires)
    tests/
  frontend/
  eval/clips/        # labeled test clips (gitignored)
  .env.example       # GEMINI_API_KEY, ANTHROPIC_API_KEY, LAWS_EDITION
```

**Rules for the agent**

- Work one phase at a time. Stop and report when a phase's "done when" check passes.
- Keep the video step and the decision step separate. The video prompt never makes rulings; the decision prompt never sees raw video.
- All model calls go through one module with retries, timeouts, and logging of inputs and outputs to `logs/` for debugging.
- Every model output is parsed into a Pydantic model. No free-text parsing with regex.
- Never hard-code Law text in prompts or code. It always comes from the retrieval layer.
- Write a unit test for each module, and mock model calls in tests. Keep one slow integration test that calls the real APIs, marked so it can be skipped.
- Do not commit API keys, clips, or the Laws PDF.

## Risks and open questions

| Risk | Impact | Fallback |
| --- | --- | --- |
| Video model misreads fast contact | Wrong verdict stated with confidence | Two-pass high-fps inspect; "cannot determine" path; show gray areas |
| Rule text licensing | Public launch blocked | Ask IFAB early; summary-plus-link mode ready |
| Broadcast clips carry copyright | Can't host or share user clips | Process and delete; don't store or redistribute clips |
| Model cites wrong or made-up rule text | Loss of trust | Word-for-word citation guard |
| Fans read output as "the correct call" | Arguments, bad PR | Clear label: an explanation of how the Laws apply, not an official ruling |
| API cost per clip | Expensive at scale | Cache by file hash; low-fps locate pass keeps tokens down |

**Open questions**

- [ ] Public app, or a demo for a hackathon or the Instagram page first? This decides how urgent the licensing work is.
- [ ] Which video model wins on the eval set: Gemini native video or frames sent to another vision model?
- [ ] Should v2 accept multiple angles of the same incident?
- [ ] Is the IFAB's simplified "Football Rules" text a better fit for fan-facing explanations, with the full Laws kept for citations?

## Sources

- [Laws of the Game 2026/27, The IFAB](https://downloads.theifab.com/downloads/laws-of-the-game-202627-double-pages?l=en)
- [Law changes 2026/27, The IFAB](https://downloads.theifab.com/downloads/changes-to-the-laws-of-the-game-202627?l=en)
- [Gemini API: Video understanding](https://ai.google.dev/gemini-api/docs/generate-content/video-understanding)
- [SoccerNet MVFoul (GitHub)](https://github.com/SoccerNet/sn-mvfoul)
- [VARS paper (arXiv 2304.04617)](https://arxiv.org/abs/2304.04617)
- [X-VARS paper (arXiv 2404.06332)](https://arxiv.org/abs/2404.06332)
