import ExamplesViewer from "@/components/ExamplesViewer";
import FoulExplainer from "@/components/FoulExplainer";
import FoulField from "@/components/FoulField";
import Pipeline from "@/components/Pipeline";
import StoryPlayer from "@/components/StoryPlayer";
import examplesData from "@/data/examples.json";
import type { Example } from "@/lib/types";

const examples = examplesData as Example[];

// the clip the scroll story and the pipeline walk through (exported with its stills)
const story = examples.find((e) => e.story) ?? null;

export default function Home() {
  return (
    <>
      <section className="on-dark relative isolate flex min-h-[calc(100svh-57px)] items-center overflow-hidden bg-[#070a08]">
        <div aria-hidden className="absolute inset-0 -z-20 bg-[radial-gradient(ellipse_at_50%_120%,#14532d_0%,transparent_60%)]" />
        <div className="absolute inset-0 -z-10">
          <FoulField />
        </div>
        {/* keep the centre readable over the cards */}
        <div aria-hidden className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_55%_45%_at_50%_50%,rgba(7,10,8,0.92)_0%,rgba(7,10,8,0.6)_55%,transparent_100%)]" />
        <div className="mx-auto w-full max-w-3xl px-4 py-24 text-center sm:px-6">
          <p className="text-sm font-medium tracking-wide text-green-300">AI referee decisions, explained</p>
          <h1 className="mt-4 text-5xl font-semibold leading-[1.02] tracking-tight sm:text-7xl">
            One call can change a match.
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-muted">
            Foul Explainer watches a clip of a tackle or handball and tells you the call, the card, and the exact line of
            the Laws of the Game behind it, so you can see why, not just what.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <a href="#examples" className="rounded-xl bg-white px-5 py-3 text-sm font-semibold text-black hover:bg-white/90">
              See it judge {examples.length} real tackles
            </a>
            <a href="#try" className="rounded-xl bg-black/60 px-5 py-3 text-sm font-semibold text-white ring-1 ring-white/25 backdrop-blur hover:bg-white/10">
              Try your own clip
            </a>
          </div>
        </div>
      </section>

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
