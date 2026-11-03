"use client";

import { useState } from "react";
import { RESTART_LABEL, VERDICT_LABEL } from "@/lib/format";
import type { Example } from "@/lib/types";
import ConfidenceBreakdown from "./ConfidenceBreakdown";
import { Quote, sourceLabel } from "./RulePanel";

const CARD = { none: "No card", yellow: "Yellow card", red: "Red card" } as const;
const TABS = ["Why", "The rule", "How sure", "What it saw"] as const;
type Tab = (typeof TABS)[number];

const yes = (v: boolean | null | undefined) => (v === null || v === undefined ? "Not visible" : v ? "Yes" : "No");

// the most specific quotes first: referee guidance, then card passages, then the rest
const specificity = (c: { kind?: string; section: string }) => (c.kind === "guidance" ? 0 : c.section === "12.4" ? 1 : 2);

function Fact({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line py-1.5 text-sm last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right first-letter:uppercase">{value ?? "Not visible"}</dd>
    </div>
  );
}

function Mark({ ok }: { ok: boolean | null }) {
  if (ok === null) return null;
  return <span className={ok ? "text-pitch" : "text-red-500"}>{ok ? " ✓" : " ✗"}</span>;
}

/** The test clips: video on the left, and beside it a panel the same height with the call and tabs for the detail. */
export default function ExamplesViewer({ examples }: { examples: Example[] }) {
  const [i, setI] = useState(0);
  const [tab, setTab] = useState<Tab>("Why");
  const ex = examples[i];
  const f = ex.facts;
  const label = ex.label;
  const right = (k: "verdict" | "card") => examples.filter((e) => e.label?.[k] && e.ai[k] === e.label[k]).length;
  const labelled = (k: "verdict" | "card") => examples.filter((e) => e.label?.[k]).length;
  const rules = ex.ai.citations
    .filter((c) => c.quote)
    .sort((a, b) => specificity(a) - specificity(b))
    .slice(0, 3);
  const detail = ex.ai.confidence_detail;
  const is = (k: "verdict" | "restart" | "card") => (label?.[k] ? ex.ai[k] === label[k] : null);

  return (
    <section id="examples" className="scroll-mt-16 border-t border-line py-20">
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="text-sm font-medium text-pitch">See it work</p>
            <h2 className="mt-1 text-3xl font-semibold tracking-tight sm:text-4xl">{examples.length} real tackles, judged</h2>
            <p className="mt-3 max-w-xl text-muted">
              Pick a clip. Beside it: the call, why, the rule it used, how sure it was, and whether it matched the answer key.
            </p>
          </div>
          <p className="text-sm text-muted">
            Right call <b className="text-foreground">{right("verdict")}/{labelled("verdict")}</b> · right card{" "}
            <b className="text-foreground">{right("card")}/{labelled("card")}</b>
          </p>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          {/* left: the clip and the clip picker */}
          <div className="space-y-3">
            <video
              key={ex.id}
              src={ex.video}
              poster={ex.poster}
              controls
              autoPlay
              muted
              loop
              playsInline
              className="aspect-video w-full rounded-2xl bg-black"
            />
            <div role="tablist" aria-label="Test clips" className="grid grid-cols-5 gap-2">
              {examples.map((e, n) => {
                const ok = !e.label?.card || e.ai.card === e.label.card;
                return (
                  <button
                    key={e.id}
                    role="tab"
                    aria-selected={n === i}
                    title={e.title}
                    onClick={() => setI(n)}
                    className={`group relative overflow-hidden rounded-lg text-left transition ${n === i ? "ring-2 ring-pitch" : "opacity-60 hover:opacity-100"}`}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={e.poster} alt={e.title} className="aspect-video w-full object-cover" />
                    <span className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/85 to-transparent px-1.5 pb-1 pt-4 text-[11px] font-medium text-white">
                      <span className="flex items-center gap-1">
                        {e.ai.card !== "none" && (
                          <span className={`inline-block h-3 w-2 rounded-[2px] ${e.ai.card === "red" ? "bg-red-600" : "bg-yellow-400"}`} />
                        )}
                        <span className="hidden sm:inline">{e.ai.card === "none" ? "No card" : e.ai.card === "red" ? "Red" : "Yellow"}</span>
                      </span>
                      {e.label && <span className={ok ? "text-green-300" : "text-red-400"}>{ok ? "✓" : "✗"}</span>}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* right: same height as the left column on wide screens; the tab body scrolls if it must */}
          <div className="lg:relative">
            <div className="flex flex-col overflow-hidden rounded-2xl border border-line bg-surface lg:absolute lg:inset-0">
              <div className="border-b border-line p-5">
                <p className="text-xs text-muted">{ex.title}</p>
                <div className="mt-1 flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-2xl font-bold tracking-tight">
                      {VERDICT_LABEL[ex.ai.verdict]}
                      {ex.ai.card !== "none" && <span className="font-semibold"> · {CARD[ex.ai.card]}</span>}
                    </p>
                    <p className="text-sm text-muted">
                      {RESTART_LABEL[ex.ai.restart]}
                      {ex.ai.offence_type && <span className="first-letter:uppercase"> · {ex.ai.offence_type}</span>}
                    </p>
                  </div>
                  {ex.ai.card !== "none" && (
                    <span aria-hidden className={`h-10 w-7 shrink-0 rotate-6 rounded-md shadow ${ex.ai.card === "yellow" ? "bg-yellow-400" : "bg-red-600"}`} />
                  )}
                </div>
                {label && (
                  <p className="mt-3 text-xs text-muted">
                    Answer key: {label.verdict ? VERDICT_LABEL[label.verdict] : "–"}
                    <Mark ok={is("verdict")} /> · {label.restart ? RESTART_LABEL[label.restart] : "–"}
                    <Mark ok={is("restart")} /> · {label.card ? CARD[label.card] : "–"}
                    <Mark ok={is("card")} />
                  </p>
                )}
              </div>

              <div role="tablist" aria-label="Details" className="flex border-b border-line px-2">
                {TABS.map((t) => (
                  <button
                    key={t}
                    role="tab"
                    aria-selected={tab === t}
                    onClick={() => setTab(t)}
                    className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm transition ${tab === t ? "border-pitch font-medium text-foreground" : "border-transparent text-muted hover:text-foreground"}`}
                  >
                    {t}
                    {t === "How sure" && (
                      <span className={`ml-1.5 text-xs ${ex.ai.confidence === "High" ? "text-pitch" : ex.ai.confidence === "Medium" ? "text-amber-500" : "text-red-500"}`}>
                        {Math.round(detail.score * 100)}%
                      </span>
                    )}
                  </button>
                ))}
              </div>

              <div role="tabpanel" className="min-h-0 flex-1 overflow-y-auto p-5">
                {tab === "Why" && <p className="text-sm leading-relaxed">{ex.ai.explanation}</p>}

                {tab === "The rule" && (
                  <div className="space-y-4">
                    {rules.map((rule) => (
                      <div key={rule.quote}>
                        <blockquote className="border-l-2 border-pitch pl-3 text-sm italic leading-relaxed">
                          “<Quote text={rule.quote!} highlight={rule.highlight} />”
                        </blockquote>
                        <a
                          href={rule.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-1 inline-block pl-3 text-xs text-muted underline-offset-2 hover:underline"
                        >
                          {sourceLabel(rule)} ↗
                        </a>
                      </div>
                    ))}
                  </div>
                )}

                {tab === "How sure" && (
                  <ConfidenceBreakdown
                    level={ex.ai.confidence}
                    modelScore={detail.model_score}
                    score={detail.score}
                    adjustments={detail.adjustments}
                    uncertainFields={ex.ai.uncertain_fields}
                    grayAreas={ex.ai.gray_areas}
                  />
                )}

                {tab === "What it saw" && f && (
                  <>
                    <dl>
                      <Fact label="Challenge" value={f.challenge_type} />
                      <Fact label="Contact" value={[f.body_part_used, f.body_part_hit].filter(Boolean).join(" → ") || null} />
                      <Fact label="Studs showing" value={yes(f.studs_showing)} />
                      <Fact label="Straight leg / lunge" value={`${yes(f.leg_straight)} / ${yes(f.lunge)}`} />
                      <Fact label="Ball played first" value={yes(f.ball_played_first)} />
                      <Fact label="Speed and force" value={f.speed_and_force} />
                    </dl>
                    {f.boot_detail && <p className="mt-3 text-sm italic text-muted">{f.boot_detail}</p>}
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
