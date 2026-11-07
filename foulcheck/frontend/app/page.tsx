import ExamplesViewer from "@/components/ExamplesViewer";
import FoulExplainer from "@/components/FoulExplainer";
import Pipeline from "@/components/Pipeline";
import UploadUnavailable from "@/components/UploadUnavailable";
import VerdictCompare from "@/components/VerdictCompare";
import examplesData from "@/data/examples.json";
import { HAS_ANALYSIS_SERVER } from "@/lib/api";
import type { Example } from "@/lib/types";

const examples = examplesData as Example[];

// the clip the comparison and the pipeline walk through (exported with its stills)
const story = examples.find((e) => e.story) ?? null;

const FSA = "https://www.irishexaminer.com/sport/soccer/arid-41819207.html";
const LEAGUE = "https://www.goal.com/en/lists/premier-league-response-fsa-var-survey-fan-backlash/bltf5edf44bdc3c87c9";

export default function Home() {
  return (
    <>
      <section className="on-dark bg-[#070a08] text-white">
        <div className="mx-auto grid w-full max-w-6xl items-center gap-4 px-4 py-4 sm:min-h-[calc(100svh-57px)] sm:gap-8 sm:px-6 sm:py-8 lg:grid-cols-[minmax(0,0.72fr)_minmax(0,1.28fr)] lg:gap-10">
          <div>
            <h1 className="text-[1.55rem] font-semibold leading-[1.1] tracking-tight sm:text-5xl lg:text-[2.6rem]">
              VAR tells you what.
              <span className="block text-green-300 sm:mt-1">Foul Explainer shows you why.</span>
            </h1>
            <p className="mt-1.5 max-w-md text-sm text-white/70 sm:mt-4 sm:text-lg sm:leading-relaxed">An AI explanation of any tackle or handball clip.</p>
            <div className="mt-3 flex flex-wrap items-center gap-2 sm:mt-6 sm:gap-3">
              <a href="#how" className="rounded-lg bg-white px-3.5 py-2 text-sm font-semibold text-black hover:bg-white/90 sm:px-5 sm:py-3">
                See how it works
              </a>
              <a href="#try" className="rounded-lg px-3.5 py-2 text-sm font-semibold ring-1 ring-white/25 hover:bg-white/10 sm:px-5 sm:py-3">
                {HAS_ANALYSIS_SERVER ? "Try your own clip" : "Run it on your own clip"}
              </a>
            </div>
          </div>
          {story && <VerdictCompare ex={story} />}
        </div>
      </section>

      {story && <Pipeline ex={story} />}

      {examples.length > 0 && <ExamplesViewer examples={examples} />}

      <section id="try" className="scroll-mt-16 border-t border-line bg-surface/50">
        {HAS_ANALYSIS_SERVER ? <FoulExplainer embedded /> : <UploadUnavailable embedded />}
      </section>

      <footer className="border-t border-line">
        <p className="mx-auto max-w-6xl px-4 py-8 text-xs leading-relaxed text-muted sm:px-6">
          An explanation of how the Laws of the Game apply to what the model saw, not an official ruling, and it can be wrong. Judges
          fouls, handball and cards (Law 12), not offside or goal-line calls. More than 90% of matchgoing fans in a{" "}
          <a href={FSA} target="_blank" rel="noreferrer" className="underline underline-offset-2">
            2026 Football Supporters&apos; Association survey
          </a>{" "}
          disagree that VAR improved the matchgoing experience; the Premier League{" "}
          <a href={LEAGUE} target="_blank" rel="noreferrer" className="underline underline-offset-2">
            says its research
          </a>{" "}
          shows fans want it kept and improved. Rule excerpts © The IFAB, Laws of the Game 2026/27; referee guidance © the Premier League
          and UEFA, quoted with links. Match footage belongs to its broadcasters.
        </p>
      </footer>
    </>
  );
}
