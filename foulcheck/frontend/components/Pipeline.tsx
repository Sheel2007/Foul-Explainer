"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import { RESTART_LABEL } from "@/lib/format";
import type { Example } from "@/lib/types";
import { Quote } from "./RulePanel";

type Stop = { title: string; caption: string; visual: React.ReactNode };

/** A labelled arrow between two stops: right on wide screens, down on phones. */
function Arrow({
  label,
  on,
  delay,
}: {
  label: string;
  on: boolean;
  delay: number;
}) {
  const draw = { transition: `stroke-dashoffset 0.5s ease ${delay}ms` };
  const head = {
    opacity: on ? 1 : 0,
    transition: `opacity 0.2s ease ${delay + 450}ms`,
  };
  return (
    <div
      className="flex items-center justify-center gap-2 py-3 md:flex-col md:gap-1 md:px-1 md:pt-0 md:pb-14"
      aria-hidden
    >
      {/* down on phones */}
      <svg viewBox="0 0 20 44" className="h-11 w-5 text-pitch md:hidden">
        <path
          d="M10 2 C 4 14, 16 26, 10 38"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray="1"
          strokeDashoffset={on ? 0 : 1}
          style={draw}
        />
        <path
          d="M4 32 10 40 16 32"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={head}
        />
      </svg>
      <span
        className="whitespace-nowrap font-mono text-[11px] text-muted transition-opacity duration-500 md:order-first"
        style={{ opacity: on ? 1 : 0, transitionDelay: `${delay + 300}ms` }}
      >
        {label}
      </span>
      {/* right on wide screens */}
      <svg viewBox="0 0 64 20" className="hidden h-5 w-16 text-pitch md:block">
        <path
          d="M2 12 C 18 4, 40 4, 56 10"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray="1"
          strokeDashoffset={on ? 0 : 1}
          style={draw}
        />
        <path
          d="M49 4 58 10.5 48 15"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={head}
        />
      </svg>
    </div>
  );
}

function StopView({
  n,
  stop,
  on,
  delay,
}: {
  n: number;
  stop: Stop;
  on: boolean;
  delay: number;
}) {
  return (
    <figure
      className="min-w-0 transition duration-700"
      style={{
        opacity: on ? 1 : 0,
        transform: on ? "none" : "translateY(18px)",
        transitionDelay: `${delay}ms`,
      }}
    >
      <div className="relative aspect-[4/3] overflow-hidden rounded-xl bg-surface">
        {stop.visual}
      </div>
      <figcaption className="mt-3">
        <span className="font-semibold">
          <span className="mr-1.5 text-pitch">{n}</span>
          {stop.title}
        </span>
        <span className="mt-0.5 block text-sm leading-snug text-muted">
          {stop.caption}
        </span>
      </figcaption>
    </figure>
  );
}

function Row({
  stops,
  labels,
  first,
  on,
  base,
}: {
  stops: Stop[];
  labels: string[];
  first: number;
  on: boolean;
  base: number;
}) {
  return (
    <div className="grid md:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr]">
      {stops.map((stop, i) => (
        <Fragment key={stop.title}>
          {i > 0 && (
            <Arrow label={labels[i - 1]} on={on} delay={base + i * 260 - 150} />
          )}
          <StopView n={first + i} stop={stop} on={on} delay={base + i * 260} />
        </Fragment>
      ))}
    </div>
  );
}

/** Small tag laid over a picture. */
function Tag({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`rounded-md bg-black/75 px-1.5 py-0.5 text-[11px] font-medium text-white ${className}`}
    >
      {children}
    </span>
  );
}

/** Semicircle gauge with the Low / Medium / High bands and a needle at `score`. */
function Gauge({ score, level }: { score: number; level: string }) {
  const arc = (a: number, b: number) => {
    const pt = (t: number) => [
      60 - 46 * Math.cos(Math.PI * t),
      62 - 46 * Math.sin(Math.PI * t),
    ];
    const [x0, y0] = pt(a);
    const [x1, y1] = pt(b);
    return `M${x0} ${y0} A46 46 0 0 1 ${x1} ${y1}`;
  };
  const angle = Math.PI * score;
  return (
    <div className="grid h-full place-items-center">
      <svg viewBox="0 0 120 80" className="w-[78%]">
        <path
          d={arc(0, 0.5)}
          stroke="#ef4444"
          strokeWidth="10"
          fill="none"
          opacity="0.8"
        />
        <path
          d={arc(0.5, 0.75)}
          stroke="#f59e0b"
          strokeWidth="10"
          fill="none"
          opacity="0.8"
        />
        <path
          d={arc(0.75, 1)}
          stroke="#22a355"
          strokeWidth="10"
          fill="none"
          opacity="0.9"
        />
        <line
          x1="60"
          y1="62"
          x2={60 - 38 * Math.cos(angle)}
          y2={62 - 38 * Math.sin(angle)}
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx="60" cy="62" r="4" fill="currentColor" />
        <text
          x="60"
          y="78"
          textAnchor="middle"
          fontSize="10"
          fontWeight="600"
          fill="currentColor"
        >
          {Math.round(score * 100)}% · {level}
        </text>
      </svg>
    </div>
  );
}

/** The pipeline as a storyboard: real frames from the story clip and small illustrations, joined by labelled arrows. */
export default function Pipeline({ ex }: { ex: Example }) {
  const ref = useRef<HTMLDivElement>(null);
  const [on, setOn] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => e.isIntersecting && setOn(true),
      { threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const st = ex.story!;
  const m = ex.moment;
  const f = ex.facts;
  const chosen = m.views.find((v) => v.chosen);
  const [ymin, xmin, ymax, xmax] = (m.contact_box ?? [400, 400, 600, 600]).map(
    (v) => v / 10,
  );
  const quote =
    ex.ai.citations.find((c) => c.kind === "guidance" && c.quote) ??
    ex.ai.citations.find((c) => c.quote);
  const verified = ex.ai.citations.filter((c) => c.quote).length;
  const cardName =
    ex.ai.card === "none"
      ? "No card"
      : `${ex.ai.card === "red" ? "Red" : "Yellow"} card`;
  const nearest = (t: number) =>
    st.strip.reduce((a, b) =>
      Math.abs(b.seconds - t) < Math.abs(a.seconds - t) ? b : a,
    ).src;

  const watch: Stop[] = [
    {
      title: "Your clip",
      caption: "One incident. Broadcast clips mix live action and replays.",
      visual: (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={ex.poster} alt="" className="h-full w-full object-cover" />
          <span className="absolute inset-0 grid place-items-center">
            <span className="grid h-12 w-12 place-items-center rounded-full bg-black/60 text-xl text-white">
              ▶
            </span>
          </span>
          <Tag className="absolute bottom-2 right-2">
            {st.duration.toFixed(1)} s
          </Tag>
        </>
      ),
    },
    {
      title: "Find the moment",
      caption:
        "Skims the whole clip, lists every angle and picks the clearest.",
      visual: (
        <div className="flex h-full flex-col justify-center gap-2 p-3">
          <div className="grid grid-cols-4 gap-1">
            {st.strip.map((fr) => {
              const hit = m.views.some((v) => nearest(v.seconds) === fr.src);
              const best = chosen && nearest(chosen.seconds) === fr.src;
              return (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={fr.src}
                  src={fr.src}
                  alt=""
                  className={`aspect-video w-full rounded-sm object-cover ${best ? "ring-2 ring-pitch" : hit ? "ring-1 ring-white/70" : "opacity-50"}`}
                />
              );
            })}
          </div>
          {/* timeline with each angle's contact */}
          <div className="relative mx-1 mt-3 h-6">
            <div className="absolute inset-x-0 top-1.5 h-0.5 rounded bg-line" />
            {m.views.map((v) => (
              <span
                key={v.seconds}
                className="absolute -translate-x-1/2 text-center"
                style={{ left: `${(v.seconds / st.duration) * 100}%` }}
              >
                <span
                  className={`mx-auto block h-3.5 w-3.5 rounded-full border-2 border-surface ${v.chosen ? "bg-pitch" : "bg-muted"}`}
                />
                <span
                  className={`block whitespace-nowrap text-[10px] ${v.chosen ? "font-semibold text-pitch" : "text-muted"}`}
                >
                  {v.kind} {v.seconds.toFixed(1)}s
                </span>
              </span>
            ))}
          </div>
        </div>
      ),
    },
    {
      title: "Record the facts",
      caption:
        "Re-watches that angle closely and writes down only what it sees. No rulings allowed.",
      visual: (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={st.contact} alt="" className="h-full w-full object-cover" />
          <span
            className="absolute rounded-sm border-2 border-red-500"
            style={{
              left: `${xmin}%`,
              top: `${ymin}%`,
              width: `${xmax - xmin}%`,
              height: `${ymax - ymin}%`,
            }}
          />
          <div className="absolute left-2 top-2 flex flex-col items-start gap-1">
            <Tag>contact {m.contact_seconds?.toFixed(1)}s</Tag>
            <Tag>{f?.challenge_type}</Tag>
          </div>
        </>
      ),
    },
    {
      title: "Zoom in on the boots",
      caption:
        "Crops and enlarges the contact, because broadcast video is too small to see studs.",
      visual: (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={st.closeup ?? st.contact}
            alt=""
            className="h-full w-full object-cover"
          />
          <div className="absolute inset-x-2 bottom-2 flex flex-wrap gap-1">
            <Tag>studs {f?.studs_showing ? "✓" : "✗"}</Tag>
            <Tag>straight leg {f?.leg_straight ? "✓" : "✗"}</Tag>
            <Tag>
              {f?.body_part_used} → {f?.body_part_hit}
            </Tag>
          </div>
        </>
      ),
    },
  ];

  const decide: Stop[] = [
    {
      title: "Look up the rule",
      caption:
        "Searches the Laws of the Game and Premier League / UEFA referee guidance for the passages that fit.",
      visual: (
        <div className="relative h-full">
          <div className="absolute left-[12%] top-[12%] h-[72%] w-[58%] -rotate-6 rounded-md bg-white p-2 shadow-md">
            <p className="font-serif text-[9px] font-bold text-neutral-800">
              Laws of the Game 2026/27
            </p>
            {[90, 75, 85, 60, 80, 70].map((w, i) => (
              <span
                key={i}
                className="mt-1.5 block h-1 rounded bg-neutral-300"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
          <div className="absolute left-[30%] top-[20%] h-[70%] w-[60%] rotate-3 rounded-md bg-white p-2.5 shadow-lg">
            <p className="font-serif text-[9px] font-bold text-neutral-800">
              Referee guidance
            </p>
            <span className="mt-1.5 block h-1 w-[70%] rounded bg-neutral-300" />
            <p className="mt-1.5 font-serif text-[9px] leading-snug text-neutral-700">
              {quote?.quote ? (
                <Quote text={quote.quote} highlight={quote.highlight} />
              ) : (
                "…"
              )}
            </p>
            <span className="mt-1.5 block h-1 w-[55%] rounded bg-neutral-300" />
          </div>
        </div>
      ),
    },
    {
      title: "Decide, twice",
      caption:
        "A language model reads the facts and those passages, never the video. A second, independent run checks it.",
      visual: (
        <div className="relative grid h-full grid-cols-2 place-items-center gap-2 px-4">
          {["Run A", "Run B"].map((run, i) => (
            <div
              key={run}
              className={`w-full rounded-lg bg-background p-2.5 shadow-sm ring-1 ring-line ${i ? "rotate-2" : "-rotate-2"}`}
            >
              <p className="text-[10px] text-muted">{run}</p>
              <span
                className={`mt-1 block h-7 w-5 rounded ${ex.ai.card === "red" ? "bg-red-600" : ex.ai.card === "yellow" ? "bg-yellow-400" : "bg-line"}`}
              />
              <p className="mt-1 text-xs font-semibold">{cardName}</p>
            </div>
          ))}
          {m.audit.second_opinion === "agree" && (
            <span className="absolute bottom-[12%] left-1/2 -translate-x-1/2 -rotate-6 rounded-md border-2 border-pitch px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-pitch">
              Agree
            </span>
          )}
        </div>
      ),
    },
    {
      title: "Check every quote",
      caption:
        "Each quoted rule must match the source word for word, or it gets rerun and then dropped.",
      visual: (
        <div className="flex h-full flex-col justify-center gap-1.5 p-2.5 text-[11px] leading-snug">
          <div className="rounded-md bg-background px-2 py-1.5 ring-1 ring-line">
            <span className="text-[10px] text-muted">The AI quoted</span>
            <p className="line-clamp-2 italic">
              “{quote?.highlight ?? quote?.quote}”
            </p>
          </div>
          <div className="rounded-md bg-background px-2 py-1.5 ring-1 ring-line">
            <span className="text-[10px] text-muted">The source says</span>
            <p className="line-clamp-2 italic">
              “…{quote?.highlight ?? quote?.quote}”
            </p>
          </div>
          <p className="text-center font-semibold text-pitch">
            ✓ {verified} of {verified} quotes match
          </p>
        </div>
      ),
    },
    {
      title: "Score confidence",
      caption:
        "Starts from the model's own rating and takes points off for anything unclear or disputed.",
      visual: (
        <Gauge score={ex.ai.confidence_detail.score} level={ex.ai.confidence} />
      ),
    },
  ];

  return (
    <section id="how" className="scroll-mt-16 py-24">
      <div ref={ref} className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        <p className="text-sm font-medium text-pitch">Under the hood</p>
        <h2 className="mt-1 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
          From a clip to a call, step by step.
        </h2>
        <p className="mt-3 max-w-2xl text-muted">
          Everything below is what the tool actually produced for the tackle
          above. The model that watches never makes the call, and the one that
          makes the call never sees the video.
        </p>

        <p className="mt-12 font-mono text-xs uppercase tracking-wider text-muted">
          Watching · video model
        </p>
        <div className="mt-4">
          <Row
            stops={watch}
            labels={["skim 2 fps", "12 fps at contact", "crop + enlarge"]}
            first={1}
            on={on}
            base={0}
          />
        </div>

        {/* hand-off: the video stops here */}
        <div className="relative my-6 md:my-2 md:h-24" aria-hidden>
          <svg
            viewBox="0 0 1000 96"
            preserveAspectRatio="none"
            className="absolute inset-0 hidden h-full w-full text-pitch md:block"
          >
            <path
              d="M880 4 C 880 60, 820 48, 500 48 S 120 40, 120 92"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeDasharray="6 6"
              vectorEffect="non-scaling-stroke"
              style={{
                opacity: on ? 1 : 0,
                transition: "opacity 0.6s ease 1100ms",
              }}
            />
          </svg>
          <p
            className="relative mx-auto w-fit rounded-full bg-background px-4 py-1.5 text-center text-sm ring-1 ring-line transition-opacity duration-500 md:top-1/2 md:-translate-y-1/2"
            style={{ opacity: on ? 1 : 0, transitionDelay: "1200ms" }}
          >
            <b>Only the facts go on.</b>{" "}
            <span className="text-muted">The video stops here.</span>
          </p>
        </div>

        <p className="font-mono text-xs uppercase tracking-wider text-muted">
          Deciding · language model
        </p>
        <div className="mt-4">
          <Row
            stops={decide}
            labels={["10 best passages", "2 drafts", "verified"]}
            first={5}
            on={on}
            base={1300}
          />
        </div>

        <div
          className="on-dark mt-10 flex flex-wrap items-center justify-center gap-4 rounded-2xl bg-[#070a08] px-6 py-6 text-center transition-opacity duration-700"
          style={{ opacity: on ? 1 : 0, transitionDelay: "2400ms" }}
        >
          {ex.ai.card !== "none" && (
            <span
              aria-hidden
              className={`h-12 w-9 rotate-6 rounded-md shadow-lg ${ex.ai.card === "red" ? "bg-red-600" : "bg-yellow-400"}`}
            />
          )}
          <div className="text-left">
            <p className="text-xl font-semibold">
              {cardName} ·{" "}
              <span className="first-letter:uppercase">
                {ex.ai.offence_type}
              </span>
            </p>
            <p className="text-sm text-muted">
              {RESTART_LABEL[ex.ai.restart]}, with the explanation, the
              highlighted rule and why it&apos;s{" "}
              {ex.ai.confidence.toLowerCase()} confidence
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
