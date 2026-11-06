import { REPO_URL } from "@/lib/api";

/** Shown instead of the upload tool on a hosted build with no analysis server behind it. */
export default function UploadUnavailable({ embedded = false }: { embedded?: boolean }) {
  const Title = embedded ? "h2" : "h1";
  return (
    <div className="mx-auto w-full max-w-6xl scroll-mt-16 px-4 py-16 sm:px-6">
      <Title className="text-3xl font-semibold tracking-tight">Run it on your own clip</Title>
      <p className="mt-3 max-w-xl text-muted">
        This demo shows saved results. Analysing a new clip needs the video server, which isn&apos;t hosted here, but you can run the whole
        tool on your own computer with a free Gemini key.
      </p>
      <a
        href={REPO_URL}
        target="_blank"
        rel="noreferrer"
        className="mt-5 inline-block rounded-lg bg-foreground px-5 py-3 text-sm font-semibold text-background hover:opacity-90"
      >
        Get the code on GitHub ↗
      </a>
    </div>
  );
}
