import type { Metadata } from "next";
import FoulExplainer from "@/components/FoulExplainer";
import UploadUnavailable from "@/components/UploadUnavailable";
import { HAS_ANALYSIS_SERVER } from "@/lib/api";

export const metadata: Metadata = { title: "Try it · Foul Explainer" };

export default function TryPage() {
  return HAS_ANALYSIS_SERVER ? <FoulExplainer /> : <UploadUnavailable />;
}
