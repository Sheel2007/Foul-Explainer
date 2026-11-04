"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RESTART_LABEL } from "@/lib/format";
import type { Example } from "@/lib/types";
import { Quote, sourceLabel } from "./RulePanel";

const STEPS = ["Intro", "It watches every angle", "It finds the moment of contact", "It zooms in on the boots", "It finds the rule", "It makes the call"];
const SHORT = ["Intro", "Watch", "Contact", "Close-up", "Rule", "Call"];
const LAST = STEPS.length - 1;
// how long each step stays up (ms); step 1 lasts as long as the clip takes to reach the contact
const DURATION = [2500, 0, 4000, 4500, 5500, 0];
const HOLD_AFTER_CONTACT = 0.8; // seconds the contact frame stays before step 2
const ZOOM = 2;
const TICK_MS = 33;

/**
 * A short walk-through of one real clip that plays by itself, like a video with chapters: it starts
 * when it scrolls into view, pauses when it leaves, and the chapter bar lets you jump, pause or replay.
 * Step 1 plays the clip at normal speed up to the contact; later steps hold that frame and add the
 * contact box, a close-up zoom, the rule and the call.
 */
export default function StoryPlayer({ ex }: { ex: Example }) {
  const frameRef = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [step, setStep] = useState(0);
  const [progress, setProgress] = useState(0); // 0-1 through the current step
  const progressRef = useRef(0);
  const [time, setTime] = useState(0);
  const [inView, setInView] = useState(false);
  const [paused, setPaused] = useState(false);
  const contact = ex.moment.contact_seconds ?? 0;
  const [hidden, setHidden] = useState(false);
  const running = inView && !hidden && !paused && step < LAST;

  useEffect(() => {
    const onVis = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  // play only while at least half of it is on screen
  useEffect(() => {
    const el = frameRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting), { threshold: 0.5 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // move to a step, resetting its clock
  const enter = useCallback(
    (n: number) => {
      setStep(n);
      setProgress(0);
      progressRef.current = 0;
      setTime(n <= 1 ? 0 : contact);
    },
    [contact],
  );

  // entering a step: put the video where that step needs it
  useEffect(() => {
    const v = video.current;
    if (!v) return;
    if (step >= 1 && step !== 1) v.pause();
    if (step !== 1 || v.currentTime >= contact) v.currentTime = step <= 1 ? 0 : contact;
  }, [step, contact]);

  // the clock: step 1 follows the video, the others a timer; both stop while paused or off screen
  useEffect(() => {
    const v = video.current;
    if (!running || !v) {
      v?.pause();
      return;
    }
    let timer = 0;
    let last = performance.now();
    let held = 0;
    let elapsed = progressRef.current * DURATION[step]; // resume where a pause left off
    if (step === 1 && v.currentTime < contact) v.play().catch(() => (v.currentTime = contact));
    const tick = (now: number) => {
      const dt = now - last;
      last = now;
      if (step === 1) {
        if (v.currentTime >= contact) {
          if (!v.paused) {
            v.pause();
            v.currentTime = contact;
          }
          held += dt;
        }
        setTime(v.currentTime);
        const p = Math.min(1, (Math.min(v.currentTime, contact) + held / 1000) / (contact + HOLD_AFTER_CONTACT));
        setProgress(p);
        if (p >= 1) return enter(2);
      } else {
        elapsed += dt;
        const p = Math.min(1, elapsed / DURATION[step]);
        progressRef.current = p;
        setProgress(p);
        if (p >= 1) return enter(Math.min(LAST, step + 1));
      }
      timer = window.setTimeout(() => tick(performance.now()), TICK_MS);
    };
    timer = window.setTimeout(() => tick(performance.now()), TICK_MS);
    return () => window.clearTimeout(timer);
  }, [running, step, contact, enter]);

  function goTo(n: number) {
    setPaused(false);
    enter(n);
  }

  const m = ex.moment;
  const facts = ex.facts;
  const [ymin, xmin, ymax, xmax] = (m.contact_box ?? [400, 400, 600, 600]).map((v) => v / 10);
  const cx = (xmin + xmax) / 2;
  const cy = (ymin + ymax) / 2;
  const s = step === 3 ? ZOOM : 1;
  const at = (x: number, y: number, z: number) => [cx + (x - cx) * z, cy + (y - cy) * z] as const;
  const checks = facts
    ? ([
        ["Studs showing", facts.studs_showing],
        ["Straight leg", facts.leg_straight],
        ["Lunging", facts.lunge],
        ["Follow-through", facts.follow_through],
      ] as const)
    : [];
  const rules = ex.ai.citations
    .filter((c) => c.quote)
    .sort((a, b) => Number(b.kind === "guidance") - Number(a.kind === "guidance") || Number(b.section === "12.4") - Number(a.section === "12.4"))
    .slice(0, 2);
  const contactLine = [facts?.body_part_used, facts?.body_part_hit].filter(Boolean).join(" → ");

  // arrows from each note to the box, in a 1600x900 box over the frame (notes: right/left 3%, top 10%, 24% wide)
  const [bx1, by1] = at(xmax, ymin, 1);
  const [bx0, by0] = at(xmin, ymin, ZOOM);
  const arrows = [
    { on: step === 2, from: [72.5, 17], to: [bx1 + 0.5, by1 - 1] },
    { on: step === 3, from: [27.5, 17], to: [bx0 - 0.5, by0 - 1] },
  ];

  return (
    <section id="story" aria-label="See how it judges one tackle" className="on-dark scroll-mt-16 border-t border-white/10 bg-[#070a08] py-16 sm:py-20">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center gap-4 px-4 sm:px-6">
        <div ref={frameRef} className="relative aspect-video" style={{ width: "min(100%, calc((100svh - 57px - 12rem) * 16 / 9))" }}>
          {/* the frame, which zooms on the contact */}
          <div className="absolute inset-0 overflow-hidden rounded-2xl bg-black ring-1 ring-white/10">
            <div
              className="absolute inset-0 transition-transform duration-[900ms] ease-[cubic-bezier(0.65,0,0.35,1)]"
              style={{ transform: `scale(${s})`, transformOrigin: `${cx}% ${cy}%` }}
            >
              <video
                ref={video}
                src={ex.story?.video ?? ex.video}
                muted
                playsInline
                preload="auto"
                className="h-full w-full object-cover"
              />
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden>
                <defs>
                  <mask id="story-hole">
                    <rect width="100" height="100" fill="white" />
                    <rect x={xmin} y={ymin} width={xmax - xmin} height={ymax - ymin} rx="1" fill="black" />
                  </mask>
                </defs>
                <rect
                  width="100"
                  height="100"
                  fill="black"
                  mask="url(#story-hole)"
                  className="transition-opacity duration-500"
                  opacity={step >= 2 && step <= 3 ? 0.5 : 0}
                />
                <rect
                  x={xmin}
                  y={ymin}
                  width={xmax - xmin}
                  height={ymax - ymin}
                  rx="1"
                  fill="none"
                  stroke="#ef4444"
                  strokeWidth="3"
                  vectorEffect="non-scaling-stroke"
                  className="transition-opacity duration-500"
                  opacity={step >= 2 && step <= 4 ? 1 : 0}
                />
              </svg>
            </div>
            <div
              className="absolute inset-0 bg-black transition-opacity duration-700"
              style={{ opacity: step === 4 ? 0.6 : step === 5 ? 0.82 : 0 }}
            />
          </div>

          {/* arrows from the notes to the contact (wide screens) */}
          <svg viewBox="0 0 1600 900" className="pointer-events-none absolute inset-0 hidden h-full w-full lg:block" aria-hidden>
            <defs>
              <marker id="story-head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0 0 10 5 0 10z" fill="#fff" />
              </marker>
            </defs>
            {arrows.map((a, n) => {
              const [x0, y0, x1, y1] = [a.from[0] * 16, a.from[1] * 9, a.to[0] * 16, a.to[1] * 9];
              return (
                <path
                  key={n}
                  d={`M${x0} ${y0} Q ${x1} ${y0} ${x1} ${y1}`}
                  fill="none"
                  stroke="#fff"
                  strokeWidth="3"
                  strokeLinecap="round"
                  pathLength={1}
                  strokeDasharray="1"
                  strokeDashoffset={a.on ? 0 : 1}
                  markerEnd={a.on ? "url(#story-head)" : undefined}
                  style={{ transition: a.on ? "stroke-dashoffset 0.6s ease 0.9s" : "stroke-dashoffset 0.2s" }}
                />
              );
            })}
          </svg>

          {/* step label */}
          <div
            className="absolute left-3 top-3 rounded-full bg-black/75 px-3 py-1.5 text-xs font-medium text-white ring-1 ring-white/15 transition-opacity duration-300 sm:left-4 sm:top-4 sm:text-sm"
            style={{ opacity: step ? 1 : 0 }}
          >
            <span className="text-green-300">{Math.max(step, 1)} / {LAST}</span> · {STEPS[Math.max(step, 1)]}
          </div>

          {/* 0: intro */}
          <Fade on={step === 0} className="absolute inset-0 grid place-items-center rounded-2xl bg-black/70 p-6 text-center">
            <div>
              <h2 className="text-xl font-semibold tracking-tight sm:text-3xl lg:text-5xl">
                Everyone sees the replay.
                <br />
                <span className="text-green-300">Almost nobody sees the rule.</span>
              </h2>
              <p className="mt-4 hidden text-sm text-muted sm:block sm:text-base">Watch it judge one real tackle</p>
            </div>
          </Fade>

          {/* 1: the angles it found, lit as the clip reaches them */}
          <Fade on={step === 1} className="absolute bottom-3 left-3 right-3 flex flex-wrap gap-2 sm:bottom-4 sm:left-4">
            {m.views.map((v) => {
              const seen = time >= Math.min(v.seconds, contact) - 0.3;
              return (
                <span
                  key={v.seconds}
                  className={`rounded-lg px-2.5 py-1.5 text-xs ring-1 transition-colors duration-300 ${seen ? "bg-black/80 text-white ring-white/30" : "bg-black/40 text-white/40 ring-white/10"}`}
                >
                  {v.kind === "replay" ? (v.slow_motion ? "Slow-mo replay" : "Replay") : "Live"} · {v.seconds.toFixed(1)}s
                  {v.chosen && seen && <b className="ml-1.5 text-green-300">clearest</b>}
                </span>
              );
            })}
          </Fade>

          {/* 2 and 3: notes beside the contact (wide screens) */}
          <Fade on={step === 2} delay={500} className="absolute right-[3%] top-[10%] hidden w-[24%] rounded-2xl bg-black/85 p-4 text-sm ring-1 ring-white/15 lg:block">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-red-400">Contact · {contact.toFixed(1)}s</p>
            <p className="mt-1 font-semibold first-letter:uppercase">{contactLine}</p>
            <p className="mt-1 text-xs text-white/60 first-letter:uppercase">{facts?.challenge_type}</p>
          </Fade>
          <Fade on={step === 3} delay={600} className="absolute left-[3%] top-[10%] hidden w-[24%] rounded-2xl bg-black/85 p-4 text-sm ring-1 ring-white/15 lg:block">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-green-300">Close-up</p>
            <Checks checks={checks} on={step === 3} />
          </Fade>

          {/* 4: the rule */}
          <div className="pointer-events-none absolute inset-0 hidden flex-col justify-center gap-3 p-[5%] sm:flex">
            {rules.map((r, n) => (
              <div
                key={r.quote}
                className="max-w-[78%] rounded-2xl bg-black/75 p-4 ring-1 ring-white/15 transition duration-700"
                style={{
                  marginLeft: n ? "auto" : undefined,
                  opacity: step === 4 ? 1 : 0,
                  transform: step === 4 ? "none" : `translateX(${n ? 48 : -48}px)`,
                  transitionDelay: step === 4 ? `${300 + n * 350}ms` : "0ms",
                }}
              >
                <p className="text-base italic leading-relaxed sm:text-lg">
                  “<Quote text={r.quote!} highlight={r.highlight} />”
                </p>
                <p className="mt-2 text-xs text-white/60">{sourceLabel(r)}</p>
              </div>
            ))}
          </div>

          {/* 5: the call */}
          <Fade on={step === 5} delay={200} className="absolute inset-0 grid place-items-center p-4 text-center">
            <div>
              {ex.ai.card !== "none" && (
                <span
                  aria-hidden
                  className={`mx-auto mb-4 block h-20 w-14 rounded-lg shadow-2xl transition-transform delay-200 duration-700 sm:h-28 sm:w-20 ${ex.ai.card === "red" ? "bg-red-600" : "bg-yellow-400"}`}
                  style={{ transform: step === 5 ? "rotate(8deg) translateY(0)" : "rotate(-30deg) translateY(30px)" }}
                />
              )}
              <p className="text-4xl font-bold tracking-tight sm:text-6xl">
                {ex.ai.card === "none" ? "Foul" : `${ex.ai.card === "red" ? "Red" : "Yellow"} card`}
              </p>
              <p className="mt-2 text-base text-white/80 first-letter:uppercase sm:text-lg">
                {ex.ai.offence_type} · {RESTART_LABEL[ex.ai.restart]}
              </p>
              <p className="mt-3 text-sm text-green-300">
                {ex.ai.confidence} confidence · {Math.round(ex.ai.confidence_detail.score * 100)}%
                {m.audit.second_opinion === "agree" && " · a second, independent run agreed"}
              </p>
              {ex.label?.card && (
                <p className="mt-1 text-sm text-white/60">
                  Answer key: {ex.label.card === "none" ? "no card" : `${ex.label.card} card`} {ex.label.card === ex.ai.card ? "✓" : "✗"}
                </p>
              )}
              <button
                type="button"
                onClick={() => goTo(1)}
                className="pointer-events-auto mt-5 rounded-lg px-4 py-2 text-sm font-medium ring-1 ring-white/25 hover:bg-white/10"
              >
                ↺ Watch again
              </button>
            </div>
          </Fade>
        </div>

        {/* chapter bar: progress through each step; click a chapter to jump to it */}
        <div className="flex w-full items-center gap-3" style={{ maxWidth: "min(100%, calc((100svh - 57px - 12rem) * 16 / 9))" }}>
          <button
            type="button"
            onClick={() => (step === LAST ? goTo(1) : setPaused((x) => !x))}
            aria-label={step === LAST ? "Watch again" : paused ? "Play" : "Pause"}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white/10 text-sm text-white hover:bg-white/20"
          >
            {step === LAST ? "↺" : paused ? "▶" : "❚❚"}
          </button>
          <nav aria-label="Chapters" className="grid flex-1 grid-cols-5 gap-1.5">
            {SHORT.slice(1).map((label, k) => {
              const n = k + 1;
              const fill = n < step ? 1 : n === step ? (step === LAST ? 1 : progress) : 0;
              return (
                <button key={label} type="button" onClick={() => goTo(n)} aria-current={n === step ? "step" : undefined} className="group text-left">
                  <span className="block h-1 overflow-hidden rounded-full bg-white/20">
                    <span className="block h-full rounded-full bg-green-400" style={{ width: `${fill * 100}%` }} />
                  </span>
                  <span className={`mt-1.5 block truncate text-[11px] sm:text-xs ${n === step ? "text-white" : "text-white/50 group-hover:text-white/80"}`}>
                    {label}
                  </span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* phones: the notes go under the frame instead of over it */}
        <div className="min-h-[6.5rem] w-full max-w-md text-sm empty:hidden lg:hidden">
          {step === 2 && (
            <p>
              <b className="text-red-400">Contact at {contact.toFixed(1)}s:</b> {contactLine}
            </p>
          )}
          {step === 3 && <Checks checks={checks} on />}
          {step === 4 &&
            rules.slice(0, 1).map((r) => (
              <p key={r.quote} className="italic sm:hidden">
                “<Quote text={r.quote!} highlight={r.highlight} />”
                <span className="mt-1 block text-xs not-italic text-white/60">{sourceLabel(r)}</span>
              </p>
            ))}
        </div>
      </div>
    </section>
  );
}

/** Fades its children in when `on` (after `delay` ms) and straight out when not. */
function Fade({ on, delay = 0, className, children }: { on: boolean; delay?: number; className: string; children: React.ReactNode }) {
  return (
    <div
      className={`${className} transition duration-500`}
      style={{
        opacity: on ? 1 : 0,
        transform: on ? "none" : "translateY(8px)",
        transitionDelay: on ? `${delay}ms` : "0ms",
        pointerEvents: on ? undefined : "none",
      }}
    >
      {children}
    </div>
  );
}

function Checks({ checks, on }: { checks: readonly (readonly [string, boolean | null])[]; on: boolean }) {
  return (
    <ul className="mt-1.5 space-y-1">
      {checks.map(([name, v], n) => (
        <li
          key={name}
          className="flex items-center gap-2 transition-opacity duration-300"
          style={{ opacity: on ? 1 : 0.15, transitionDelay: on ? `${900 + n * 250}ms` : "0ms" }}
        >
          <span className={v ? "text-red-400" : "text-white/50"}>{v ? "✓" : v === false ? "✗" : "?"}</span>
          <span>{name}</span>
        </li>
      ))}
    </ul>
  );
}
