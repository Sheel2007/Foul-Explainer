"use client";

import { useRef, useState } from "react";

const MAX_BYTES = 100 * 1024 * 1024;
const MAX_SECONDS = 60;
const TYPES = ["video/mp4", "video/quicktime", "video/webm"];
const EXTENSIONS = [".mp4", ".mov", ".webm", ".m4v"];

export interface PickedClip {
  file: File;
  url: string;
  duration: number | null;
}

function readDuration(url: string): Promise<number | null> {
  return new Promise((resolve) => {
    const v = document.createElement("video");
    v.preload = "metadata";
    v.onloadedmetadata = () => resolve(Number.isFinite(v.duration) ? v.duration : null);
    v.onerror = () => resolve(null); // some browsers can't read MOV metadata; the server checks again
    v.src = url;
  });
}

export async function checkClip(file: File): Promise<PickedClip | string> {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!TYPES.includes(file.type) && !EXTENSIONS.includes(ext)) return "Choose an MP4, MOV or WebM video.";
  if (file.size > MAX_BYTES) return `That file is ${(file.size / 1048576).toFixed(0)} MB; the limit is 100 MB.`;
  const url = URL.createObjectURL(file);
  const duration = await readDuration(url);
  if (duration !== null && duration > MAX_SECONDS) {
    URL.revokeObjectURL(url);
    return `That clip is ${Math.round(duration)} seconds long; the limit is ${MAX_SECONDS}. Trim it to the incident.`;
  }
  return { file, url, duration };
}

export default function UploadPanel({
  onSubmit,
  error,
  serverKey,
}: {
  onSubmit: (clip: PickedClip, context: string, apiKey: string) => void;
  error: string | null;
  /** true when the server may use its own key, so the visitor's key is optional */
  serverKey: boolean | null;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [clip, setClip] = useState<PickedClip | null>(null);
  const [context, setContext] = useState("");
  // Held in memory only, sent as a header with the upload. Never written to storage.
  const [apiKey, setApiKey] = useState("");
  const needsKey = serverKey === false;
  const [problem, setProblem] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  async function pick(file: File | undefined) {
    if (!file) return;
    setProblem(null);
    const result = await checkClip(file);
    if (typeof result === "string") {
      setProblem(result);
      setClip(null);
    } else {
      if (clip) URL.revokeObjectURL(clip.url);
      setClip(result);
    }
  }

  const message = problem ?? error;

  return (
    <form
      className="mx-auto w-full max-w-xl space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (clip && (!needsKey || apiKey.trim())) onSubmit(clip, context, apiKey);
      }}
    >
      <div
        role="button"
        tabIndex={0}
        aria-label="Choose a video clip"
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          pick(e.dataTransfer.files[0]);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
          dragging
            ? "border-pitch bg-pitch/5"
            : "border-line hover:border-pitch/60 hover:bg-surface"
        }`}
      >
        <svg aria-hidden viewBox="0 0 24 24" className="mb-3 h-10 w-10 text-pitch" fill="none" stroke="currentColor" strokeWidth={1.6}>
          <path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {clip ? (
          <>
            <p className="font-medium">{clip.file.name}</p>
            <p className="text-sm text-muted">
              {(clip.file.size / 1048576).toFixed(1)} MB
              {clip.duration !== null && ` · ${clip.duration.toFixed(1)} s`} · click to change
            </p>
          </>
        ) : (
          <>
            <p className="font-medium">Drop a clip here, or click to choose</p>
            <p className="mt-1 text-sm text-muted">One incident · 5–30 seconds · MP4, MOV or WebM</p>
          </>
        )}
        <input
          ref={input}
          type="file"
          accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm,.m4v"
          className="hidden"
          onChange={(e) => pick(e.target.files?.[0])}
        />
      </div>

      <details className="group text-sm" open={context.length > 0}>
        <summary className="cursor-pointer list-none text-muted hover:text-foreground">
          <span className="group-open:hidden">+ Add a note the clip doesn&apos;t show (optional)</span>
          <span className="hidden group-open:inline">Note (optional)</span>
        </summary>
        <textarea
          value={context}
          onChange={(e) => setContext(e.target.value)}
          maxLength={500}
          rows={2}
          placeholder="e.g. this was inside the penalty area, the defender was the last man"
          className="mt-1.5 w-full resize-none rounded-xl border border-line bg-background px-3 py-2 text-sm outline-none focus:border-pitch focus:ring-2 focus:ring-pitch/20"
        />
        <span className="text-xs text-muted">Treated as a hint, not a fact. The answer says if it relied on it.</span>
      </details>

      <label className="block">
        <span className="text-sm font-medium">
          Your Gemini API key{needsKey ? "" : " (optional)"}
        </span>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="AIza…"
          className="mt-1.5 w-full rounded-xl border border-line bg-background px-3 py-2 font-mono text-sm outline-none focus:border-pitch focus:ring-2 focus:ring-pitch/20"
        />
        <span className="text-xs text-muted">
          Used for this analysis only and never saved, not even in your browser.{" "}
          {needsKey ? "" : "Leave it blank to use the server's key. "}
          <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" className="underline hover:text-foreground">
            Get a free key
          </a>
          .
        </span>
      </label>

      {message && (
        <p role="alert" className="rounded-xl bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
          {message}
        </p>
      )}

      <button
        type="submit"
        disabled={!clip || (needsKey && !apiKey.trim())}
        className="w-full rounded-xl bg-pitch px-4 py-3 font-semibold text-white transition hover:bg-pitch-dark disabled:cursor-not-allowed disabled:opacity-40"
      >
        Explain the call
      </button>
    </form>
  );
}
