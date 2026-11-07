import { REPO_URL } from "@/lib/api";

/** Shown instead of the upload tool on a hosted build with no analysis server behind it. */
export default function UploadUnavailable({ embedded = false }: { embedded?: boolean }) {
  const Title = embedded ? "h2" : "h1";
  return (
    <div className="mx-auto w-full max-w-6xl scroll-mt-16 px-4 py-6 sm:px-6 sm:py-16">
      <Title className="text-2xl font-semibold tracking-tight sm:text-3xl">Run it on your own clip</Title>
      <p className="mt-1.5 max-w-xl text-sm text-muted sm:mt-3 sm:text-base">
        This demo shows saved results. Analysing a new clip needs the video server, which isn&apos;t hosted here, but you can run the whole
        tool on your own computer with your own Gemini, Anthropic or OpenAI key.
      </p>
      <a
        href={REPO_URL}
        target="_blank"
        rel="noreferrer"
        className="mt-3 inline-block rounded-lg bg-foreground px-4 py-2.5 sm:mt-5 sm:px-5 sm:py-3 text-sm font-semibold text-background hover:opacity-90"
      >
        Get the code on GitHub ↗
      </a>
    </div>
  );
}
