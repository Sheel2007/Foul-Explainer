import type { JobStatus, Ruling } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function errorText(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {}
  return `Request failed (${res.status})`;
}

/** Whether the server can fall back to its own key, so a visitor's key is optional. */
export async function getConfig(): Promise<{ server_key: boolean; edition: string }> {
  const res = await fetch(`${API_URL}/api/config`);
  if (!res.ok) throw new Error(await errorText(res));
  return res.json();
}

/** `apiKey` travels only in this request's header; nothing here stores it. */
export async function createJob(file: File, context: string, apiKey?: string): Promise<JobStatus> {
  const form = new FormData();
  form.append("file", file);
  if (context.trim()) form.append("context", context.trim());
  const headers: HeadersInit = apiKey?.trim() ? { "X-Gemini-Api-Key": apiKey.trim() } : {};
  const res = await fetch(`${API_URL}/api/jobs`, { method: "POST", body: form, headers });
  if (!res.ok) throw new Error(await errorText(res));
  return res.json();
}

export const explainedVideoUrl = (jobId: string) => `${API_URL}/api/jobs/${jobId}/video`;

export async function getResult(jobId: string): Promise<Ruling> {
  const res = await fetch(`${API_URL}/api/jobs/${jobId}/result`);
  if (!res.ok) throw new Error(await errorText(res));
  return res.json();
}

/** Follow a job's progress over server-sent events, falling back to polling if the stream drops. */
export function watchJob(jobId: string, onStatus: (s: JobStatus) => void): () => void {
  let stopped = false;
  let poll: ReturnType<typeof setInterval> | undefined;
  const source = new EventSource(`${API_URL}/api/jobs/${jobId}/events`);

  const handle = (s: JobStatus) => {
    if (stopped) return;
    onStatus(s);
    if (s.status === "done" || s.status === "error") stop();
  };

  source.addEventListener("status", (e) => handle(JSON.parse((e as MessageEvent).data)));
  source.onerror = () => {
    source.close();
    if (stopped || poll) return;
    poll = setInterval(async () => {
      const res = await fetch(`${API_URL}/api/jobs/${jobId}`).catch(() => null);
      if (res?.ok) handle(await res.json());
    }, 2000);
  };

  function stop() {
    stopped = true;
    source.close();
    if (poll) clearInterval(poll);
  }
  return stop;
}

export interface FeedbackInput {
  job_id: string;
  rating: "up" | "down";
  would_call?: "foul" | "no_foul" | "handball" | "not_sure";
  would_card?: "none" | "yellow" | "red";
  comment?: string;
}

export async function sendFeedback(fb: FeedbackInput): Promise<void> {
  const res = await fetch(`${API_URL}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fb),
  });
  if (!res.ok) throw new Error(await errorText(res));
}
