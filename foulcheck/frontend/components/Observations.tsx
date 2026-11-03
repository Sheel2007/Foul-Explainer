import { Fragment } from "react";
import { parseTs, TS_IN_TEXT } from "@/lib/format";
import type { Observation } from "@/lib/types";

const yesNo = (v: boolean | null) => (v === null ? null : v ? "Yes" : "No");

/** Turns "00:03.8" inside text into buttons that seek the video. */
export function Timestamped({ text, onSeek }: { text: string; onSeek: (s: number) => void }) {
  const parts = text.split(TS_IN_TEXT);
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <button
            key={i}
            type="button"
            onClick={() => onSeek(Math.max(0, (parseTs(p) ?? 0) - 0.5))}
            className="rounded bg-pitch/10 px-1 font-mono text-[0.85em] text-pitch-dark underline-offset-2 hover:underline dark:text-green-300"
          >
            {p}
          </button>
        ) : (
          <Fragment key={i}>{p}</Fragment>
        ),
      )}
    </>
  );
}

export default function Observations({ obs, onSeek }: { obs: Observation; onSeek: (s: number) => void }) {
  const unsure = (field: string) => obs.uncertain_fields.some((f) => f === field || f.startsWith(`${field}.`));
  const c = obs.contact;
  const rows: [string, string | null, string][] = [
    ["Challenge", obs.challenge_type, "challenge_type"],
    ["Contact", c.made === null ? null : c.made ? [c.body_part_used, c.body_part_hit].filter(Boolean).join(" → ") || "Yes" : "No contact", "contact"],
    ["Ball played first", yesNo(obs.ball_played_first), "ball_played_first"],
    ["Studs showing", yesNo(obs.challenge?.studs_showing ?? null), "challenge.studs_showing"],
    ["Leg straight / lunge", obs.challenge ? [yesNo(obs.challenge.leg_straight), yesNo(obs.challenge.lunge)].map((v) => v ?? "?").join(" / ") : null, "challenge"],
    ["Speed and force", obs.speed_and_force, "speed_and_force"],
    ["Ball hit hand/arm", obs.handball.touched ? `Yes, ${obs.handball.arm_position ?? "arm position unclear"}` : yesNo(obs.handball.touched), "handball"],
    ["Where", obs.location, "location"],
    ["Attack", obs.attack_context, "attack_context"],
  ];
  return (
    <section aria-label="What the model saw" className="space-y-3">
      <h3 className="font-semibold">What the model saw</h3>
      {obs.summary && (
        <p className="leading-relaxed">
          <Timestamped text={obs.summary} onSeek={onSeek} />
        </p>
      )}
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
        {rows.map(([label, value, field]) => (
          <Fragment key={label}>
            <dt className="text-muted">{label}</dt>
            <dd className="first-letter:uppercase">
              {value ?? <span className="text-muted">Not visible</span>}
              {unsure(field) && (
                <span className="ml-2 rounded bg-amber-500/15 px-1.5 py-0.5 text-xs text-amber-800 dark:text-amber-300">unsure</span>
              )}
            </dd>
          </Fragment>
        ))}
      </dl>
      {obs.view_quality && <p className="text-sm text-muted">View: {obs.view_quality}</p>}
    </section>
  );
}
