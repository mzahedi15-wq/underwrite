"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { Progress } from "@/components/ui/progress";

const steps = [
  { id: "fetch", label: "Fetching property data", desc: "Pulling listing details from Zillow", duration: 2000 },
  { id: "comps", label: "Pulling STR comps", desc: "Querying comp performance in a 1-mile radius", duration: 3000 },
  { id: "market", label: "Analyzing market conditions", desc: "Synthesizing regulation data and demand drivers", duration: 3500 },
  { id: "model", label: "Building financial model", desc: "Running 10-year DCF with three scenarios", duration: 2500 },
  { id: "narrative", label: "Writing market narrative", desc: "Drafting investment thesis with supporting data", duration: 3000 },
  { id: "deck", label: "Generating pitch deck", desc: "Composing 8-slide investor presentation", duration: 2000 },
  { id: "scope", label: "Scoping renovation", desc: "Producing STR-optimized line-item scope of work", duration: 2500 },
  { id: "package", label: "Assembling package", desc: "Compiling all documents", duration: 1500 },
];

type StepStatus = "pending" | "running" | "done";

export default function ProcessingPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [stepStatuses, setStepStatuses] = useState<Record<string, StepStatus>>(
    Object.fromEntries(steps.map((s) => [s.id, "pending"]))
  );
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);
  const [failed, setFailed] = useState(false);
  const [address, setAddress] = useState<string | null>(null);

  // Animate steps
  useEffect(() => {
    let cancelled = false;
    let elapsed = 0;
    const total = steps.reduce((acc, s) => acc + s.duration, 0);

    async function run() {
      for (const step of steps) {
        if (cancelled) return;
        setStepStatuses((prev) => ({ ...prev, [step.id]: "running" }));
        await new Promise((res) => setTimeout(res, step.duration));
        if (cancelled) return;
        elapsed += step.duration;
        setProgress(Math.round((elapsed / total) * 100));
        setStepStatuses((prev) => ({ ...prev, [step.id]: "done" }));
      }
    }

    run();
    return () => { cancelled = true; };
  }, []);

  // Poll DB for actual status
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/analyses/${id}`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.address) {
          setAddress([data.address, data.city, data.state].filter(Boolean).join(", "));
        }

        if (data.status === "COMPLETE") {
          clearInterval(interval);
          setProgress(100);
          setStepStatuses(Object.fromEntries(steps.map((s) => [s.id, "done"])));
          setDone(true);
          setTimeout(() => router.push(`/reports/${id}`), 1200);
        } else if (data.status === "FAILED") {
          clearInterval(interval);
          setFailed(true);
        }
      } catch {
        // ignore poll errors
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [id, router]);

  const completedCount = Object.values(stepStatuses).filter((s) => s === "done").length;

  return (
    <div className="p-8 flex gap-8 h-full">
      <div className="flex-1 max-w-lg">
        <div className="mb-8">
          <h1
            style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }}
            className="text-2xl text-[#0D0D0D] mb-1"
          >
            {done ? "Analysis complete" : failed ? "Analysis failed" : "Generating analysis…"}
          </h1>
          {address && <p className="text-sm text-[#6B6860]">{address}</p>}
        </div>

        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-[#6B6860]">{completedCount} of {steps.length} steps complete</span>
            <span
              style={{ fontFamily: "var(--font-jetbrains-mono)" }}
              className="text-xs font-medium text-[#0D0D0D]"
            >
              {progress}%
            </span>
          </div>
          <Progress value={progress} />
        </div>

        <div className="flex flex-col gap-1">
          {steps.map((step, i) => {
            const status = stepStatuses[step.id];
            return (
              <div
                key={step.id}
                className={`flex items-start gap-3 rounded-lg px-3 py-3 transition-colors ${
                  status === "running" ? "bg-white border border-[#E5E3DE]" : ""
                }`}
              >
                <div className="mt-0.5 shrink-0">
                  {status === "done" ? (
                    <CheckCircle2 size={16} className="text-[#16A34A]" />
                  ) : status === "running" ? (
                    <Loader2 size={16} className="text-[#6357A0] animate-spin" />
                  ) : (
                    <Circle size={16} className="text-[#E5E3DE]" />
                  )}
                </div>
                <div>
                  <p className={`text-sm font-medium ${
                    status === "done" ? "text-[#6B6860] line-through" :
                    status === "running" ? "text-[#0D0D0D]" : "text-[#6B6860]"
                  }`}>
                    {step.label}
                  </p>
                  {status === "running" && (
                    <p className="text-xs text-[#6B6860] mt-0.5">{step.desc}</p>
                  )}
                </div>
                <span className="ml-auto text-xs text-[#E5E3DE] font-mono shrink-0">
                  {String(i + 1).padStart(2, "0")}
                </span>
              </div>
            );
          })}
        </div>

        {done && (
          <div className="mt-6">
            <a
              href={`/reports/${id}`}
              className="inline-flex items-center gap-2 bg-[#0D0D0D] text-white px-6 py-3 rounded-lg font-medium text-sm hover:bg-[#1a1a1a] transition-colors"
            >
              View full report →
            </a>
          </div>
        )}

        {failed && (
          <div className="mt-6 p-4 bg-red-50 rounded-lg border border-red-200">
            <p className="text-sm text-red-700">
              The analysis failed to complete. Please try submitting the property URL again.
            </p>
          </div>
        )}
      </div>

      {/* Right: placeholder panel while processing */}
      <div className="hidden xl:flex w-80 flex-col gap-4">
        <div className="rounded-xl overflow-hidden border border-[#E5E3DE] flex-1 relative bg-[#F0EEE9] flex items-center justify-center">
          <Loader2 size={32} className="text-[#E5E3DE] animate-spin" />
        </div>
      </div>
    </div>
  );
}
