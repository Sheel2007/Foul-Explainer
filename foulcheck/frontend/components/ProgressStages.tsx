"use client";

import { useEffect, useState } from "react";
import type { JobStatus } from "@/lib/types";

export default function ProgressStages({ job, startedAt }: { job: JobStatus | null; startedAt: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, []);

  const stages = job?.stages ?? [];
  const current = job?.stage ? stages.findIndex((s) => s.key === job.stage) : -1;
  const steps = [{ key: "upload", label: "Uploading the clip" }, ...stages];
  const active = job ? current + 1 : 0; // index into steps; upload is done once a job exists

  return (
    <div className="rounded-2xl border border-line bg-surface p-5" aria-live="polite">
      <ol className="space-y-3">
        {steps.map((s, i) => {
          const state = i < active ? "done" : i === active ? "active" : "todo";
          return (
            <li key={s.key} className="flex items-center gap-3">
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs ${
                  state === "done"
                    ? "bg-pitch text-white"
                    : state === "active"
                      ? "border-2 border-pitch"
                      : "border border-line text-muted"
                }`}
              >
                {state === "done" ? "✓" : state === "active" ? <span className="h-2.5 w-2.5 animate-ping rounded-full bg-pitch" /> : i + 1}
              </span>
              <span className={state === "todo" ? "text-muted" : state === "active" ? "font-medium" : ""}>{s.label}</span>
            </li>
          );
        })}
      </ol>
      <p className="mt-4 text-sm text-muted">
        {Math.floor((now - startedAt) / 1000)} s elapsed. A careful look at the video can take a minute or two.
      </p>
    </div>
  );
}
