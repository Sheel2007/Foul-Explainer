import type { Restart, Verdict } from "./types";

/** "01:07.4" -> 67.4 */
export function parseTs(ts: string | null | undefined): number | null {
  const m = ts?.trim().match(/^(\d{1,2}):(\d{2}(?:\.\d+)?)$/);
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

/** 67.43 -> "1:07.4" */
export function fmtTime(seconds: number): string {
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  return `${m}:${(s - m * 60).toFixed(1).padStart(4, "0")}`;
}

export const VERDICT_LABEL: Record<Verdict, string> = {
  foul: "Foul",
  no_foul: "No foul",
  handball: "Handball",
  cannot_determine: "Cannot tell",
};

export const RESTART_LABEL: Record<Restart, string> = {
  direct_free_kick: "Direct free kick",
  indirect_free_kick: "Indirect free kick",
  penalty_kick: "Penalty kick",
  play_on: "Play on",
  unknown: "Restart unclear",
};

export const TS_IN_TEXT = /\b(\d{2}:\d{2}\.\d)\b/g;
