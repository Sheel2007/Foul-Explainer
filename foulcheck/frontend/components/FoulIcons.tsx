/** Simple line pictograms for the incidents floating in the hero. 24x24, stroke = currentColor. */

export type IconName = "boot" | "card" | "hand" | "whistle" | "shirt" | "screen" | "ball" | "goal";

const PATHS: Record<IconName, React.ReactNode> = {
  boot: (
    <>
      <path d="M5 4h5v7l7 2.5c1.8.6 3 2 3 3.5v1H4.5L5 4Z" />
      <path d="M4.5 18v2M9 18v2M13.5 18v2M18 18v2" />
      <path d="M10 8h2" />
    </>
  ),
  card: <rect x="7" y="3.5" width="10" height="15" rx="1.5" transform="rotate(8 12 11)" />,
  hand: (
    <>
      <path d="M8 13V6.5a1.5 1.5 0 0 1 3 0V11" />
      <path d="M11 10V4.5a1.5 1.5 0 0 1 3 0V11" />
      <path d="M14 10.5V6a1.5 1.5 0 0 1 3 0v7c0 4-2.5 7-6 7-2.6 0-4-1.4-5.4-3.6L4 13.6a1.5 1.5 0 0 1 2.4-1.7L8 13.5" />
    </>
  ),
  whistle: (
    <>
      <circle cx="9" cy="14" r="5" />
      <path d="M12.5 10.5 20 7v4l-6 2.5" />
      <path d="M4 6l2 2M8 4v2.5" />
    </>
  ),
  shirt: <path d="M8 3 3 6l2 4 2.5-1V21h9V9l2.5 1 2-4-5-3c-.5 1.5-2 2.5-4 2.5S8.5 4.5 8 3Z" />,
  screen: (
    <>
      <rect x="3" y="4" width="18" height="12" rx="1.5" />
      <path d="m10.5 7.5 4 2.5-4 2.5v-5ZM8 20h8M12 16v4" />
    </>
  ),
  ball: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m12 8 3 2.2-1.1 3.5h-3.8L9 10.2 12 8ZM12 8V3.5M15 10.2l4.3-1.4M13.9 13.7l2.6 3.6M10.1 13.7l-2.6 3.6M9 10.2 4.7 8.8" />
    </>
  ),
  goal: (
    <>
      <path d="M3 18V7h18v11" />
      <path d="M3 7l3 3h12l3-3M6 10v8M18 10v8M9 10v8M12 10v8M15 10v8" />
      <circle cx="12" cy="20.5" r=".8" />
    </>
  ),
};

export default function FoulIcon({ name, className }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={className}
    >
      {PATHS[name]}
    </svg>
  );
}
