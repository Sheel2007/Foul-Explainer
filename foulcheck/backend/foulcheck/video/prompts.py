"""Prompts for the video step. They ask for facts only: rulings belong to the decision engine."""

from foulcheck.video.schema import LocateResult, Observation, View, fmt_ts

# Part of the video cache keys. Bump the matching one whenever a prompt below changes meaning.
LOCATE_VERSION = "v1"
INSPECT_VERSION = "v3"  # v2: studs, straight leg, lunge, follow-through; v3: boot_detail and contact_box
CLOSEUP_VERSION = "v1"

NEUTRAL_RULES = """\
Describe only what you can see. Do not judge the incident: never use rule or verdict words
such as "foul", "reckless", "careless", "excessive force", "offence", "illegal", "card",
"booking", "sent off", "penalty kick", "free kick" or "simulation". Naming a place
on the pitch ("penalty area") is fine. If something cannot be seen, use null and say so."""

LOCATE = f"""\
You are a football (soccer) video analyst. This clip shows one incident between players: a
physical challenge or contact, or the ball touching a player's hand or arm. The clip may show
the incident live and then in one or more replays, from different cameras or in slow motion,
and may include broadcast graphics, cutaways and transitions.

1. Decide whether such an incident is shown at all (incident_found).
2. List every time the incident is shown (views), live first, then each replay in order.
   For each view give the exact moment of contact as MM:SS.s on this video's timeline,
   whether it is live or a replay, whether it is slow motion, the camera angle, and how
   clearly the contact itself can be seen.
3. Set best_view to the view that shows the contact most clearly.
4. List the players directly involved (team by shirt colour, shirt number if readable, role).

{NEUTRAL_RULES}"""


def inspect(locate: LocateResult, view: View, start: float, end: float) -> str:
    who = "; ".join(
        f"{p.id}: {p.team or '?'} #{p.number or '?'} {p.role or ''}".strip() for p in locate.players
    ) or "not identified yet"
    return f"""\
You are a football (soccer) video analyst. This is a short window ({fmt_ts(start)} to
{fmt_ts(end)} of the original video) around one incident: {locate.incident}
The window shows the {view.kind}{' slow-motion' if view.slow_motion else ''} view from the
{view.camera}, with contact at about {view.contact_time}. Players involved: {who}.

Watch frame by frame and fill in every field of the JSON schema:
- contact_time: the exact moment of contact, MM:SS.s on the ORIGINAL video timeline (between
  {fmt_ts(start)} and {fmt_ts(end)}).
- Use the player ids above in contact.by / contact.on, and fill players.
- Say exactly which body part made contact and which was hit, whether the ball was played
  before the contact, and the speed and force at contact.
- Look closely at the challenging leg at the moment of contact and fill challenge: was the
  sole/studs of the boot facing the opponent, was the leg straight, did the player lunge, and
  did the leg carry on into the opponent after touching the ball? Name the boot part precisely
  in contact.body_part_used (e.g. "studs/sole", "instep", "outside of foot"), not just "foot".
- If the ball touched a hand or arm, describe the arm position and whether it moved towards
  the ball.
- boot_detail: one sentence on what the challenging boot is doing at contact.
- contact_box: a box around the challenging boot and the opponent's leg at the moment of
  contact, [ymin, xmin, ymax, xmax] scaled 0-1000 (used to zoom in for a close-up).
- location: relative to the penalty area, only if the pitch markings show it.
- Put the name of every field you could not see clearly in uncertain_fields.
- summary: 2-4 sentences with MM:SS.s timestamps.

{NEUTRAL_RULES}"""


def closeup(obs: Observation) -> str:
    by = obs.contact.by or "the challenging player"
    on = obs.contact.on or "the opponent"
    return f"""\
This is a zoomed-in close-up (cropped and enlarged) of the moment of contact, about
{obs.contact_time or "the middle of the clip"}. {obs.challenge_type or "A challenge"} by {by} on {on}.

Look only at the challenging leg and boot, frame by frame, and answer:
- At contact, is the sole/studs of the boot facing the opponent (studs up), or the side of the
  foot, the laces or the toe? Set challenge.studs_showing accordingly.
- Is the leg straight or bent? Did the player lunge? Does the leg carry on into the opponent
  after any touch on the ball?
- Which part of the boot or leg made contact, and which part of the opponent was hit?
- boot_detail: one sentence describing exactly what the boot is doing at contact.
If the close-up is too blurry for a field, use null and list it in uncertain_fields.

{NEUTRAL_RULES}"""


def repair_note(error: str) -> str:
    return f"\n\nYour previous answer was rejected: {error}\nReturn corrected JSON only."
