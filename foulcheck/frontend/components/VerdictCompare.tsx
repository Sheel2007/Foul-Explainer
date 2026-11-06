"use client";

import { useEffect, useRef, useState } from "react";
import type { Example } from "@/lib/types";
import { Quote } from "./RulePanel";

const START = 100; // opens on the VAR side, then wipes across to show the difference
const REST = 40; // left of the contact box, so each side's notes sit clear of the handle
const WIPE_MS = 1100;
const WAIT_MS = 900;

// The three complaints about VAR, in the same order as the answers beside them.
const VAR_TODAY = [
  ["No explanation", "You mostly get the verdict."],
  ["Inconsistent", "It comes down to each referee's opinion."],
  ["Black box", "The review happens out of sight."],
];

// Column positions shared by both sides: the verdict band, then three rows that line up across the handle.
const ROWS = "absolute bottom-2 top-[43%] grid grid-rows-3 gap-1 sm:bottom-3 sm:top-[32%]";

/**
 * The hero visual: one frame under a drag handle. Left is what the stadium is told and VAR's three
 * problems; right is the tool's real output for that tackle, answering each problem on the same row.
 */
export default function VerdictCompare({ ex }: { ex: Example }) {
  const [pos, setPos] = useState(START);
  const touched = useRef(false);
  const contact = ex.story?.contact ?? ex.poster;
  const f = ex.facts;
  const [ymin, xmin, ymax, xmax] = (ex.moment.contact_box ?? [400, 400, 600, 600]).map((v) => v / 10);
  const quote = ex.ai.citations.find((c) => c.kind === "guidance" && c.quote) ?? ex.ai.citations.find((c) => c.quote);
  const card = ex.ai.card === "none" ? "No card" : `${ex.ai.card === "red" ? "Red" : "Yellow"} card`;
  const score = Math.round(ex.ai.confidence_detail.score * 100);
  const checks = [
    ["Studs", f?.studs_showing],
    ["Straight leg", f?.leg_straight],
    ["Lunge", f?.lunge],
  ] as const;

  // the opening wipe teaches the handle; it stops as soon as someone touches it
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const settle = window.setTimeout(() => setPos(REST), 0);
      return () => window.clearTimeout(settle);
    }
    let timer = 0;
    const begun = performance.now() + WAIT_MS;
    const tick = () => {
      if (touched.current) return;
      const t = Math.min(1, Math.max(0, (performance.now() - begun) / WIPE_MS));
      const eased = t * t * (3 - 2 * t);
      setPos(START + (REST - START) * eased);
      if (t < 1) timer = window.setTimeout(tick, 16);
    };
    timer = window.setTimeout(tick, WAIT_MS);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <figure className="min-w-0">
      <div className="relative aspect-[3/4] select-none overflow-hidden rounded-xl bg-[#0d110f] ring-1 ring-white/15 sm:aspect-video">
        {/* right side: Foul Explainer */}
        <div className="absolute inset-0">
          <div className="absolute inset-x-0 top-0 aspect-video overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={contact} alt="" className="h-full w-full object-cover" />
            <div className="absolute inset-y-0 right-0 w-1/2 bg-gradient-to-l from-black/90 via-black/75 to-transparent" />
            <span
              className="absolute rounded-[2px] border-2 border-red-500"
              style={{ left: `${xmin}%`, top: `${ymin}%`, width: `${xmax - xmin}%`, height: `${ymax - ymin}%` }}
            />
            {/* each answer points back at the contact */}
            <svg viewBox="0 0 1600 900" className="pointer-events-none absolute inset-0 hidden h-full w-full sm:block" aria-hidden>
              {[42, 62, 82].map((y) => (
                <path
                  key={y}
                  d={`M${61.5 * 16} ${y * 9} L${xmax * 16 + 8} ${Math.min(ymax - 4, Math.max(ymin + 4, y)) * 9}`}
                  stroke="#fff"
                  strokeWidth="2"
                  opacity="0.7"
                />
              ))}
            </svg>
          </div>
          <p className="absolute left-[60%] right-3 top-[12%] text-base font-bold leading-tight sm:left-[62%] sm:top-[15%] sm:text-2xl">{card}</p>
          <div className={`${ROWS} left-[42%] right-3 text-white sm:left-[62%]`}>
            <Answer name="The reason">
              {quote?.quote ? (
                <span className="line-clamp-4 italic sm:line-clamp-3">
                  “<Quote text={quote.quote} highlight={quote.highlight} />”
                </span>
              ) : (
                <span className="line-clamp-3">{ex.ai.explanation}</span>
              )}
            </Answer>
            <Answer name="Same checklist, every clip">
              {checks.map(([name, v]) => (
                <span key={name} className="mr-2 inline-block whitespace-nowrap">
                  {name} {v ? "✓" : v === false ? "✗" : "?"}
                </span>
              ))}
            </Answer>
            <Answer name="How sure, and why">
              {ex.ai.confidence}, {score}%
              {ex.moment.audit.second_opinion === "agree" && ". A second run agreed."}
            </Answer>
          </div>
          <Label className="right-3 sm:right-4">Foul Explainer</Label>
        </div>

        {/* left side: VAR today, clipped at the handle */}
        <div className="absolute inset-0 bg-[#0d110f]" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}>
          <div className="absolute inset-x-0 top-0 aspect-video overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={contact} alt="" className="h-full w-full object-cover brightness-[0.35] grayscale" />
          </div>
          <div className="absolute left-[2%] top-[9%] w-[35%] rounded bg-black py-[1.5%] text-center ring-1 ring-white/20 sm:top-[13%]">
            <p className="led-text text-[6px] tracking-[0.1em] text-amber-400 sm:text-[9px] sm:tracking-[0.18em]">VAR CHECK COMPLETE</p>
            <p className="led-text led-dots text-sm font-black tracking-[0.04em] text-red-500 sm:text-2xl">{card.toUpperCase()}</p>
          </div>
          <div className={`${ROWS} left-3 w-[33%] text-white sm:left-4`}>
            {VAR_TODAY.map(([name, text]) => (
              <div key={name} className="self-center text-[11px] leading-snug sm:text-[13px]">
                <p className="font-semibold">
                  <span className="mr-1 text-red-400">✗</span>
                  {name}
                </p>
                <p className="mt-0.5 text-white/70">{text}</p>
              </div>
            ))}
          </div>
          <Label className="left-3 sm:left-4">VAR today</Label>
        </div>

        {/* handle */}
        <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white" style={{ left: `${pos}%` }}>
          <span className="absolute left-1/2 top-[24%] grid h-9 w-9 sm:top-1/2 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white text-sm font-bold text-black shadow-lg">
            ↔
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={pos}
          aria-label="Compare what VAR shows with what Foul Explainer shows"
          onChange={(e) => {
            touched.current = true;
            setPos(Number(e.target.value));
          }}
          className="absolute inset-0 h-full w-full cursor-ew-resize touch-pan-y opacity-0"
        />
      </div>
      <figcaption className="mt-2 text-xs text-white/60">One real tackle, {ex.title.split(" · ")[0]}. Drag to compare.</figcaption>
    </figure>
  );
}

function Answer({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div className="self-center text-[11px] leading-snug sm:text-[13px]">
      <p className="font-semibold">
        <span className="mr-1 text-green-300">✓</span>
        {name}
      </p>
      <div className="mt-0.5 text-white/90">{children}</div>
    </div>
  );
}

function Label({ className, children }: { className: string; children: React.ReactNode }) {
  return (
    <span className={`absolute top-2 rounded bg-black/75 px-2 py-0.5 text-[11px] font-semibold text-white sm:top-3 sm:text-xs ${className}`}>
      {children}
    </span>
  );
}
