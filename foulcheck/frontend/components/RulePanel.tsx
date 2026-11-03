import type { Citation } from "@/lib/types";

/** The quote with the deciding words marked. */
export function Quote({ text, highlight }: { text: string; highlight: string | null }) {
  const i = highlight ? text.toLowerCase().indexOf(highlight.toLowerCase()) : -1;
  if (!highlight || i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <mark className="rounded bg-yellow-300 px-0.5 not-italic text-black">{text.slice(i, i + highlight.length)}</mark>
      {text.slice(i + highlight.length)}
    </>
  );
}

const PUBLISHER: Record<string, string> = { PL: "Premier League", UEFA: "UEFA" };

type Cited = Pick<Citation, "section" | "title" | "kind" | "page">;

/** Short badge: "Law 12.4", or "PL guidance". */
export function badge(c: Pick<Cited, "section" | "kind">) {
  return c.kind === "guidance" ? `${c.section} guidance` : `Law ${c.section}`;
}

/** Where the passage comes from, for the link under a quote. */
export function sourceLabel(c: Partial<Cited> & Pick<Cited, "section" | "title">) {
  if (c.kind === "guidance") return `${PUBLISHER[c.section] ?? c.section} referee guidance: ${c.title}`;
  return `Law ${c.section} · ${c.title}, Laws of the Game 2026/27` + (c.page ? `, page ${c.page}` : "");
}

export default function RulePanel({ citations, edition }: { citations: Citation[]; edition: string }) {
  return (
    <section aria-label="The rule" className="space-y-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="font-semibold">The rule</h3>
        <span className="text-xs text-muted">{edition}</span>
      </div>
      {citations.length === 0 && <p className="text-sm text-muted">No Law passages were cited for this answer.</p>}
      <ul className="space-y-2" data-testid="rule-panel">
        {citations.map((c, i) => (
          <li key={c.chunk_id}>
            <details className="group rounded-xl border border-line bg-surface open:bg-background" open={i === 0}>
              <summary className="flex cursor-pointer list-none items-start gap-3 p-3">
                <span
                  className={`mt-0.5 shrink-0 rounded-md px-1.5 py-0.5 text-xs font-bold ${
                    c.kind === "guidance" ? "border border-foreground" : "bg-foreground text-background"
                  }`}
                >
                  {badge(c)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">
                    {c.title}
                    {c.subtitle && <span className="text-muted"> · {c.subtitle}</span>}
                  </span>
                  <span className="block text-sm text-muted">{c.why}</span>
                </span>
                <span aria-hidden className="text-muted transition group-open:rotate-90">›</span>
              </summary>
              <div className="space-y-2 px-3 pb-3 pl-[4.25rem]">
                {c.quote ? (
                  <blockquote className="border-l-2 border-pitch pl-3 text-sm italic leading-relaxed">
                    “<Quote text={c.quote} highlight={c.highlight} />”
                  </blockquote>
                ) : (
                  <p className="text-sm text-muted">See the official text for the exact wording.</p>
                )}
                <a
                  href={c.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-block text-sm font-medium text-pitch-dark underline-offset-2 hover:underline dark:text-green-300"
                >
                  {c.kind === "guidance" ? `${PUBLISHER[c.section] ?? c.section} guidance page` : `Official Laws PDF, page ${c.page}`} ↗
                </a>
              </div>
            </details>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">
        Excerpts from the Laws of the Game © The IFAB, quoted for explanation.
        {citations.some((c) => c.kind === "guidance") &&
          " Guidance passages are official Premier League or UEFA notes on how referees apply the Laws; the Laws decide."}
      </p>
    </section>
  );
}
