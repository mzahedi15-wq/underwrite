"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { Progress } from "@/components/ui/progress";

const steps = [
  {
    id: "fetch",
    label: "Fetching property data",
    desc: "Pulling listing details, photos, and tax records from Zillow",
    duration: 2000,
  },
  {
    id: "comps",
    label: "Pulling STR comps",
    desc: "Querying AirDNA for 90-day comp performance in a 1-mile radius",
    duration: 3000,
  },
  {
    id: "market",
    label: "Analyzing market conditions",
    desc: "Synthesizing regulation data, seasonality trends, and demand drivers",
    duration: 3500,
  },
  {
    id: "model",
    label: "Building financial model",
    desc: "Running 10-year DCF with conservative, base, and optimistic scenarios",
    duration: 2500,
  },
  {
    id: "narrative",
    label: "Writing market narrative",
    desc: "Drafting hyper-local investment thesis with supporting data",
    duration: 3000,
  },
  {
    id: "deck",
    label: "Generating pitch deck",
    desc: "Composing 8-slide investor presentation",
    duration: 2000,
  },
  {
    id: "scope",
    label: "Scoping renovation",
    desc: "Producing STR-optimized line-item renovation scope of work",
    duration: 2500,
  },
  {
    id: "package",
    label: "Assembling package",
    desc: "Compiling all documents and generating PDFs",
    duration: 1500,
  },
];

type StepStatus = "pending" | "running" | "done";

export default function ProcessingPage() {
  const [stepStatuses, setStepStatuses] = useState<Record<string, StepStatus>>(
    Object.fromEntries(steps.map((s) => [s.id, "pending"]))
  );
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);

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
      setDone(true);
    }

    run();
    return () => { cancelled = true; };
  }, []);

  const completedCount = Object.values(stepStatuses).filter((s) => s === "done").length;

  return (
    <div className="p-8 flex gap-8 h-full">
      {/* Left: steps */}
      <div className="flex-1 max-w-lg">
        <div className="mb-8">
          <h1
            style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }}
            className="text-2xl text-[#0D0D0D] mb-1"
          >
            {done ? "Analysis complete" : "Generating analysis…"}
          </h1>
          <p className="text-sm text-[#6B6860]">
            8421 E Chaparral Rd · Scottsdale, AZ 85250
          </p>
        </div>

        {/* Progress bar */}
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

        {/* Steps */}
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
                {/* Icon */}
                <div className="mt-0.5 shrink-0">
                  {status === "done" ? (
                    <CheckCircle2 size={16} className="text-[#16A34A]" />
                  ) : status === "running" ? (
                    <Loader2 size={16} className="text-[#6357A0] animate-spin" />
                  ) : (
                    <Circle size={16} className="text-[#E5E3DE]" />
                  )}
                </div>

                {/* Text */}
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

                {/* Step number */}
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
              href="/reports/demo"
              className="inline-flex items-center gap-2 bg-[#0D0D0D] text-white px-6 py-3 rounded-lg font-medium text-sm hover:bg-[#1a1a1a] transition-colors"
            >
              View full report →
            </a>
          </div>
        )}
      </div>

      {/* Right: property photo panel */}
      <div className="hidden xl:flex w-80 flex-col gap-4">
        <div className="rounded-xl overflow-hidden border border-[#E5E3DE] flex-1 relative">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/images/hero-scottsdale.png"
            alt="Property"
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
          <div className="absolute bottom-4 left-4 right-4">
            <p className="text-white text-xs font-medium mb-0.5">8421 E Chaparral Rd</p>
            <p className="text-white/60 text-xs">Scottsdale, AZ 85250</p>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E5E3DE] p-4">
          <p className="text-xs text-[#6B6860] mb-1">Preliminary verdict</p>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 rounded-full bg-[#16A34A]" />
            <p className="text-sm font-semibold text-[#0D0D0D]">Strong Buy</p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <p className="text-[#6B6860]">List price</p>
              <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="font-medium text-[#0D0D0D]">$749,000</p>
            </div>
            <div>
              <p className="text-[#6B6860]">Est. CoC</p>
              <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="font-medium text-[#16A34A]">14.7%</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
