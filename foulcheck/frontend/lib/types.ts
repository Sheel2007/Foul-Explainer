// Mirrors the backend's Pydantic models (foulcheck/decision/schema.py, foulcheck/video/schema.py).

export type Verdict = "foul" | "no_foul" | "handball" | "cannot_determine";
export type Restart = "direct_free_kick" | "indirect_free_kick" | "penalty_kick" | "play_on" | "unknown";
export type Card = "none" | "yellow" | "red";
export type Level = "High" | "Medium" | "Low";

export interface Confidence {
  model_score: number;
  score: number;
  level: Level;
  /** "-0.24: video model unsure of ...", from backend/foulcheck/decision/confidence.py */
  adjustments: string[];
}

export interface Player {
  id: string;
  team: string | null;
  number: string | null;
  role: string | null;
}

export interface Observation {
  contact_time: string | null;
  players: Player[];
  contact: {
    made: boolean | null;
    by: string | null;
    on: string | null;
    body_part_used: string | null;
    body_part_hit: string | null;
  };
  ball_played_first: boolean | null;
  challenge?: { studs_showing: boolean | null; leg_straight: boolean | null; lunge: boolean | null; follow_through: boolean | null };
  challenge_type: string | null;
  speed_and_force: "low" | "medium" | "high" | null;
  handball: { touched: boolean | null; arm_position: string | null; deliberate_movement: boolean | null };
  location: string | null;
  attack_context: string | null;
  view_quality: string | null;
  uncertain_fields: string[];
  summary: string;
}

export interface View {
  contact_time: string;
  kind: "live" | "replay";
  slow_motion: boolean;
  camera: string;
  clarity: "clear" | "partial" | "poor";
}

export interface VideoAnalysis {
  clip: string;
  duration_s: number;
  window: [number, number] | null;
  locate: { incident_found: boolean; incident: string; views: View[]; best_view: number };
}

export interface Citation {
  chunk_id: string;
  law: string;
  section: string;
  title: string;
  subtitle: string;
  page: number;
  reference: string;
  why: string;
  quote: string | null;
  highlight: string | null;
  source_url: string;
  /** "guidance" = Premier League / UEFA referee guidance on applying the Laws; section holds the publisher */
  kind?: "law" | "guidance";
}

export interface Ruling {
  verdict: Verdict;
  offence_type: string | null;
  restart: Restart;
  card: Card;
  confidence: Confidence;
  explanation: string;
  citations: Citation[];
  gray_areas: string[];
  key_moment: string | null;
  edition: string;
  edition_label: string;
  context_hint: string | null;
  used_user_context: boolean;
  observation: Observation | null;
  video: VideoAnalysis | null;
  notes: string[];
  disclaimer: string;
}

export interface JobStatus {
  id: string;
  status: "queued" | "running" | "done" | "error";
  stage: string | null;
  stages: { key: string; label: string }[];
  error: string | null;
  clip_name: string;
  context: string | null;
  has_result: boolean;
  has_video: boolean;
}

/** A test clip shown on the homepage (written by `python -m foulcheck.explain.examples`). */
export interface Example {
  id: string;
  title: string;
  video: string;
  poster: string;
  ai: {
    verdict: Verdict;
    restart: Restart;
    card: Card;
    offence_type: string | null;
    confidence: Level;
    explanation: string;
    key_moment: string | null;
    citations: Pick<Citation, "section" | "title" | "quote" | "highlight" | "source_url" | "kind">[];
    confidence_detail: Pick<Confidence, "model_score" | "score" | "adjustments">;
    gray_areas: string[];
    uncertain_fields: string[];
  };
  facts: {
    challenge_type: string | null;
    body_part_used: string | null;
    body_part_hit: string | null;
    ball_played_first: boolean | null;
    speed_and_force: string | null;
    location: string | null;
    boot_detail: string | null;
    studs_showing: boolean | null;
    leg_straight: boolean | null;
    lunge: boolean | null;
    follow_through: boolean | null;
  } | null;
  label: { verdict: Verdict | null; restart: Restart | null; card: Card | null } | null;
  /** the homepage story clip: raw video plus stills for the pipeline diagram (one clip only) */
  story: {
    video: string;
    duration: number;
    strip: { src: string; seconds: number }[];
    contact: string;
    closeup: string | null;
  } | null;
  moment: {
    contact_seconds: number | null;
    /** [ymin, xmin, ymax, xmax], 0-1000 */
    contact_box: number[] | null;
    views: { seconds: number; kind: "live" | "replay"; slow_motion: boolean; camera: string | null; clarity: string; chosen: boolean }[];
    closeup: boolean;
    audit: Record<string, string | number | boolean | null>;
  };
}
