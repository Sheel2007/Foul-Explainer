"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { fmtTime, parseTs } from "@/lib/format";
import type { View } from "@/lib/types";

export interface PlayerHandle {
  seek: (seconds: number) => void;
}

const SPEEDS = [0.25, 0.5, 1];

const VideoPlayer = forwardRef<
  PlayerHandle,
  { src: string; keyMoment: string | null; views?: View[]; inspected?: [number, number] | null }
>(function VideoPlayer({ src, keyMoment, views = [], inspected = null }, ref) {
  const video = useRef<HTMLVideoElement>(null);
  const [duration, setDuration] = useState(0);
  const [time, setTime] = useState(0);
  const [speed, setSpeed] = useState(1);
  const key = parseTs(keyMoment);

  useImperativeHandle(ref, () => ({
    seek(seconds: number) {
      const v = video.current;
      if (!v) return;
      v.currentTime = Math.max(0, seconds);
      v.scrollIntoView({ behavior: "smooth", block: "nearest" });
    },
  }));

  useEffect(() => {
    if (video.current) video.current.playbackRate = speed;
  }, [speed]);

  const pct = (t: number) => `${duration ? Math.min(100, (t / duration) * 100) : 0}%`;

  function jumpToContact() {
    const v = video.current;
    if (!v || key === null) return;
    v.currentTime = Math.max(0, key - 1);
    setSpeed(0.25);
    v.playbackRate = 0.25;
    void v.play();
  }

  return (
    <div className="space-y-3">
      <video
        ref={video}
        src={src}
        controls
        muted
        playsInline
        className="aspect-video w-full rounded-2xl bg-black"
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
        onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
      />

      <div
        className="relative h-8 cursor-pointer select-none"
        role="slider"
        aria-label="Clip timeline"
        aria-valuemin={0}
        aria-valuemax={duration}
        aria-valuenow={time}
        tabIndex={0}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          if (video.current && duration) video.current.currentTime = ((e.clientX - r.left) / r.width) * duration;
        }}
      >
        <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-line" />
        {inspected && (
          <div
            title="Window the model inspected closely"
            className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-pitch/30"
            style={{ left: pct(inspected[0]), width: `calc(${pct(inspected[1])} - ${pct(inspected[0])})` }}
          />
        )}
        <div className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-foreground/40" style={{ width: pct(time) }} />
        {views.map((v) => {
          const t = parseTs(v.contact_time);
          return t === null ? null : (
            <span
              key={v.contact_time}
              title={`${v.kind === "live" ? "Live" : "Replay"} view of the contact (${v.contact_time})`}
              className="absolute top-1/2 h-3 w-0.5 -translate-x-1/2 -translate-y-1/2 bg-muted"
              style={{ left: pct(t) }}
            />
          );
        })}
        {key !== null && (
          <span
            data-testid="key-moment-marker"
            title={`Key moment ${keyMoment}`}
            className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-sm border-2 border-background bg-pitch shadow"
            style={{ left: pct(key) }}
          />
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <button
          type="button"
          onClick={jumpToContact}
          disabled={key === null}
          className="rounded-lg bg-pitch px-3 py-1.5 font-medium text-white hover:bg-pitch-dark disabled:opacity-40"
        >
          Jump to contact {key !== null && `(${fmtTime(key)})`}
        </button>
        <div className="ml-auto flex overflow-hidden rounded-lg border border-line" role="group" aria-label="Playback speed">
          {SPEEDS.map((s) => (
            <button
              type="button"
              key={s}
              onClick={() => setSpeed(s)}
              aria-pressed={speed === s}
              className={`px-2.5 py-1.5 ${speed === s ? "bg-foreground text-background" : "hover:bg-surface"}`}
            >
              {s}x
            </button>
          ))}
        </div>
        <span className="tabular-nums text-muted">
          {fmtTime(time)} / {fmtTime(duration)}
        </span>
      </div>
    </div>
  );
});

export default VideoPlayer;
