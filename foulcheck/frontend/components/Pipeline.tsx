import { Fragment } from "react";
import { explainAdjustment } from "@/lib/confidence";
import { RESTART_LABEL, VERDICT_LABEL } from "@/lib/format";
import type { Example } from "@/lib/types";
import { Quote } from "./RulePanel";

type Stop = { title: string; caption: string; visual: React.ReactNode };

/** The phone version of the timeline: the same steps as small cards, two to a row, joined by arrows. */
type PhoneStop = { title: string; visual: React.ReactNode };

function PhoneArrowRight() {
  return (
    <svg viewBox="0 0 14 10" className="mt-[calc((50vw-1.25rem)*0.25-0.3rem)] h-2.5 w-3.5 self-start text-pitch" aria-hidden>
      <path d="M1 5h10M8 1.5 12 5 8 8.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** From the end of one row back to the start of the next, like the desktop's hand-off curve. */
function PhoneTurn({ dashed, label }: { dashed?: boolean; label?: React.ReactNode }) {
  return (
    <div className={`relative ${label ? "my-0.5 h-7" : "h-5"}`} aria-hidden={!label}>
      <svg viewBox="0 0 100 20" preserveAspectRatio="none" className="absolute inset-0 h-full w-full text-pitch">
        <path
          d="M76 1 C 76 12, 70 10, 50 10 S 24 8, 24 19"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeDasharray={dashed ? "3 3" : undefined}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      {label && (
        <p className="relative top-1/2 mx-auto w-fit -translate-y-1/2 rounded-full bg-background px-2.5 py-0.5 text-[10.5px] ring-1 ring-line">
          {label}
        </p>
      )}
    </div>
  );
}

function PhoneRow({ stops, first }: { stops: PhoneStop[]; first: number }) {
  const card = (stop: PhoneStop, n: number) => (
    <figure className="min-w-0">
      <div className="relative aspect-[2/1] overflow-hidden rounded-lg bg-surface ring-1 ring-line">{stop.visual}</div>
      <figcaption className="mt-0.5 truncate text-[12px] font-semibold leading-tight">
        <span className="mr-1 text-pitch">{n}</span>
        {stop.title}
      </figcaption>
    </figure>
  );
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] gap-x-1">
      {card(stops[0], first)}
      <PhoneArrowRight />
      {card(stops[1], first + 1)}
    </div>
  );
}

/** A labelled arrow between two stops. */
function Arrow({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 px-1 pb-14" aria-hidden>
      <span className="whitespace-nowrap font-mono text-[11px] text-muted">{label}</span>
      <svg viewBox="0 0 64 20" className="h-5 w-16 text-pitch">
        <path d="M2 12 C 18 4, 40 4, 56 10" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M49 4 58 10.5 48 15" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

function StopView({ n, stop }: { n: number; stop: Stop }) {
  return (
    <figure className="min-w-0">
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
}: {
  stops: Stop[];
  labels: string[];
  first: number;
}) {
  return (
    <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr]">
      {stops.map((stop, i) => (
        <Fragment key={stop.title}>
          {i > 0 && <Arrow label={labels[i - 1]} />}
          <StopView n={first + i} stop={stop} />
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

/** The pipeline as a storyboard: real frames from the story clip and small illustrations, joined by labelled arrows. */
export default function Pipeline({ ex }: { ex: Example }) {
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

  const agreed = m.audit.second_opinion === "agree";
  const runs = [
    ["Call", VERDICT_LABEL[ex.ai.verdict]],
    ["Restart", RESTART_LABEL[ex.ai.restart].replace("free kick", "FK")],
    ["Card", cardName],
  ];
  // the confidence working, one line per kind of check
  const conf = ex.ai.confidence_detail;
  const points = (match: RegExp) =>
    conf.adjustments.filter((a) => match.test(a)).reduce((sum, a) => sum + explainAdjustment(a).points, 0);
  const hinge = points(/red card depends/);
  const other = points(/^(?!.*(unsure|clearly visible|disagreed|red card depends|capped))/);
  const working: (readonly [string, number])[] = [
    ["Key facts unclear", points(/unsure/)],
    ["Contact hard to see", points(/clearly visible/)],
    ["Second run disagreed", points(/disagreed/)],
    ...(hinge ? [["Card rests on one reading", hinge] as const] : []),
    ...(other ? [["Other checks", other] as const] : []),
  ];

  const phoneTag = (text: React.ReactNode) => (
    <span className="absolute bottom-1 right-1 rounded bg-black/75 px-1 text-[9.5px] font-medium text-white">{text}</span>
  );
  const phoneImage = (src: string) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt="" className="h-full w-full object-cover" />
  );
  const strip = [0, 2, 4, 6].map((n) => st.strip[n]).filter(Boolean);
  const best = chosen ? nearest(chosen.seconds) : null;
  const box = { left: `${xmin}%`, top: `${ymin}%`, width: `${xmax - xmin}%`, height: `${ymax - ymin}%` };
  const phoneWatch: PhoneStop[] = [
    { title: "Your clip", visual: <>{phoneImage(ex.poster)}{phoneTag(`${st.duration.toFixed(1)} s`)}</> },
    {
      title: "Find the moment",
      visual: (
        <div className="grid h-full grid-cols-2 gap-0.5 p-1">
          {strip.map((fr) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={fr.src} src={fr.src} alt="" className={`h-full w-full rounded-[2px] object-cover ${fr.src === best ? "ring-2 ring-pitch" : "opacity-50"}`} />
          ))}
        </div>
      ),
    },
    {
      title: "Record the facts",
      visual: (
        <>
          {phoneImage(st.contact)}
          <span className="absolute border-2 border-red-500" style={box} />
          {phoneTag(`contact ${m.contact_seconds?.toFixed(1)}s`)}
        </>
      ),
    },
    {
      title: "Zoom on the boots",
      visual: <>{phoneImage(st.closeup ?? st.contact)}{phoneTag(`studs ${f?.studs_showing ? "✓" : "✗"}`)}</>,
    },
  ];
  const phoneDecide: PhoneStop[] = [
    {
      title: "Look up the rule",
      visual: (
        <div className="absolute inset-1.5 rotate-[-1.5deg] rounded bg-white px-1.5 py-1 font-serif text-[9.5px] leading-tight text-neutral-800 shadow">
          <p className="font-sans text-[8px] font-semibold uppercase tracking-wide text-neutral-500">{quote?.kind === "guidance" ? "Referee guidance" : "Laws of the Game"}</p>
          <p className="mt-0.5 line-clamp-3">
            <mark className="bg-yellow-300 px-0.5 text-black">{quote?.highlight ?? quote?.quote}</mark>
          </p>
        </div>
      ),
    },
    {
      title: "Decide, twice",
      visual: (
        <div className="flex h-full flex-col justify-center gap-0.5 px-2 font-mono text-[10px] leading-tight">
          <p className="flex justify-between"><span className="text-muted">Run 1</span>{cardName}</p>
          <p className="flex justify-between"><span className="text-muted">Run 2</span>{agreed ? cardName : "differs"}</p>
          <p className={agreed ? "text-pitch" : "text-red-500"}>{agreed ? "✓ agree" : "✗ disagree"}</p>
        </div>
      ),
    },
    {
      title: "Check every quote",
      visual: (
        <div className="flex h-full flex-col justify-center px-2 text-[10px] leading-tight">
          <p className="line-clamp-2 italic">“{quote?.highlight ?? quote?.quote}”</p>
          <p className="mt-1 font-semibold text-pitch">✓ {verified} of {verified} match</p>
        </div>
      ),
    },
    {
      title: "Score confidence",
      visual: (
        <div className="flex h-full flex-col justify-center px-2 font-mono leading-tight">
          <p className="text-[10px] text-muted">
            {Math.round(conf.model_score * 100)}%{working.filter(([, n]) => n).map(([, n]) => ` −${n}`).join("")}
          </p>
          <p className="text-lg font-semibold">{Math.round(conf.score * 100)}%</p>
          <p className="text-[10px] text-muted">{ex.ai.confidence} confidence</p>
        </div>
      ),
    },
  ];

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
        <div className="flex h-full flex-col justify-center p-3 font-mono text-[10px] leading-tight sm:text-[11px]">
          <table className="w-full table-fixed text-left">
            <thead className="text-muted">
              <tr className="border-b border-line">
                <th className="w-[30%] py-1.5 font-normal" />
                <th className="py-1.5 pr-1 font-normal">Run 1</th>
                <th className="py-1.5 pr-1 font-normal">Run 2</th>
                <th className="w-4 py-1.5 font-normal" />
              </tr>
            </thead>
            <tbody>
              {runs.map(([name, value]) => (
                <tr key={name} className="border-b border-line">
                  <td className="py-1.5 pr-1 align-top text-muted">{name}</td>
                  <td className="py-1.5 pr-1 align-top">{value}</td>
                  <td className="py-1.5 pr-1 align-top">{agreed ? value : "See note"}</td>
                  <td className="py-1.5 align-top text-pitch">{agreed && "✓"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!agreed && <p className="mt-2 font-sans text-muted">The second run could not confirm this call.</p>}
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
        <dl className="flex h-full flex-col justify-center p-3 font-mono text-[10px] sm:text-[11px]">
          <div className="flex justify-between gap-2 border-b border-line py-1.5">
            <dt className="text-muted">Model&apos;s own rating</dt>
            <dd>{Math.round(conf.model_score * 100)}%</dd>
          </div>
          {working.map(([name, points]) => (
            <div key={name} className="flex justify-between gap-2 border-b border-line py-1.5">
              <dt className="text-muted">{name}</dt>
              <dd className={points ? "text-red-500" : "text-muted"}>−{points}</dd>
            </div>
          ))}
          <div className="flex justify-between gap-2 pt-1.5 text-xs font-semibold sm:text-sm">
            <dt>{ex.ai.confidence}</dt>
            <dd>{Math.round(conf.score * 100)}%</dd>
          </div>
        </dl>
      ),
    },
  ];

  return (
    <section id="how" className="scroll-mt-14 py-3 md:scroll-mt-16 md:py-24">
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        <p className="hidden text-sm font-medium text-pitch md:block">Under the hood</p>
        <h2 className="max-w-3xl text-xl font-semibold tracking-tight md:mt-1 md:text-4xl">
          From a clip to a call<span className="hidden md:inline">, step by step</span>.
        </h2>
        <p className="mt-0.5 max-w-2xl text-xs leading-snug text-muted md:mt-3 md:text-base md:leading-normal">
          <span className="hidden md:inline">Everything below is what the tool actually produced for the tackle above. </span>
          <span className="md:hidden">The model that watches never makes the call.</span>
          <span className="hidden md:inline">
            The model that watches never makes the call, and the one that makes the call never sees the video.
          </span>
        </p>

        {/* phones and small tablets: the same timeline, two steps to a row, all on one screen */}
        <div className="mt-2 md:hidden">
          <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted">Watching · video model</p>
          <PhoneRow stops={phoneWatch.slice(0, 2)} first={1} />
          <PhoneTurn />
          <PhoneRow stops={phoneWatch.slice(2)} first={3} />
          <PhoneTurn
            dashed
            label={
              <>
                <b>Only the facts go on.</b> <span className="text-muted">The video stops here.</span>
              </>
            }
          />
          <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted">Deciding · language model</p>
          <PhoneRow stops={phoneDecide.slice(0, 2)} first={5} />
          <PhoneTurn />
          <PhoneRow stops={phoneDecide.slice(2)} first={7} />
        </div>

        <div className="hidden md:block">
          <p className="mt-12 font-mono text-xs uppercase tracking-wider text-muted">Watching · video model</p>
          <div className="mt-4">
            <Row stops={watch} labels={["skim 2 fps", "12 fps at contact", "crop + enlarge"]} first={1} />
          </div>

          {/* hand-off: the video stops here */}
          <div className="relative my-2 h-24" aria-hidden>
            <svg viewBox="0 0 1000 96" preserveAspectRatio="none" className="absolute inset-0 h-full w-full text-pitch">
              <path
                d="M880 4 C 880 60, 820 48, 500 48 S 120 40, 120 92"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeDasharray="6 6"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
            <p className="relative top-1/2 mx-auto w-fit -translate-y-1/2 rounded-full bg-background px-4 py-1.5 text-center text-sm ring-1 ring-line">
              <b>Only the facts go on.</b> <span className="text-muted">The video stops here.</span>
            </p>
          </div>

          <p className="font-mono text-xs uppercase tracking-wider text-muted">Deciding · language model</p>
          <div className="mt-4">
            <Row stops={decide} labels={["10 best passages", "2 drafts", "verified"]} first={5} />
          </div>
        </div>
      </div>
    </section>
  );
}
