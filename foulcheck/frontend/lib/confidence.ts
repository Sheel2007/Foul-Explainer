/** Turns the backend's confidence adjustments ("-0.24: video model unsure of a, b") into plain sentences. */

const FIELD: Record<string, string> = {
  ball_played_first: "whether the ball was played first",
  "contact.body_part_hit": "where the contact landed",
  "contact.body_part_used": "what made the contact",
  body_part_used: "what made the contact",
  "contact.made": "whether there was contact",
  contact: "the contact",
  "challenge.studs_showing": "whether studs were showing",
  "challenge.leg_straight": "whether the leg was straight",
  "challenge.lunge": "whether it was a lunge",
  speed_and_force: "the speed and force",
  location: "where it happened",
  challenge_type: "the type of challenge",
  handball: "the handball",
  "handball.touched": "whether the ball touched a hand or arm",
};

export function fieldLabel(f: string): string | null {
  if (f.startsWith("players")) return null; // shirt numbers do not affect the call
  return FIELD[f] ?? f.replace(/^[a-z_]+\./, "").replaceAll("_", " ");
}

/** Readable list of what the video model could not see, without duplicates. */
export function unclearFacts(fields: string[]): string[] {
  return [...new Set(fields.map(fieldLabel).filter((x): x is string => !!x))];
}

const list = (xs: string[]) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs.at(-1)}`);

export interface Deduction {
  points: number; // percentage points taken off, 0 for a cap
  text: string;
}

export function explainAdjustment(raw: string): Deduction {
  const m = raw.match(/^-(\d+(?:\.\d+)?): (.*)$/);
  const points = m ? Math.round(Number(m[1]) * 100) : 0;
  const why = m ? m[2] : raw.replace(/^capped: /, "");
  let text = why.charAt(0).toUpperCase() + why.slice(1) + ".";
  const unsure = why.match(/^video model unsure of (.*)$/);
  const disagreed = why.match(/^a second independent run disagreed on (.*)$/);
  if (unsure) text = `The video model couldn't clearly see ${list(unclearFacts(unsure[1].split(", ")))}.`;
  else if (why === "contact not clearly visible") text = "The contact wasn't clearly visible from the best camera angle.";
  else if (disagreed)
    text = `A second, independent run of the decision came out differently: ${disagreed[1]
      .replace(/(\w+) \((\w+) vs (\w+)\)/g, (_, f, a, b) => `${f} ${a.replaceAll("_", " ")} vs ${b.replaceAll("_", " ")}`)}.`;
  else if (why.startsWith("decision relies on the user's context")) text = "The call relied on the note typed with the clip, not only on the video.";
  return { points, text };
}
