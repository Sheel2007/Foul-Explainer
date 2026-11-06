# Foul Explainer (foulcheck)

Full design: `../docs/build-plan.md`. This file holds the standing instructions from that plan plus notes learned while building.

## Instructions for the coding agent

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
- Do not commit API keys, source clips, or the Laws PDF (the silent site copies in `frontend/public/examples/` are the exception, by the user's choice). This folder is part of a monorepo; the ignore rules are in the root `.gitignore`.

## Commands (run from `backend/`)

- Build the rulebook store: `uv run python -m foulcheck.laws.build` (downloads the PDF if missing, adds any fetched referee guidance, writes `data/laws/<edition>/chunks.jsonl` and `laws.sqlite`)
- Fetch referee guidance pages (once, needs Google Chrome): `uv sync --extra fetch && uv run python -m foulcheck.laws.guidance fetch` -> `data/laws/<edition>/guidance/*.txt`, then rebuild the store
- Tests: `uv run pytest` (tests marked `data` skip when the store is not built). Real-API tests are marked `slow` and deselected by default; run them with `uv run pytest -m slow`
- Judge clips end to end: `uv run python -m foulcheck [CLIP ...] [--context "..."] [--json] [--decision-model ...]` (no clips = all of `eval/clips/`)
- Eval: `uv run python -m foulcheck.eval [--video model=...,l=2,i=12,think=low ...] [--decision MODEL|none] [--no-second-opinion]` -> `eval/results/<date>-<time>.csv/.md`. Labels: `uv run python -m foulcheck.eval.label CLIP --verdict ... --card ... --restart ... --sections 12.1,12.4 --difficulty clear --source ...` (or `--list`).
- Web app: API `uv run uvicorn foulcheck.api.app:app --port 8000` (from `backend/`), UI `npm run dev` (from `frontend/`, port 3000). The UI reads `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). Both are also in `.claude/launch.json` at the repo root for the browser pane (local, not committed).
- Explained videos (the main user-facing output): `uv run python -m foulcheck.explain CLIP [...] [--context ...] [--decision-model ...] [--video-model ...] [--rerender]` -> `explained/<name>_explained.mp4` + `<name>_ruling.json` (repo root, gitignored). `--rerender` redraws from the saved ruling with no model calls. User-facing usage is in `README.md`.
- Video step on clips: `uv run python -m foulcheck.video [CLIP ...] [--analyzer gemini|frames-gemini|frames-claude] [--json] [--no-cache]` (no clips = all of `eval/clips/`)

## Notes

- Edition is pinned in `foulcheck/config.py` (`LAWS_EDITION`, default `2026-27`). A new edition = add an entry to `EDITIONS` and rebuild.
- In the 2026/27 text, Law 12 sections are: 12.1 Direct free kick, 12.2 Indirect free kick, 12.3 Corner kick (new: goalkeeper 8-second rule), 12.4 Disciplinary action, 12.5 Restart of play after fouls and misconduct. Disciplinary action is 12.4, not 12.3.
- The PDF is double-page spreads; `parse.py` splits each page at the midline and takes the Law from the running footer.
- `normalize()` in `laws/parse.py` is the canonical text form. The Phase 3 citation guard must compare quotes using it.
- `tags.py` selectors raise at build time if they match nothing, so a re-laid-out edition fails loudly instead of silently losing rules.
- Embeddings: local FastEmbed `BAAI/bge-small-en-v1.5` (no API key). Tests use `HashEmbedder`.
- Vector hits are limited to Laws 12, 13, 14 and referee guidance (`VECTOR_LAWS` in `retrieve.py`) since v1 judges under Law 12.
- Referee guidance (`laws/guidance.py`): the Laws have no studs/ankle wording; the specifics (e.g. PL "High + Full + Forceful contact on ankle or above is considered dangerous = Red card") are in Premier League and UEFA guidance pages. 11 pages (`SOURCES`) are saved as text, split at headings into chunks with `kind="guidance"`, `law` = publisher ("PL"/"UEFA"), `section` = page slug, `url` = page. `GUIDANCE_MAP` in `tags.py` tags them; its selectors only fail the build when their page was fetched. Any contact raises `contact_severity`, which forces the PL point-of-contact passage into retrieval. The prompt marks them REFEREE GUIDANCE (Laws decide). Citations carry `kind`; for guidance `section` is the publisher and `source_url` the page. Copyright: quoting these is fine for a personal/demo tool; a public launch should show summaries plus links.
- All model calls go through `foulcheck/llm.py` (`call` for retries/logging, `generate_json` for Pydantic parsing + one repair retry). Logs land in `logs/<date>/`.
- Video outputs are cached in `backend/data/cache/video/<sha>/<analyzer-id>/`; delete or pass `--no-cache` after prompt changes.
- Clips often contain the live action plus slow-motion replays. The locate pass lists every view and picks the clearest; the inspect pass runs on that view only.
- `check_neutral` in `video/base.py` rejects ruling words ("foul", "reckless", "card"...) in video output and triggers the repair retry.
- Default video model `gemini-3.8-flash` (stable). Gemini returns 503 "high demand" often. On the free tier failed requests still count toward the daily quota, so `llm.call` gives 503/504 only 3 attempts (20 s, 60 s gaps), waits out per-minute 429s using the server's retryDelay (limit is 5 requests/minute/model), and never retries daily-quota 429s. Don't run two evals on the same model at once.

- Decision engine (`foulcheck/decision/`): runs two drafts in parallel (temperatures 0.4 and 1.0). The first passes through the citation guard (unknown chunk IDs and non-verbatim quotes trigger one rerun, then quotes are dropped and section refs kept). The second only feeds the disagreement check in `confidence.py`.
- Confidence = model score minus penalties (key uncertain fields, unclear view, restart/location mismatch, reliance on user context, second-run disagreement, and -0.25 for a red card resting on studs or high force read from video, with a matching gray area: both decision runs read the same facts, so their agreement can't catch a misread). Shown as High >= 0.75, Medium >= 0.5, else Low.
- Gemini free tier allows 20 requests/day per model. A full clip costs 4 calls (2 video + 2 decision). Daily-quota 429s are not retried.
- The guard requires the restart and card to be grounded in a cited passage (penalty -> a chunk tagged `penalty_kick`, DFK -> 12.1, IFK -> 12.2, card -> 12.4); on a second miss the engine adds that citation itself. Quotes may skip words with "..."/"…"/"[...]" or skip list items at a bullet: each piece must be verbatim, in order, and pieces cut by "..." need 2+ words. No length cap. Rulings carry an `audit` dict used by the eval.
- Retrieval always includes the best chunk for `MANDATORY_TAGS` (definitions, and the penalty-award passage when the observation is in the box).
- Video cache layout: `data/cache/video/<sha16>/<analyzer name>/locate-<PROMPT_VERSION>-l<fps>.json` and `inspect-<PROMPT_VERSION>-l<fps>-i<fps>-<start>-<end>.json`, each with a `.meta.json` timing sidecar. Bump `PROMPT_VERSION` in `video/prompts.py` when a video prompt changes.
- Clip 1 became a handball on 2026-11-05 (Liverpool v Real Madrid; answer key from the owner on 2026-11-06: handball, penalty, no red, recorded as no card); the old clip, label and ruling are in `explained/previous-clip-1/`. Labels in `eval/labels/`: ruling labels for clips 2-5 from the project owner (2026-10-24; restart for 2-4 inferred as DFK), fact labels (`contact_times`) verified frame by frame. No difficulty labels yet.
- Phase 5 findings (`eval/results/2026-10-24-phase5-summary.md`): the default pipeline (3.8-flash video + 3.6-flash decisions) on the 5 labelled clips scored verdict 5/5 (but every label is "foul"), card 4/5 (clip 2 red called yellow), restart 5/5, citation recall 100%, first drafts 5/5 passing the guard. Latency is the unmet target: median 213 s, max 335 s. `think=low` gave no speed-up in the 2 locate passes that got through. The all-lite pipeline is 14 s median but misplaces location and incident. The user wants to stay on the free Gemini tier (20 requests/model/day, resets midnight Pacific).
- 2026-11-02 re-run with referee guidance + prompt scoping (guidance applies to its topic; a slide/lunge alone = careless): cards 4/5 right (2 red, 4 none, 5 none, 3 yellow from the 2026-11-01 ruling since its re-run hit 503/504; 1 yellow vs label none, Low confidence). Before the prompt scoping, the PL line "Contact on foot only is typically considered reckless = Yellow card" pushed clips 4 and 5 to yellow.
- 2026-11-04: `gemini-3.8-flash` video calls returned 503/504 on every try for days (clip 3: 0 of 30 since Nov 2; a clip 2 control failed too), so it was overload, not the clip or the key. A run of clip 3 with `--video-model gemini-3.6-flash` worked but said studs + high force = red (label yellow; 3.8-flash's wide-shot run said instep, medium force, yellow). Treat 3.6-flash video as not comparable until evaluated. The user chose to publish it, wrong call included, for transparency; the Nov 1 yellow is in `explained/previous-2026-11-02/`. The site labels clips whose video model differs from the rest. Diagnosis: the close-up reported studs and high force with no doubt listed (3.8-flash's close-ups marked studs uncertain on clips 1, 4 and 5); that one fact adds the `serious_foul_play` and `excessive_force` tags and passages, and both decision runs read the same facts, so "second run agreed" can't catch a video error and confidence stayed 95%.
- Open gap: the video model claimed certainty on a contact right at the penalty-area corner (clip 5).

- API (`foulcheck/api/`): `POST /api/jobs` (multipart file + context) -> job; `GET /api/jobs/{id}/events` (SSE `status` events); `GET /api/jobs/{id}/result`; `POST /api/feedback` (appends to `backend/data/feedback/feedback.jsonl`). Jobs live in memory; uploads are deleted when a job ends.
- Frontend is Next.js 16 (`cacheComponents` on) + Tailwind 4. Read `frontend/node_modules/next/dist/docs/` before changing Next-specific code (see `frontend/AGENTS.md`). The page is one client component tree under `components/FoulExplainer.tsx`; theme colours are tokens in `app/globals.css`.

- Video step has three passes for the default Gemini analyzer: locate (2 fps, whole clip), inspect (12 fps window; also returns `contact_box`), and a close-up (`closeup()`: ffmpeg crops the box from ±0.6 s around contact, enlarges it, and asks only boot questions). Close-up answers replace the wide-shot `challenge`/body-part fields (`merge_closeup`). Added because broadcast clips are ~640×360: the wide shot called clip 2's studs-up lunge "instep". Cache versions: `LOCATE_VERSION`, `INSPECT_VERSION`, `CLOSEUP_VERSION` in `video/prompts.py`.
- Only studs seen (`challenge.studs_showing` or body part "studs/sole") raise the `serious_foul_play` tag, which forces both Law 12.4 serious-foul-play passages into retrieval. A lunge or straight leg alone only points to reckless (clip 1 was wrongly red-carded when lunge+straight leg counted).
- API keys: `POST /api/jobs` takes a visitor's key in `X-Api-Key`; it is passed to the runner and dropped (not on `Job`, not logged; masked in error logs). `providers.py` detects the company from the prefix (`AIza` Gemini, `sk-ant-` Anthropic, `sk-` OpenAI) and runs both steps on it: Gemini watches the video, the others use `FrameSequenceAnalyzer` (still frames, plus the close-up). Other companies are refused. Claude and OpenAI have only been tested with mocks and fake keys, not a real analysis; `OPENAI_MODEL` defaults to the id in OpenAI's vision guide. The server's `.env` key is used only if `FOULCHECK_ALLOW_SERVER_KEY=1`. `GET /api/config` tells the UI whether a key is required.
- Site: `/` opens on "VAR tells you what. Foul Explainer shows you why." beside one visual (`components/VerdictCompare.tsx`): a frame under a drag handle, with the verdict and VAR's three problems (no explanation, inconsistent, black box) on the left and the tool's real answers on matching rows on the right. The user wants this terse, built into the visual, not as text below. Keep claims about VAR sourced and fair: in-stadium announcements now exist, so don't say fans get no explanation at all. Sources are in the footer. Next is the pipeline (`components/Pipeline.tsx`): a static timeline of 8 steps with real stills and labelled arrows, built from `examples.json` `story` and `moment`. No video here: the user tried and rejected scroll-scrubbing, scroll-pinned steps and a self-playing walkthrough. They also dislike icon-like visuals (coloured card rectangles, gauges, stamps), so steps 6 and 8 show real data and tables. It is plain, with no scroll-in animation and no result strip at the end. Then the "5 real incidents" viewer (`frontend/data/examples.json`: clip plus a picker on the left; on the right a panel the same height with the call, answer key and tabs Why / The rule / How sure / What it saw), then the upload tool (`FoulExplainer embedded`, section `#try`). `/try` is the plain tool. Regenerate examples with `uv run python -m foulcheck.explain.examples` (renders `<n>_clip.mp4` with CONTACT tags only via `render_video(panel=False)`, plus, for `STORY_ID`, a tag-free copy `<n>_story.mp4`, a film strip, the contact frame and the close-up crop; no model calls). `frontend/public/examples/` is committed, so re-export before pushing.
- Hosting: Vercel builds from GitHub on each push, with Root Directory `foulcheck/frontend`. The user chose to commit `public/examples/` (silent site clips and stills) so builds have them; they decided against Vercel Blob. Vercel can only host the frontend: the backend needs ffmpeg and multi-minute jobs. With `NEXT_PUBLIC_API_URL` unset, a production build shows `components/UploadUnavailable.tsx` in place of the upload tool.
- Confidence is shown as a breakdown (`components/ConfidenceBreakdown.tsx`, `lib/confidence.ts` turns the backend's adjustment strings into sentences): model's own rating, each deduction, unclear facts, gray areas. If `confidence.py` changes its note wording, update `lib/confidence.ts`.
- Everything the website serves is silent: `render_video(audio=False)` for the examples export and the API's renders; players are `muted`.
- Explained video (`foulcheck/explain/`): `panel.py` draws the side panel with Pillow (this ffmpeg has no drawtext); `render.py` scales the clip to 720 px high, hstacks the 640 px panel on the right, and overlays a red CONTACT tag on the video (top left) at each view's contact time. The panel shrinks text, then drops the gray area and a citation, until everything fits. Citations carry a `highlight` (model-picked words, kept only if inside the quote; else a keyword fallback in `guard.py`). Chunk IDs are stripped from fan-facing text.
- Web app renders the explained video as a 4th job stage; `GET /api/jobs/{id}/video` serves it. Renders live in `backend/data/renders/`, deleted after 2 h (`RENDER_TTL_S`). A failed render keeps the ruling (note added).

## Progress

- [x] Phase 1: Rulebook pipeline (done-when test: `tests/test_retrieve.py::test_phase1_done_when_studs_tackle_returns_reckless_and_excessive_force`)
- [x] Phase 2: Video analyzer (5 sample clips in `eval/clips/` give valid observations; contact times checked against frames)
- [x] Phase 3: Decision engine (all 5 sample clips print full rulings with guard-verified citations)
- [x] Phase 4: Web app (clip 5 uploaded in the browser; verdict, key-moment marker, rule panel, gray areas, feedback all shown)
- [x] Explained-video pipeline (CLI + web download); all 5 sample clips rendered in `explained/`
- [~] Phase 5: Evaluation and tuning. Harness, labels for 5 clips, default-pipeline eval done; all targets met except latency (honest uncertainty not measurable). Open: 45 more clips (incl. non-fouls and handball), difficulty labels, latency (see `eval/results/2026-10-24-phase5-summary.md`)
