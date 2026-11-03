import { explainAdjustment, unclearFacts } from "@/lib/confidence";
import type { Level } from "@/lib/types";

const LEVEL_TEXT: Record<Level, string> = {
  High: "text-pitch-dark dark:text-green-300",
  Medium: "text-amber-700 dark:text-amber-300",
  Low: "text-red-700 dark:text-red-300",
};
const LEVEL_BAR: Record<Level, string> = { High: "bg-pitch", Medium: "bg-amber-500", Low: "bg-red-500" };

/**
 * How sure the tool is and why: the decision model's own rating, each check that lowered it,
 * what the video model could not see, and how a referee could see it differently.
 */
export default function ConfidenceBreakdown({
  level,
  modelScore,
  score,
  adjustments,
  uncertainFields = [],
  grayAreas = [],
}: {
  level: Level;
  modelScore: number;
  score: number;
  adjustments: string[];
  uncertainFields?: string[];
  grayAreas?: string[];
}) {
  const deductions = adjustments.map(explainAdjustment);
  const unclear = unclearFacts(uncertainFields);
  const pct = (x: number) => `${Math.round(x * 100)}%`;

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-baseline justify-between gap-3">
          <span className={`text-lg font-semibold ${LEVEL_TEXT[level]}`}>{level} confidence</span>
          <span className="text-sm tabular-nums text-muted">{pct(score)}</span>
        </div>
        {/* filled = final score, hatched = what the checks took off the model's own rating */}
        <div className="relative mt-2 h-2.5 overflow-hidden rounded-full bg-line" aria-hidden>
          <div
            className="absolute inset-y-0 left-0 bg-[repeating-linear-gradient(135deg,var(--muted)_0_3px,transparent_3px_6px)] opacity-50"
            style={{ width: pct(modelScore) }}
          />
          <div className={`absolute inset-y-0 left-0 rounded-full ${LEVEL_BAR[level]}`} style={{ width: pct(score) }} />
          <div className="absolute inset-y-0 left-1/2 w-px bg-background" />
          <div className="absolute inset-y-0 left-3/4 w-px bg-background" />
        </div>
        <div className="mt-1 flex justify-between text-[11px] text-muted">
          <span>Low</span>
          <span className="pl-8">Medium from 50%</span>
          <span>High from 75%</span>
        </div>
      </div>

      <ol className="space-y-2 text-sm">
        <li className="flex gap-3">
          <span className="w-12 shrink-0 text-right font-medium tabular-nums">{pct(modelScore)}</span>
          <span className="text-muted">The decision model&apos;s own rating of its call.</span>
        </li>
        {deductions.map((d) => (
          <li key={d.text} className="flex gap-3">
            <span className="w-12 shrink-0 text-right font-medium tabular-nums text-red-600 dark:text-red-400">
              {d.points ? `−${d.points}` : "cap"}
            </span>
            <span>{d.text}</span>
          </li>
        ))}
        {deductions.length === 0 && (
          <li className="flex gap-3">
            <span className="w-12 shrink-0 text-right text-pitch">✓</span>
            <span className="text-muted">
              No check lowered it: the key facts were clearly visible and a second, independent run agreed.
            </span>
          </li>
        )}
      </ol>

      {unclear.length > 0 && (
        <div className="text-sm">
          <p className="font-medium">Couldn&apos;t see clearly</p>
          <p className="mt-0.5 text-muted first-letter:uppercase">{unclear.join(" · ")}</p>
        </div>
      )}

      {grayAreas.length > 0 && (
        <div className="text-sm">
          <p className="font-medium">A referee could also see it this way</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-muted">
            {grayAreas.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
