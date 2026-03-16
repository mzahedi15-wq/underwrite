"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Link2, ArrowRight, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const packageItems = [
  { label: "Financial model", desc: "IRR, CoC return, NOI, cap rate — full 10-year projection" },
  { label: "Market narrative", desc: "Hyper-local STR market analysis with comp data" },
  { label: "Investor pitch deck", desc: "8-slide presentation ready to share with partners" },
  { label: "Renovation scope", desc: "Line-item SOW calibrated for STR optimization" },
];

const propertyTypes = ["Single Family", "Condo", "Multi-Family", "Cabin / Retreat", "Townhouse"];
const investStrategies = ["Buy & Hold STR", "Fix & Flip to STR", "New Construction STR", "Convert LTR to STR"];

export default function NewAnalysisPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [propType, setPropType] = useState("Single Family");
  const [strategy, setStrategy] = useState("Buy & Hold STR");
  const [targetRenovation, setTargetRenovation] = useState("");
  const [notes, setNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/analyses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          propertyUrl: url,
          propertyType: propType,
          strategy,
          renovationBudget: targetRenovation || null,
          notes: notes || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong. Please try again.");
        setSubmitting(false);
        return;
      }
      router.push(`/processing/${data.id}`);
    } catch {
      setError("Network error. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      {/* Header */}
      <div className="mb-8">
        <h1
          style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }}
          className="text-2xl text-[#0D0D0D] mb-1"
        >
          New analysis
        </h1>
        <p className="text-sm text-[#6B6860]">
          Paste a Zillow or Redfin listing URL to generate a full STR investment package.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        {/* URL input */}
        <div className="bg-white rounded-xl border border-[#E5E3DE] p-5">
          <label className="block text-sm font-semibold text-[#0D0D0D] mb-1">Property URL</label>
          <p className="text-xs text-[#6B6860] mb-3">Zillow and Redfin listings supported</p>
          <div className="relative">
            <Link2 size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6B6860]" />
            <Input
              type="url"
              placeholder="https://www.zillow.com/homedetails/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="pl-9"
              required
            />
          </div>
        </div>

        {/* Configuration */}
        <div className="bg-white rounded-xl border border-[#E5E3DE] p-5">
          <h2 className="text-sm font-semibold text-[#0D0D0D] mb-4">Configuration</h2>

          <div className="flex flex-col gap-5">
            {/* Property type */}
            <div>
              <label className="block text-xs font-medium text-[#6B6860] uppercase tracking-wider mb-2">
                Property type
              </label>
              <div className="flex flex-wrap gap-2">
                {propertyTypes.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setPropType(t)}
                    className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                      propType === t
                        ? "bg-[#0D0D0D] text-white border-[#0D0D0D]"
                        : "bg-white text-[#6B6860] border-[#E5E3DE] hover:border-[#0D0D0D] hover:text-[#0D0D0D]"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Investment strategy */}
            <div>
              <label className="block text-xs font-medium text-[#6B6860] uppercase tracking-wider mb-2">
                Investment strategy
              </label>
              <div className="flex flex-wrap gap-2">
                {investStrategies.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setStrategy(s)}
                    className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                      strategy === s
                        ? "bg-[#0D0D0D] text-white border-[#0D0D0D]"
                        : "bg-white text-[#6B6860] border-[#E5E3DE] hover:border-[#0D0D0D] hover:text-[#0D0D0D]"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Renovation budget */}
            <div>
              <label className="block text-xs font-medium text-[#6B6860] uppercase tracking-wider mb-2">
                Renovation budget (optional)
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-[#6B6860]">$</span>
                <Input
                  type="number"
                  placeholder="e.g. 45,000"
                  value={targetRenovation}
                  onChange={(e) => setTargetRenovation(e.target.value)}
                  className="pl-7"
                />
              </div>
            </div>

            {/* Notes */}
            <div>
              <label className="block text-xs font-medium text-[#6B6860] uppercase tracking-wider mb-2">
                Additional notes (optional)
              </label>
              <textarea
                rows={3}
                placeholder="e.g. Prioritize pool addition ROI, assume 10% down payment..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full rounded-lg border border-[#E5E3DE] bg-white px-3 py-2 text-sm text-[#0D0D0D] placeholder:text-[#6B6860] focus:outline-none focus:ring-2 focus:ring-[#6357A0] focus:border-transparent resize-none"
              />
            </div>
          </div>
        </div>

        {/* What you'll get */}
        <div className="bg-[#F0EEE9] rounded-xl border border-[#E5E3DE] p-5">
          <div className="flex items-center gap-2 mb-3">
            <Info size={13} className="text-[#6B6860]" />
            <h3 className="text-xs font-medium text-[#6B6860] uppercase tracking-wider">What you&apos;ll receive</h3>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {packageItems.map(({ label, desc }) => (
              <div key={label} className="flex gap-2.5">
                <div className="w-4 h-4 rounded-full bg-[#16A34A]/15 flex items-center justify-center shrink-0 mt-0.5">
                  <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                    <path d="M1.5 4l1.5 1.5 3.5-3.5" stroke="#16A34A" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <div>
                  <p className="text-xs font-semibold text-[#0D0D0D]">{label}</p>
                  <p className="text-xs text-[#6B6860]">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">{error}</p>
        )}

        {/* Submit */}
        <div className="flex items-center justify-between">
          <p className="text-xs text-[#6B6860]">Est. 12–18 minutes to complete</p>
          <Button type="submit" size="lg" className="gap-2" disabled={submitting}>
            {submitting ? "Starting…" : "Start analysis"} <ArrowRight size={16} />
          </Button>
        </div>
      </form>
    </div>
  );
}
