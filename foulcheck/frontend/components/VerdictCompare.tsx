"use client";

import { useEffect, useRef, useState } from "react";
import type { Example } from "@/lib/types";
import { Quote, sourceLabel } from "./RulePanel";

const START = 100; // opens on the VAR side, then wipes across to show the difference
const REST = 40; // left of the contact box, so each side's text sits clear of the handle
const WIPE_MS = 1100;
const WAIT_MS = 900;

/** The same frame twice under a drag handle: what the stadium is told, and what this tool shows. */
export default function VerdictCompare({ ex }: { ex: Example }) {
  const [pos, setPos] = useState(START);
  const touched = useRef(false);
  const contact = ex.story?.contact ?? ex.poster;
  const [ymin, xmin, ymax, xmax] = (ex.moment.contact_box ?? [400, 400, 600, 600]).map((v) => v / 10);
  const quote = ex.ai.citations.find((c) => c.kind === "guidance" && c.quote) ?? ex.ai.citations.find((c) => c.quote);
  const card = ex.ai.card === "none" ? "No card" : `${ex.ai.card === "red" ? "Red" : "Yellow"} card`;
  const facts = [ex.facts?.body_part_used, ex.facts?.body_part_hit].filter(Boolean).join(" → ");

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
      <div className="relative aspect-video select-none overflow-hidden rounded-xl bg-black ring-1 ring-white/15">
        {/* right side: Foul Explainer */}
        <div className="absolute inset-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={contact} alt="" className="h-full w-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/10 to-black/30" />
          <span
            className="absolute rounded-[2px] border-2 border-red-500"
            style={{ left: `${xmin}%`, top: `${ymin}%`, width: `${xmax - xmin}%`, height: `${ymax - ymin}%` }}
          />
          <div
            className="absolute -translate-y-full border-l-2 border-red-500 pb-1 pl-2 text-[10px] font-semibold text-white first-letter:uppercase sm:text-sm"
            style={{ left: `${xmax + 1}%`, top: `${ymin + 8}%` }}
          >
            {facts}
          </div>
          <div className="absolute bottom-2 left-[60%] right-3 sm:bottom-4 sm:right-4">
            <div className="text-[11px] font-semibold leading-tight text-white sm:text-sm">
              <span className="block">{card}</span>
              <span className="block text-green-300">
                {ex.ai.confidence} confidence, {Math.round(ex.ai.confidence_detail.score * 100)}%
              </span>
            </div>
            {quote?.quote && (
              <>
                <p className="mt-1 hidden text-xs italic leading-snug text-white sm:block">
                  “<Quote text={quote.quote} highlight={quote.highlight} />”
                </p>
                <p className="mt-0.5 hidden text-[10px] text-white/70 sm:block">{sourceLabel(quote)}</p>
              </>
            )}
          </div>
          <Label className="right-3 sm:right-4">Foul Explainer</Label>
        </div>

        {/* left side: VAR today, clipped at the handle */}
        <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={contact} alt="" className="h-full w-full object-cover brightness-[0.45] grayscale" />
          <div className="absolute inset-y-0 left-0 grid w-[40%] place-items-center">
            <div className="w-[88%] rounded bg-black py-[7%] text-center ring-1 ring-white/20">
              <p className="led-text text-[7px] tracking-[0.12em] text-amber-400 sm:text-[11px] sm:tracking-[0.2em]">VAR CHECK COMPLETE</p>
              <p className="led-text mt-1 text-sm font-black tracking-[0.06em] text-red-500 led-dots sm:text-3xl">{card.toUpperCase()}</p>
            </div>
          </div>
          <Label className="left-3 sm:left-4">VAR today</Label>
        </div>

        {/* handle */}
        <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white" style={{ left: `${pos}%` }}>
          <span className="absolute left-1/2 top-1/2 grid h-9 w-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white text-sm font-bold text-black shadow-lg">
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
      <figcaption className="mt-2 text-xs text-white/60">
        One real tackle, {ex.title.split(" · ")[0]}. Drag to compare. On the right is the tool&apos;s actual output.
      </figcaption>
    </figure>
  );
}

function Label({ className, children }: { className: string; children: React.ReactNode }) {
  return (
    <span className={`absolute top-3 rounded bg-black/75 px-2 py-1 text-[11px] font-semibold text-white sm:top-4 sm:text-xs ${className}`}>
      {children}
    </span>
  );
}
