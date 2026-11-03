"""Hand-written Law 12 tag map, so retrieval of the core rules never depends on embeddings.

Selectors locate chunks by Law, section and sub-heading, with a short key phrase only where a
section holds several rule ideas. They point at chunks; the Law text itself always comes from
the parsed PDF.
"""

import re
from dataclasses import dataclass

from foulcheck.laws.models import Chunk
from foulcheck.video.schema import Observation


@dataclass(frozen=True)
class Sel:
    law: str
    section: str | None = None  # exact, "" for a Law's preamble, None for any
    subtitle: str | None = None  # prefix of the sub-heading, "" for none
    contains: str | None = None  # key phrase, case-insensitive

    def matches(self, c: Chunk) -> bool:
        if c.law != self.law:
            return False
        if self.section is not None and c.section != self.section:
            return False
        if self.subtitle is not None:
            if self.subtitle == "" and c.subtitle:
                return False
            if not c.subtitle.lower().startswith(self.subtitle.lower()):
                return False
        return self.contains is None or self.contains.lower() in c.text.lower()


# Always retrieved: the base terms every foul decision is reasoned from.
DEFINITIONS = "foul_definitions"

TAG_MAP: dict[str, list[Sel]] = {
    DEFINITIONS: [Sel("12", "12.1", "", "reckless is when")],
    "direct_free_kick": [
        Sel("12", "12.1", "", "careless, reckless or using excessive force"),
        Sel("12", "12.1", "", "involves contact"),
    ],
    "holding": [
        Sel("12", "12.1", "", "holds an opponent"),
        Sel("12", "12.4", "Denying a goal", "holding, pulling"),
    ],
    "handball": [
        Sel("12", "12.1", "Handling the ball"),
        Sel("12", "12.1", "", "a handball offence"),
    ],
    "careless": [Sel("12", "12.1", "", "reckless is when")],
    "reckless": [
        Sel("12", "12.1", "", "reckless is when"),
        Sel("12", "12.4", "Cautions for unsporting behaviour"),
    ],
    "excessive_force": [
        Sel("12", "12.1", "", "reckless is when"),
        Sel("12", "12.4", "Serious foul play"),
    ],
    "serious_foul_play": [Sel("12", "12.4", "Serious foul play")],
    "violent_conduct": [Sel("12", "12.4", "Violent conduct")],
    "dangerous_play": [
        Sel("12", "12.2", "Playing in a dangerous manner"),
        Sel("12", "12.2", "", "plays in a dangerous manner"),
    ],
    "impeding": [
        Sel("12", "12.2", "Impeding"),
        Sel("12", "12.2", "", "impedes the progress"),
    ],
    "dogso": [
        Sel("12", "12.4", "Denying a goal"),
        Sel("12", "12.4", "Sending-off offences", "obvious goal-scoring"),
    ],
    "spa": [
        Sel("12", "12.4", "Cautions for unsporting behaviour"),
        Sel("12", "12.4", "Delaying the restart of play to show a card"),
    ],
    "simulation": [Sel("12", "12.4", "Cautions for unsporting behaviour")],
    "caution": [
        Sel("12", "12.4", "", "yellow card communicates"),
        Sel("12", "12.4", "Cautionable offences", "a player is cautioned"),
    ],
    "sending_off": [
        Sel("12", "12.4", "", "yellow card communicates"),
        Sel("12", "12.4", "Sending-off offences", "is sent off"),
    ],
    "advantage": [Sel("12", "12.4", "Advantage")],
    "restart": [Sel("12", "12.5", "", "physical offence")],
    "penalty_kick": [Sel("14", "", "", "penalty kick is awarded if")],
    "free_kick": [Sel("13", "13.1", "", "awarded to the opposing team")],
}

# Official referee guidance (Premier League, UEFA) on how the Laws are applied: it holds the
# specifics the Laws leave to judgement, e.g. which point of contact makes a tackle a red card.
# Here `law` is the publisher and `section` the page slug (see guidance.py).
CONTACT_SEVERITY = "contact_severity"
GUIDANCE_MAP: dict[str, list[Sel]] = {
    CONTACT_SEVERITY: [
        Sel("PL", "serious-foul-play", "Contact"),
        Sel("UEFA", "serious-foul-play", "What referees consider"),
    ],
    "serious_foul_play": [
        Sel("PL", "serious-foul-play", "Contact"),
        Sel("UEFA", "serious-foul-play", "When VAR should recommend a red card"),
    ],
    "excessive_force": [Sel("PL", "serious-foul-play", "Considerations")],
    "dangerous_play": [
        Sel("PL", "high-foot", "Reckless"),
        Sel("PL", "high-foot", "Excessive force"),
    ],
    "violent_conduct": [
        Sel("PL", "violent-conduct", "Considerations"),
        Sel("UEFA", "violent-conduct", "When VAR should recommend a red card"),
    ],
    "dogso": [
        Sel("PL", "dogso"),
        Sel("UEFA", "dogso", "What referees consider"),
    ],
    "handball": [Sel("PL", "handball")],
    "holding": [Sel("PL", "holding")],
    "impeding": [Sel("PL", "blocking", "Considerations")],
}

# Order in which tags are ranked when more chunks match than fit.
TAG_PRIORITY = list(dict.fromkeys([*TAG_MAP, *GUIDANCE_MAP]))


def tag_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Stamp tags from the tag maps onto chunks. Fails loudly if a selector finds nothing (guidance
    selectors only when their page was fetched at all)."""
    pages = {(c.law, c.section) for c in chunks if c.kind == "guidance"}
    maps = [(TAG_MAP, True), (GUIDANCE_MAP, False)]
    for tag_map, required in maps:
        for tag, sels in tag_map.items():
            for sel in sels:
                hits = [c for c in chunks if sel.matches(c)]
                if not hits and (required or (sel.law, sel.section) in pages):
                    raise ValueError(f"Tag map selector for {tag!r} matched no chunk: {sel}")
                _stamp(tag, hits)
    return chunks


def _stamp(tag: str, hits: list[Chunk]) -> None:
    for c in hits:
        if tag not in c.tags:
            c.tags.append(tag)


def _has(text: str | None, *words: str) -> bool:
    return bool(text) and any(re.search(rf"\b{w}", text.lower()) for w in words)


def observation_tags(obs: Observation) -> list[str]:
    """Rule-based mapping from observed facts to the Law topics a referee would consult."""
    tags = [DEFINITIONS]
    c = obs.contact
    challenge = obs.challenge_type
    force = obs.speed_and_force

    if c.made:
        tags += ["direct_free_kick", "restart", "free_kick", CONTACT_SEVERITY]
    elif challenge:
        tags += ["dangerous_play", "impeding"]
    if _has(challenge, "hold", "pull", "grab", "shirt"):
        tags.append("holding")
    if _has(challenge, "strik", "punch", "elbow", "head-butt", "headbutt", "slap", "kick out", "stamp"):
        tags.append("violent_conduct")
    if _has(challenge, "high foot", "high boot", "bicycle", "scissor", "overhead"):
        tags.append("dangerous_play")
    if _has(challenge, "dive", "simulat", "fell without"):
        tags.append("simulation")

    studs = _has(c.body_part_used, "stud", "sole")
    lunge = _has(challenge, "slid", "lunge", "two-foot", "two footed", "two-footed", "jump")
    if c.made or challenge:
        tags.append("careless")
    if force in ("medium", "high") or studs or lunge or obs.ball_played_first is False:
        tags += ["reckless", "caution"]
    d = obs.challenge
    studs = studs or bool(d.studs_showing)
    # Only studs actually seen leading into the opponent point to serious foul play: a straight
    # leading leg or a lunge is part of most slides, so on their own they only point to reckless.
    dangerous = studs
    if d.lunge or d.follow_through:
        tags += ["reckless", "caution"]
    if force == "high" or studs or dangerous or _has(challenge, "two-foot", "two footed", "two-footed"):
        tags += ["excessive_force", "sending_off"]
    if dangerous:
        tags.append("serious_foul_play")

    if obs.handball.touched:
        tags += ["handball", "free_kick"]

    loc = (obs.location or "").lower()
    if "penalty area" in loc and "outside" not in loc:
        tags.append("penalty_kick")
    elif not loc or "unknown" in loc or "location" in obs.uncertain_fields:
        tags += ["penalty_kick", "free_kick"]

    if _has(obs.attack_context, "goal", "last", "one-on-one", "one on one", "clear", "through",
            "breakaway", "counter", "promising", "toward", "towards"):
        tags += ["dogso", "spa", "sending_off", "caution"]

    seen: set[str] = set()
    return [t for t in tags if not (t in seen or seen.add(t))]
