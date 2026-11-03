"use client";

import { useEffect, useRef } from "react";
import FoulIcon, { type IconName } from "./FoulIcons";

type Tone = "red" | "yellow" | "pen" | "none";

/** Kinds of incident and what each call does to a match. Generic examples, not specific games. */
const INCIDENTS: { icon: IconName; what: string; call: string; effect: string; tone: Tone }[] = [
  { icon: "boot", what: "Studs-up slide", call: "Red card", effect: "Down to 10 for the rest of the match", tone: "red" },
  { icon: "goal", what: "Trip in the box", call: "Penalty", effect: "A shot from 11 m with only the keeper to beat", tone: "pen" },
  { icon: "hand", what: "Handball on the line", call: "Red card + penalty", effect: "Goal stopped, player sent off", tone: "red" },
  { icon: "boot", what: "Late tackle", call: "Yellow card", effect: "One more and they're off", tone: "yellow" },
  { icon: "whistle", what: "Last-defender foul", call: "Red card", effect: "Clear goal chance denied", tone: "red" },
  { icon: "shirt", what: "Shirt pull at a corner", call: "Penalty", effect: "Holding in the box", tone: "pen" },
  { icon: "screen", what: "Elbow in a header", call: "Red card", effect: "Spotted on the VAR replay", tone: "red" },
  { icon: "ball", what: "Shoulder to shoulder", call: "Play on", effect: "A fair challenge, no foul", tone: "none" },
  { icon: "whistle", what: "Dive in the box", call: "Yellow card", effect: "Booked for simulation", tone: "yellow" },
  { icon: "hand", what: "Ball hits arm by side", call: "No handball", effect: "Arm in a natural position", tone: "none" },
  { icon: "card", what: "Second booking", call: "Sent off", effect: "Two yellows make a red", tone: "red" },
  { icon: "boot", what: "Studs on the foot only", call: "Yellow card", effect: "Reckless, not dangerous", tone: "yellow" },
];

/** Position in the scene: left/top in %, depth in px (negative = further away), tilt in degrees. */
const SPOTS: { x: number; y: number; z: number; ry: number; rx: number; hideSm?: boolean }[] = [
  { x: 4, y: 10, z: -120, ry: 22, rx: 6 },
  { x: 74, y: 8, z: -60, ry: -24, rx: 4 },
  { x: 58, y: 70, z: 40, ry: -14, rx: -6 },
  { x: 10, y: 64, z: 20, ry: 18, rx: -4 },
  { x: 36, y: 2, z: -420, ry: 6, rx: 10, hideSm: true },
  { x: 84, y: 40, z: -260, ry: -30, rx: 0 },
  { x: -2, y: 38, z: -320, ry: 30, rx: 2, hideSm: true },
  { x: 30, y: 82, z: -200, ry: 10, rx: -10, hideSm: true },
  { x: 62, y: 28, z: -560, ry: -10, rx: 6, hideSm: true },
  { x: 82, y: 76, z: -380, ry: -22, rx: -8 },
  { x: 20, y: 30, z: -640, ry: 14, rx: 4, hideSm: true },
  { x: 46, y: 50, z: -760, ry: 0, rx: 0, hideSm: true },
];

const TONE: Record<Tone, { chip: string; icon: string }> = {
  red: { chip: "bg-red-600 text-white", icon: "text-red-400" },
  yellow: { chip: "bg-yellow-400 text-black", icon: "text-yellow-300" },
  pen: { chip: "bg-white text-black", icon: "text-white" },
  none: { chip: "bg-white/15 text-white", icon: "text-green-300" },
};

/** A field of incident cards floating in 3D; the scene tilts towards the pointer. */
export default function FoulField() {
  const scene = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scene.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const move = (e: PointerEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        el.style.setProperty("--px", ((e.clientX / window.innerWidth) * 2 - 1).toFixed(3));
        el.style.setProperty("--py", ((e.clientY / window.innerHeight) * 2 - 1).toFixed(3));
      });
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => {
      window.removeEventListener("pointermove", move);
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden opacity-45 [perspective:1100px] md:opacity-100">
      <div
        ref={scene}
        className="foul-scene absolute inset-[-6%] [transform-style:preserve-3d]"
      >
        {INCIDENTS.map((it, n) => {
          const s = SPOTS[n];
          const far = s.z < -350;
          return (
            <div
              key={it.what}
              className={`absolute [transform-style:preserve-3d] ${s.hideSm ? "hidden md:block" : ""}`}
              style={{
                left: `${s.x}%`,
                top: `${s.y}%`,
                transform: `translateZ(${s.z}px) rotateY(${s.ry}deg) rotateX(${s.rx}deg)`,
              }}
            >
              <div
                className="foul-float w-52 rounded-2xl border border-white/15 bg-white/[0.07] p-3.5 text-white shadow-2xl shadow-black/50 backdrop-blur-md sm:w-60"
                style={{
                  animationDelay: `${-n * 1.7}s`,
                  animationDuration: `${9 + (n % 4) * 2}s`,
                  opacity: far ? 0.5 : 0.92,
                  filter: far ? "blur(1.2px)" : undefined,
                }}
              >
                <div className="flex items-center gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/10">
                    <FoulIcon name={it.icon} className={`h-6 w-6 ${TONE[it.tone].icon}`} />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{it.what}</p>
                    <span className={`mt-1 inline-block rounded px-1.5 py-0.5 text-[11px] font-bold ${TONE[it.tone].chip}`}>
                      {it.call}
                    </span>
                  </div>
                </div>
                <p className="mt-2.5 text-xs leading-snug text-white/65">{it.effect}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
