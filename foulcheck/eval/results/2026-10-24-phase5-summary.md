# Phase 5 summary (2026-10-24, updated 2026-10-28)

Labels: `eval/labels/*.json`. Ruling labels come from the project owner. Restart for clips 1-4 is inferred as a direct free kick (fouls, not penalties). Contact times were checked frame by frame. No difficulty labels, so every clip counts as a clear case.

| Clip | Label |
|---|---|
| 1 | Foul, no card |
| 2 | Foul, red card |
| 3 | Foul, yellow card |
| 4 | Foul, no card |
| 5 | Foul, penalty, no card |

All runs used the free Gemini tier (20 requests per model per day). Each run used whichever models had quota left, so no single configuration was run cleanly with every fix in place.

## Runs on the labelled clips

| Run | Video model | Decision model | Fixes in place | Verdict | Card | Restart | Citation recall | First drafts passing guard | Model time (median / max) | Report |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 3.8-flash, 12 fps | 3.1-flash-lite, two runs | no | 5/5 | 3/5 | 5/5 | 100% | 0/5 | 171 s / 236 s | `210226` |
| B | 3.8-flash, 12 fps | 3-flash-preview, two runs | no | 5/5 | 3/5 | 5/5 | 100% | 2/5 | 340 s / 834 s | `211937` |
| C | 3.5-flash-lite, 6 fps | 3.5-flash-lite, one run | no | 5/5 | 3/5 | 4/5 | 80% | 2/5 | **14 s / 42 s** | `210200` |
| D | 3.8-flash, 12 fps | 3-flash-preview, one run | yes | 3/3 | 0/3 | 3/3 | 100% | **3/3** | 139 s / 166 s | `212251` (clips 3 and 5 hit the quota) |
| **E (default)** | 3.8-flash, 12 fps | 3.6-flash, two runs | yes | **5/5** | **4/5** | **5/5** | **100%** | **5/5** | 213 s / 335 s | `2026-10-25-*` (clips 1-3) + `2026-10-28-*` (clips 4, 5) |

The video-only comparison is in `2052`.

## v1 targets

| Target | v1 goal | Status | Evidence |
|---|---|---|---|
| Verdict accuracy (clear cases) | ≥ 75% | Met (default: 5/5), but weak evidence | 100% in every run. All 5 labels are "foul", so a system that always said foul would also score 100%. Clear non-fouls and handball clips are needed to test this. |
| Card accuracy | ≥ 60% | Met by the default pipeline: 4/5 (80%). Runs A–C: 3/5; D: 0/3 | Still the weakest area, and n = 5. The default pipeline's one miss is clip 2. Clip 4, over-carded in earlier runs, came out correctly as no card in E. Clip 2 (red) was given yellow in every run: the video saw "foot → ankle, ball played first", with no studs or lunge. Clip 4 (no card) was given yellow whenever the video was 3.8-flash, because the model saw an attack towards goal and cited stopping a promising attack. Run C reached 3/5 by giving no card on every clip. Run D also gave clip 1 a yellow where A and B gave none, so single-run card calls vary. |
| Citation recall | ≥ 90% | Met (default: 100%) | 80% in run C, because clips 2 and 3 got no card and so cited no 12.4 passage. |
| Citation precision | 100% | Met by design | Shown quotes are always verbatim. First drafts used to fail the guard often (0–40%), which forced slow reruns. After the fixes, all 5 first drafts in the default pipeline passed (run D: 3/3), so no reruns were needed. |
| Honest uncertainty | Most hard clips Medium/Low | Not measurable | No difficulty labels. Clip 1 (distant, partly blocked view) was rated Low in every run with 3.8-flash video. |
| Latency | < 45 s | Missed by the default pipeline (median 213 s, max 335 s). Met only by the all-lite pipeline (run C: median 14 s, max 42 s) | In the default pipeline the decision step alone took 13–124 s (median 54 s). Lite pays for its speed in accuracy: contact time within 0.3 s on 1/4 clips (3.8-flash: 4/4), the wrong incident on clip 1, and a midfield tackle placed "inside penalty area" on clip 3, which became a wrong penalty. With 3.8-flash video, the video passes alone take 98–228 s. |

## Fixes made from these results

1. **Elided quotes:** the guard now accepts quotes that skip words with "...", "…" or "[...]", or skip list items at a bullet. Every piece must appear word for word and in order, and a piece cut by "..." must be at least two words. Almost every rejection was a correct quote of Law 12.1's list opening plus one bullet.
2. **No 40-word cap:** the guard no longer rejects long verbatim quotes. A rerun to shorten an honest quote cost 10–200 s.
3. **Penalty retrieval:** the passage that awards a penalty is always retrieved when the observation is inside the penalty area. Before, it could be cut by the 8-chunk cap, leaving only Law 14 procedure text such as "the ball is in play when it is kicked".
4. **Penalty grounding:** a penalty now only counts as grounded by a passage tagged as awarding a penalty, not by any Law 14 text.
5. **Prompt:** the decision prompt now says to cite the passage that sets the restart and, for a card, a disciplinary passage, and to mark skipped words with "...".
6. **Label isolation bug:** a unit test was writing to the real `eval/labels/2.json`. Fixed and verified.
7. **New metric:** restart accuracy.

## 2026-10-25 run after the quota reset

- **Default pipeline (run E):** 3.8-flash video (cached) + 3.6-flash decisions with the second opinion, all fixes in place.
  - **Clip 1:** foul, direct free kick, no card. Correct. Low confidence, from the distant view and unsure facts.
  - **Clip 3:** foul, direct free kick, yellow. Correct. High confidence.
  - Both first drafts passed the guard, and both second opinions agreed.
  - **Clip 2** (second run, 08:30 EDT): foul, direct free kick, yellow. Wrong card (label: red), High confidence. The first draft passed the guard; the second opinion couldn't run (quota). Decision step 13.5 s.
  - The decision step alone took 47 s and 124 s, so the default pipeline misses the 45 s target even with video cached.
  - **Clips 2, 4 and 5 got no ruling.** Gemini returned 503 "overloaded", then the daily and per-minute quotas ran out.
- **3.8-flash `think=low` video run:** no results.
  - 17 of the 20 daily 3.8-flash requests were 503s, plus one 504 timeout.
  - The quota was gone before any clip finished.
- **Cause:** on the free tier, failed requests count toward the daily quota, and the old policy retried 503s up to 5 times. Running two evals at once also hit the 5-requests-per-minute limit on 3.6-flash.
- **Second attempt (08:30 EDT, same Pacific day):** the quota had not actually reset. Free-tier quotas reset at midnight Pacific (03:00 EDT), and the earlier run that morning had already used up both models' daily quota for that Pacific day. Only clip 2's first decision got through; clips 4 and 5 and every `think=low` call returned daily-quota 429s. The new retry policy stopped each one after a single attempt, so no further quota was wasted.
- **Retry policy now:**
  - **Per-minute 429:** waits the delay the server asks for (about 55 s), then retries.
  - **503/504:** at most 3 attempts, 20 s then 60 s apart.
  - **Daily-quota 429:** fails at once.

## 2026-10-28 run

- **Default pipeline, clips 4 and 5:** both correct.
  - **Clip 4:** foul, direct free kick, no card.
  - **Clip 5:** foul, penalty kick, no card. It cited Law 14, which earlier runs never did.
  - Both High confidence; first drafts passed the guard and the second opinions agreed. Decision step 59 s and 54 s.
  - The default pipeline now covers all 5 clips (row E).
- **3.8-flash `think=low` video run:** again no complete result. All 15 requests were 503s, and the new policy stopped each clip after 3 attempts.
- **What exists for `think=low`:** only two locate passes, from the Oct 25 run, timing successful attempts only.

  | Clip | `think=low` | Default thinking | Contact chosen with `think=low` (label) |
  |---|---|---|---|
  | 1 | 86 s | 51 s | 05.1 (label 5.0) |
  | 2 | 62 s | 50 s | 03.5 (label 3.85) |

  Neither was faster. With two samples on different days of heavy Gemini load this isn't conclusive, but it gives no reason to think thinking time is the bottleneck. 3.8-flash latency looks dominated by service load (frequent 503s, variable response times).

## Still open

- **Latency is the main unmet v1 target.** `think=low` doesn't look like the fix. Options:
  - a middle model (`gemini-3.6-flash`) for video, once its quota isn't shared with the decision step on the same day;
  - 3.5-flash-lite for locate plus 3.8-flash for inspect;
  - fewer inspect frames.

  Each needs measuring against the contact-time labels.
- **Card calibration:** possible levers are retrieving more of the disciplinary passages (the 8-chunk cap dropped serious-foul-play p2 on clip 2; vector search filled two slots with irrelevant passages) and asking the video model whether studs were showing. Do not tune on 5 clips; it needs the 50-clip set.
- **The clip set:** 45 more clips, including clear non-fouls and handball (both ways), plus difficulty labels.
