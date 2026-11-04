import ExamplesViewer from "@/components/ExamplesViewer";
import FoulExplainer from "@/components/FoulExplainer";
import FanQuestions from "@/components/FanQuestions";
import Pipeline from "@/components/Pipeline";
import StoryPlayer from "@/components/StoryPlayer";
import VerdictCompare from "@/components/VerdictCompare";
import examplesData from "@/data/examples.json";
import type { Example } from "@/lib/types";

const examples = examplesData as Example[];

// the clip the scroll story and the pipeline walk through (exported with its stills)
const story = examples.find((e) => e.story) ?? null;

export default function Home() {
  return (
    <>
      <section className="on-dark bg-[#070a08] text-white">
        <div className="mx-auto grid min-h-[calc(100svh-57px)] w-full max-w-6xl items-center gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] lg:gap-12">
          <div>
            <h1 className="text-4xl font-semibold leading-[1.04] tracking-tight sm:text-5xl">
              VAR tells you what.
              <span className="mt-1 block text-green-300">Foul Explainer shows you why.</span>
            </h1>
            <p className="mt-5 max-w-md text-lg leading-relaxed text-white/70">
              Give it a clip of a tackle or handball. An AI makes the call, quotes the exact rule behind it, and tells you how sure it is.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <a href="#story" className="rounded-lg bg-white px-5 py-3 text-sm font-semibold text-black hover:bg-white/90">
                Watch it judge a tackle
              </a>
              <a href="#try" className="rounded-lg px-5 py-3 text-sm font-semibold ring-1 ring-white/25 hover:bg-white/10">
                Try your own clip
              </a>
            </div>
            <p className="mt-5 text-xs text-white/50">An explanation for fans, not an official ruling.</p>
          </div>
          {story && <VerdictCompare ex={story} />}
        </div>
      </section>

      {story && <FanQuestions examples={examples} story={story} />}

      {story && <StoryPlayer ex={story} />}
      {story && <Pipeline ex={story} />}

      {examples.length > 0 && <ExamplesViewer examples={examples} />}

      <section id="try" className="scroll-mt-16 border-t border-line bg-surface/50">
        <FoulExplainer embedded />
      </section>

      <footer className="border-t border-line">
        <p className="mx-auto max-w-6xl px-4 py-8 text-xs leading-relaxed text-muted sm:px-6">
          An explanation of how the Laws of the Game apply to what the model saw, not an official ruling. Judges fouls,
          handball and cards (Law 12), not offside or goal-line calls. Rule excerpts © The IFAB, Laws of the Game 2026/27;
          referee guidance © the Premier League and UEFA, quoted with links. Match footage belongs to its broadcasters.
        </p>
      </footer>
    </>
  );
}
