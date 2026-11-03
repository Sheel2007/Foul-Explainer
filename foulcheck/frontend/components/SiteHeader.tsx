import Link from "next/link";

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-black/80 text-white backdrop-blur">
      <nav className="mx-auto flex w-full max-w-6xl items-center gap-5 px-4 py-3 sm:px-6">
        <Link href="/" className="mr-auto font-semibold tracking-tight">
          Foul Explainer
        </Link>
        <Link href="/#how" className="hidden text-sm text-white/70 hover:text-white sm:inline">How it works</Link>
        <Link href="/#examples" className="text-sm text-white/70 hover:text-white">Examples</Link>
        <Link href="/#try" className="rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-black hover:bg-white/90">
          Try it
        </Link>
      </nav>
    </header>
  );
}
