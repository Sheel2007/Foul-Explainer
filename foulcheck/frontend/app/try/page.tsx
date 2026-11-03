import type { Metadata } from "next";
import FoulExplainer from "@/components/FoulExplainer";

export const metadata: Metadata = { title: "Try it · Foul Explainer" };

export default function TryPage() {
  return <FoulExplainer />;
}
