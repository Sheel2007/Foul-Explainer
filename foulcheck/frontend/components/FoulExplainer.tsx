"use client";

import { useEffect, useRef, useState } from "react";
import { createJob, explainedVideoUrl, getConfig, getResult, watchJob } from "@/lib/api";
import type { JobStatus, Ruling } from "@/lib/types";
import ConfidenceBreakdown from "./ConfidenceBreakdown";
import FeedbackForm from "./FeedbackForm";
import Observations, { Timestamped } from "./Observations";
import ProgressStages from "./ProgressStages";
import RulePanel from "./RulePanel";
import UploadPanel, { type PickedClip } from "./UploadPanel";
import VerdictCard from "./VerdictCard";
import VideoPlayer, { type PlayerHandle } from "./VideoPlayer";

type Phase = "idle" | "working" | "done";

/** `embedded` = a section near the bottom of the homepage rather than its own page. */
export default function FoulExplainer({ embedded = false }: { embedded?: boolean }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [clip, setClip] = useState<PickedClip | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [ruling, setRuling] = useState<Ruling | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState(0);
  const stopWatching = useRef<(() => void) | null>(null);
  const player = useRef<PlayerHandle>(null);
  const root = useRef<HTMLDivElement>(null);

  // null until we hear back: whether the server may use its own key, so the visitor's is optional
  const [serverKey, setServerKey] = useState<boolean | null>(null);

  useEffect(() => () => stopWatching.current?.(), []);
  useEffect(() => {
    getConfig().then((c) => setServerKey(c.server_key)).catch(() => setServerKey(false));
  }, []);

  async function start(picked: PickedClip, context: string, apiKey: string) {
    setClip(picked);
    setError(null);
    setJob(null);
    setRuling(null);
    setStartedAt(Date.now());
    setPhase("working");
    if (embedded) root.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    else window.scrollTo({ top: 0 });
    try {
      const created = await createJob(picked.file, context, apiKey);
      setJob(created);
      stopWatching.current = watchJob(created.id, async (status) => {
        setJob(status);
        if (status.status === "error") {
          setError(status.error ?? "Something went wrong.");
          setPhase("idle");
        } else if (status.status === "done") {
          try {
            setRuling(await getResult(status.id));
            setPhase("done");
          } catch (e) {
            setError((e as Error).message);
            setPhase("idle");
          }
        }
      });
    } catch (e) {
      setError((e as Error).message === "Failed to fetch" ? "Could not reach the analysis server." : (e as Error).message);
      setPhase("idle");
    }
  }

  function reset() {
    stopWatching.current?.();
    if (clip) URL.revokeObjectURL(clip.url);
    setClip(null);
    setJob(null);
    setRuling(null);
    setPhase("idle");
  }

  const seek = (s: number) => player.current?.seek(s);
  const upload = <UploadPanel onSubmit={start} error={error} serverKey={serverKey} />;

  const Title = embedded ? "h2" : "h1";

  return (
    <div ref={root} className={`mx-auto w-full max-w-6xl scroll-mt-16 px-4 sm:px-6 ${embedded ? "py-20" : "py-8"}`}>
      <header className="mb-8 flex items-center gap-3">
        <div className="mr-auto">
          {embedded && phase === "idle" && <p className="text-sm font-medium text-pitch">Your turn</p>}
          <Title className={`font-semibold tracking-tight ${embedded ? "mt-1 text-3xl sm:text-4xl" : "text-2xl"}`}>
            {phase !== "idle" ? clip?.file.name : embedded ? "Try it on your own clip" : "Upload a clip"}
          </Title>
          <p className={`text-muted ${embedded ? "mt-3" : "text-sm"}`}>
            {embedded && phase === "idle"
              ? "One incident, 5 to 30 seconds. You need your own API key from Gemini, Anthropic or OpenAI; it's used for this analysis only and never saved."
              : "See how the Laws of the Game apply to it."}
          </p>
        </div>
        {phase !== "idle" && (
          <button type="button" onClick={reset} className="rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-surface">
            New clip
          </button>
        )}
      </header>

      {phase === "idle" && (
        <div className="py-6">
          {upload}
          <p className="mx-auto mt-6 max-w-xl text-center text-xs text-muted">
            Judges fouls, handball and cards under Law 12. Not offside or goal-line calls. Clips are deleted after analysis.
          </p>
        </div>
      )}

      {phase !== "idle" && clip && (
        // DOM order is video, verdict, observations so phones show the answer right under the clip;
        // on wide screens the grid puts video and observations together in the left column.
        <div className="grid gap-8 lg:grid-cols-[1.15fr_1fr] lg:grid-rows-[auto_1fr]">
          <div className="lg:col-start-1 lg:row-start-1">
            <VideoPlayer
              ref={player}
              src={clip.url}
              keyMoment={ruling?.key_moment ?? null}
              views={ruling?.video?.locate.views}
              inspected={ruling?.video?.window ?? null}
            />
          </div>

          <div className="space-y-6 lg:col-start-2 lg:row-span-2 lg:row-start-1">
            {phase === "working" && <ProgressStages job={job} startedAt={startedAt} />}
            {ruling && (
              <>
                <VerdictCard ruling={ruling} />
                {job?.has_video && (
                  <a
                    href={explainedVideoUrl(job.id)}
                    download
                    className="flex items-center justify-between gap-3 rounded-2xl border border-line bg-surface p-4 hover:border-pitch"
                  >
                    <span>
                      <span className="block font-semibold">Download the explained video</span>
                      <span className="block text-sm text-muted">Your clip with the call and the highlighted rule beside it.</span>
                    </span>
                    <span aria-hidden className="text-2xl text-pitch">↓</span>
                  </a>
                )}
                <section aria-label="Explanation" className="space-y-2">
                  <h3 className="font-semibold">Why</h3>
                  <p className="leading-relaxed">
                    <Timestamped text={ruling.explanation} onSeek={seek} />
                  </p>
                </section>
                <RulePanel citations={ruling.citations} edition={ruling.edition_label} />
                <section id="how-sure" aria-label="How sure" className="scroll-mt-20 space-y-3">
                  <h3 className="font-semibold">How sure, and why</h3>
                  <ConfidenceBreakdown
                    level={ruling.confidence.level}
                    modelScore={ruling.confidence.model_score}
                    score={ruling.confidence.score}
                    adjustments={ruling.confidence.adjustments}
                    uncertainFields={ruling.observation?.uncertain_fields}
                    grayAreas={ruling.gray_areas}
                  />
                </section>
                {job && <FeedbackForm jobId={job.id} />}
                <p className="text-xs text-muted">{ruling.disclaimer}</p>
              </>
            )}
          </div>

          {ruling && (
            <div className="space-y-6 lg:col-start-1 lg:row-start-2">
              {ruling.observation && <Observations obs={ruling.observation} onSeek={seek} />}
              {ruling.context_hint && (
                <p className="rounded-xl bg-surface p-3 text-sm">
                  <span className="text-muted">Your note: </span>“{ruling.context_hint}”
                  <span className="text-muted">
                    {ruling.used_user_context ? " The answer relied on it." : " The answer did not rely on it."}
                  </span>
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
