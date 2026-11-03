"use client";

import { useState } from "react";
import { sendFeedback, type FeedbackInput } from "@/lib/api";

export default function FeedbackForm({ jobId }: { jobId: string }) {
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [call, setCall] = useState<FeedbackInput["would_call"]>();
  const [card, setCard] = useState<FeedbackInput["would_card"]>();
  const [comment, setComment] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  if (state === "sent") {
    return <p className="rounded-xl bg-pitch/10 p-4 text-sm">Thanks. Your call helps us test the explainer.</p>;
  }

  const choice = (active: boolean) =>
    `rounded-lg border px-3 py-1.5 text-sm ${active ? "border-pitch bg-pitch/10 font-medium" : "border-line hover:bg-surface"}`;

  return (
    <form
      className="space-y-3 rounded-2xl border border-line p-4"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!rating) return;
        setState("sending");
        try {
          await sendFeedback({ job_id: jobId, rating, would_call: call, would_card: card, comment: comment.trim() || undefined });
          setState("sent");
        } catch {
          setState("error");
        }
      }}
    >
      <div className="flex items-center gap-2">
        <span className="mr-auto font-semibold">Was this explanation right?</span>
        <button type="button" aria-pressed={rating === "up"} onClick={() => setRating("up")} className={choice(rating === "up")}>
          👍 Yes
        </button>
        <button type="button" aria-pressed={rating === "down"} onClick={() => setRating("down")} className={choice(rating === "down")}>
          👎 No
        </button>
      </div>
      {rating && (
        <>
          <fieldset className="space-y-2">
            <legend className="text-sm text-muted">What would you have called?</legend>
            <div className="flex flex-wrap gap-2">
              {(["foul", "no_foul", "handball", "not_sure"] as const).map((v) => (
                <button key={v} type="button" onClick={() => setCall(v)} className={choice(call === v)}>
                  {{ foul: "Foul", no_foul: "No foul", handball: "Handball", not_sure: "Not sure" }[v]}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {(["none", "yellow", "red"] as const).map((v) => (
                <button key={v} type="button" onClick={() => setCard(v)} className={choice(card === v)}>
                  {{ none: "No card", yellow: "Yellow", red: "Red" }[v]}
                </button>
              ))}
            </div>
          </fieldset>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            rows={2}
            placeholder="Anything the explainer got wrong? (optional)"
            className="w-full resize-none rounded-xl border border-line bg-background px-3 py-2 text-sm outline-none focus:border-pitch"
          />
          <div className="flex items-center gap-3">
            <button type="submit" disabled={state === "sending"} className="rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background disabled:opacity-50">
              {state === "sending" ? "Sending…" : "Send feedback"}
            </button>
            {state === "error" && <span className="text-sm text-red-600">Could not send. Try again.</span>}
          </div>
        </>
      )}
    </form>
  );
}
