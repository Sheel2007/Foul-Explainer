# Foul Explainer

Upload a short clip of one soccer incident. You get back the call and the rule behind it, on the page and as a video with a panel beside the clip:

- **The call:** foul / no foul / handball, the restart, and any card, with a confidence level.
- **The key moment:** a red CONTACT strip lights up each time the contact is shown, live and in every replay.
- **Why:** a plain-language explanation.
- **The rule:** quotes from the Laws of the Game 2026/27, with the words that decide the case highlighted, plus official Premier League and UEFA referee guidance where the Laws leave the detail to judgement (for example, contact at or above the ankle with studs is a red card).

It is an explanation of how the Laws apply to what the model saw, not an official ruling.

## Setup (once)

- Install `ffmpeg` and `uv`.
- Put `GEMINI_API_KEY=...` in `foulcheck/.env`. The free tier works; it allows about 5 clips a day.
- To let the web app use that key when a visitor doesn't enter their own, also set
  `FOULCHECK_ALLOW_SERVER_KEY=1` in `.env`. Leave it unset on a public site, so visitors must bring their own free Gemini key.
- Optional, once: save the Premier League and UEFA referee guidance pages (needs Google Chrome installed), from `backend/`:

  ```bash
  uv sync --extra fetch && uv run python -m foulcheck.laws.guidance fetch
  ```

- Build the rulebook, from `backend/` (includes the guidance if you fetched it):

  ```bash
  uv run python -m foulcheck.laws.build
  ```

## Option 1: the web app

Start the API from `backend/`:

```bash
uv run uvicorn foulcheck.api.app:app --port 8000
```

Then start the page from `frontend/` (the first time, run `npm install` there):

```bash
npm run dev
```

Open http://localhost:3000, drop in a clip (MP4, MOV or WebM, up to 60 s), and wait.

- **API keys:** a visitor's key is sent only with that upload, held in memory for that one analysis, and never written to disk, logs or the browser. Your own key lives only in `.env`.
- **Homepage examples:** the walkthrough, pipeline diagram and "5 real incidents, judged" section are built from the test clips in `eval/clips/` and their saved rulings. Refresh them after re-running the clips, from `backend/`:

  ```bash
  uv run python -m foulcheck.explain.examples
  ```

  The videos stay out of git (broadcast footage), so a fresh clone shows these sections without video until you add your own clips, run them and export.

- The page shows the call, the explanation and the highlighted rules next to your clip.
- **Download the explained video** gives you the clip with the panel beside it.
- Uploaded clips are deleted after analysis. Explained videos are kept on the server for 2 hours.

## Option 2: one command

From `backend/`:

```bash
uv run python -m foulcheck.explain path/to/clip.mp4
```

- This writes `explained/<name>_explained.mp4` and `explained/<name>_ruling.json` in the repo root.
- `--context "it was inside the box"` adds a hint the model treats as a claim, not a fact.
- You can pass several clips at once.
- `--rerender` redraws the video from the saved ruling without calling any model.

## Limits

- One incident per clip; 5–30 s works best.
- v1 judges fouls, handball and cards under Law 12. It does not judge offside or goal-line calls.
- On the free Gemini tier each clip uses 4 requests, and a full analysis takes 2–5 minutes.
