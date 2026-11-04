import type { Example } from "@/lib/types";
import ConfidenceBreakdown from "./ConfidenceBreakdown";
import { Quote, sourceLabel } from "./RulePanel";

const FSA = "https://www.irishexaminer.com/sport/soccer/arid-41819207.html";
const LEAGUE = "https://www.goal.com/en/lists/premier-league-response-fsa-var-survey-fan-backlash/bltf5edf44bdc3c87c9";
const PL_SCREENS = "https://www.premierleague.com/news/1293250";

function Question({ n, name, question, children }: { n: number; name: string; question: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-sm font-medium text-red-400">
        {n}. {name}
      </p>
      <h3 className="mt-2 text-3xl font-semibold leading-[1.1] tracking-tight sm:text-4xl">“{question}”</h3>
      <div className="mt-4 space-y-3 leading-relaxed text-white/70">{children}</div>
    </div>
  );
}

function Answer({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-w-0 border-l-2 border-green-400 pl-5">
      <p className="text-sm font-medium text-green-300">What Foul Explainer does</p>
      {children}
    </div>
  );
}

function Tackle({ ex }: { ex: Example }) {
  const f = ex.facts;
  const rows = [
    ["Studs showing", f?.studs_showing ? "Yes" : f?.studs_showing === false ? "No" : "Not visible"],
    ["Contact", [f?.body_part_used, f?.body_part_hit].filter(Boolean).join(" → ") || "Not visible"],
    ["Speed and force", f?.speed_and_force ?? "Not visible"],
  ];
  return (
    <div className="min-w-0">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={ex.poster} alt={ex.title} className="aspect-video w-full rounded-md object-cover" />
      <p className="mt-2 flex items-center gap-2 font-semibold">
        <span aria-hidden className={`h-4 w-3 rounded-[2px] ${ex.ai.card === "red" ? "bg-red-600" : "bg-yellow-400"}`} />
        {ex.ai.card === "red" ? "Red card" : "Yellow card"}
      </p>
      <dl className="mt-1 text-xs">
        {rows.map(([k, v]) => (
          <div key={k} className="border-t border-white/15 py-1">
            <dt className="text-white/50">{k}</dt>
            <dd className="first-letter:uppercase">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** The three complaints about VAR, in the words fans use, each answered with the tool's real output. */
export default function FanQuestions({ examples, story }: { examples: Example[]; story: Example }) {
  const yellow = examples.find((e) => e.id !== story.id && e.ai.card === "yellow" && e.label?.card === "yellow");
  const unsure = [...examples].sort((a, b) => a.ai.confidence_detail.score - b.ai.confidence_detail.score)[0];
  const rule = story.ai.citations.find((c) => c.kind === "guidance" && c.quote) ?? story.ai.citations.find((c) => c.quote);
  const opinion = examples.flatMap((e) => e.ai.citations).find((c) => c.quote?.includes("considered by the referee"));
  const quoted = opinion?.quote ?? "";
  const lawPhrase = quoted.slice(Math.max(0, quoted.indexOf("in a manner"))).split(":")[0];

  return (
    <section id="why" className="on-dark scroll-mt-16 bg-[#070a08] py-20 text-white sm:py-28">
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        <h2 className="max-w-3xl text-2xl font-medium leading-snug text-white/70 sm:text-3xl">
          VAR was meant to settle arguments. Fans are still left asking the same three questions.
        </h2>

        <div className="mt-14 space-y-20 sm:space-y-24">
          <div className="grid gap-8 lg:grid-cols-2 lg:gap-16">
            <Question n={1} name="No real explanation" question="Why was that a red?">
              <p>
                Stadium screens were built to show{" "}
                <a href={PL_SCREENS} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-white">
                  what is being checked and the final decision
                </a>
                . New announcements help, but fans told the{" "}
                <a href={FSA} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-white">
                  Football Supporters&apos; Association
                </a>{" "}
                they are still unhappy with how decisions are communicated.
              </p>
            </Question>
            <Answer>
              <p className="mt-3 text-lg leading-relaxed">{story.ai.explanation}</p>
              {rule?.quote && (
                <>
                  <p className="mt-4 italic leading-relaxed">
                    “<Quote text={rule.quote} highlight={rule.highlight} />”
                  </p>
                  <a href={rule.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs text-white/60 underline-offset-2 hover:underline">
                    {sourceLabel(rule)} ↗
                  </a>
                </>
              )}
            </Answer>
          </div>

          <div className="grid gap-8 lg:grid-cols-2 lg:gap-16">
            <Question n={2} name="Inconsistent decisions" question="That was only a yellow last week.">
              {opinion?.quote && (
                <p>
                  The rule itself leaves room for this. A tackle is a foul when it&apos;s done{" "}
                  <span className="italic">
                    “<Quote text={lawPhrase} highlight="considered by the referee" />”
                  </span>
                  . Different referees can reach different calls, and fans rarely see what separated them.
                </p>
              )}
            </Question>
            <Answer>
              <p className="mt-3 leading-relaxed">
                Every tackle goes through the same checklist and the same rule text, so you can compare two calls line by line. Here are two
                sliding tackles, and what separated them.
              </p>
              <div className="mt-4 grid grid-cols-2 gap-4">
                {yellow && <Tackle ex={yellow} />}
                <Tackle ex={story} />
              </div>
              <p className="mt-3 text-xs leading-relaxed text-white/60">
                It isn&apos;t perfectly consistent either. Each call runs twice, and when the two runs disagree it says so and lowers its
                confidence.
              </p>
            </Answer>
          </div>

          <div className="grid gap-8 lg:grid-cols-2 lg:gap-16">
            <Question n={3} name="A black box" question="What did they even look at?">
              <p>
                The review happens in a video room you can&apos;t see. You rarely get the angles used, what was hard to see, or how close
                the call was. You wait, then get the result.
              </p>
            </Question>
            <Answer>
              <p className="mt-3 leading-relaxed">
                It shows its working, including its doubts. On this clip, it told us not to trust it much, and exactly why:
              </p>
              <div className="mt-4">
                <ConfidenceBreakdown
                  level={unsure.ai.confidence}
                  modelScore={unsure.ai.confidence_detail.model_score}
                  score={unsure.ai.confidence_detail.score}
                  adjustments={unsure.ai.confidence_detail.adjustments}
                  uncertainFields={unsure.ai.uncertain_fields}
                />
              </div>
            </Answer>
          </div>
        </div>

        <div className="mt-20 grid gap-8 border-t border-white/15 pt-10 sm:grid-cols-[auto_1fr] sm:items-center sm:gap-12">
          <p className="text-6xl font-semibold tracking-tight sm:text-7xl">90%+</p>
          <div className="max-w-2xl">
            <p className="text-lg leading-relaxed">
              of matchgoing Premier League fans disagree that VAR has made the matchgoing experience better, in a{" "}
              <a href={FSA} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                March 2026 Football Supporters&apos; Association survey
              </a>{" "}
              of nearly 8,000 fans.
            </p>
            <p className="mt-2 text-sm leading-relaxed text-white/60">
              The Premier League{" "}
              <a href={LEAGUE} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                says its own research
              </a>{" "}
              shows fans want VAR kept and improved. Foul Explainer doesn&apos;t replace VAR or referees. It explains the decision, and it can
              be wrong too.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
