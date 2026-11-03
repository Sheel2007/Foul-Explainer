import { RESTART_LABEL, VERDICT_LABEL } from "@/lib/format";
import type { Ruling } from "@/lib/types";

const LEVEL_STYLE = {
  High: "bg-pitch/15 text-pitch-dark dark:text-green-300",
  Medium: "bg-amber-500/15 text-amber-800 dark:text-amber-300",
  Low: "bg-red-500/15 text-red-800 dark:text-red-300",
};

function CardIcon({ card }: { card: "yellow" | "red" }) {
  return (
    <span
      aria-hidden
      className={`inline-block h-12 w-9 rotate-6 rounded-md shadow-md ${card === "yellow" ? "bg-yellow-400" : "bg-red-600"}`}
    />
  );
}

export default function VerdictCard({ ruling }: { ruling: Ruling }) {
  const { verdict, card, restart, offence_type, confidence } = ruling;
  return (
    <section aria-label="Verdict" className="rounded-2xl border border-line bg-surface p-5">
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">The call</p>
          <h2 className="mt-1 text-4xl font-bold tracking-tight" data-testid="verdict">
            {VERDICT_LABEL[verdict]}
          </h2>
          <p className="mt-2 text-lg">
            {RESTART_LABEL[restart]}
            {card !== "none" && <>, {card} card</>}
          </p>
          {offence_type && <p className="text-sm text-muted first-letter:uppercase">{offence_type}</p>}
        </div>
        {card !== "none" && <CardIcon card={card} />}
      </div>

      <p className="mt-4 text-sm">
        <a href="#how-sure" className={`rounded-full px-2.5 py-1 font-semibold ${LEVEL_STYLE[confidence.level]}`}>
          {confidence.level} confidence · {Math.round(confidence.score * 100)}%
        </a>
      </p>
    </section>
  );
}
