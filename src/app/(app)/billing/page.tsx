"use client";

import { useEffect, useState } from "react";
import { Check, Zap, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface UserData {
  plan: "FREE" | "STARTER" | "PRO" | "UNLIMITED";
  firstName: string | null;
}

interface UsageData {
  usedThisMonth: number;
  totalEver: number;
}

const PLANS = [
  {
    id: "starter",
    name: "Starter",
    price: 49,
    period: "month",
    limit: "3 analyses / month",
    features: [
      "Full financial model (DCF, CoC, cap rate)",
      "Airbnb + VRBO comp analysis",
      "AI market narrative",
      "Renovation scope of work",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: 99,
    period: "month",
    limit: "10 analyses / month",
    highlight: true,
    features: [
      "Everything in Starter",
      "Investor pitch deck",
      "Sensitivity analysis matrix",
      "Suggested offer price",
      "Priority processing",
    ],
  },
  {
    id: "unlimited",
    name: "Unlimited",
    price: 249,
    period: "month",
    limit: "Unlimited analyses",
    features: [
      "Everything in Pro",
      "Unlimited analyses",
      "API access",
      "White-label reports",
      "Dedicated support",
    ],
  },
];

const PLAN_LIMITS: Record<string, number | null> = {
  FREE: 1,
  STARTER: 3,
  PRO: 10,
  UNLIMITED: null,
};

const PLAN_LABEL: Record<string, string> = {
  FREE: "Free",
  STARTER: "Starter",
  PRO: "Pro",
  UNLIMITED: "Unlimited",
};

export default function BillingPage() {
  const [user, setUser] = useState<UserData | null>(null);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/user").then((r) => r.json()),
      fetch("/api/analyses").then((r) => r.json()),
    ]).then(([userData, analyses]) => {
      setUser(userData);
      const now = new Date();
      const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
      const thisMonth = Array.isArray(analyses)
        ? analyses.filter((a: { createdAt: string }) => new Date(a.createdAt) >= startOfMonth).length
        : 0;
      setUsage({ usedThisMonth: thisMonth, totalEver: Array.isArray(analyses) ? analyses.length : 0 });
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  async function handleUpgrade(planId: string) {
    setCheckingOut(planId);
    try {
      const res = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan: planId }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        alert(data.error || "Billing is not yet configured.");
      }
    } catch {
      alert("Billing is not yet configured.");
    } finally {
      setCheckingOut(null);
    }
  }

  const currentPlanId = user?.plan ?? "FREE";
  const limit = PLAN_LIMITS[currentPlanId];
  const usedPct = limit ? Math.min(((usage?.usedThisMonth ?? 0) / limit) * 100, 100) : 0;

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8">
        <h1
          style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }}
          className="text-2xl text-[#0D0D0D] mb-1"
        >
          Billing
        </h1>
        <p className="text-sm text-[#6B6860]">Manage your plan and usage.</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 size={24} className="animate-spin text-[#6B6860]" />
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {/* Current plan card */}
          <div className="bg-white rounded-xl border border-[#E5E3DE] p-6">
            <div className="flex items-start justify-between mb-5">
              <div>
                <p className="text-xs font-medium text-[#6B6860] uppercase tracking-wider mb-1">Current plan</p>
                <p
                  style={{ fontFamily: "var(--font-outfit)", fontWeight: 800 }}
                  className="text-2xl text-[#0D0D0D]"
                >
                  {PLAN_LABEL[currentPlanId]}
                </p>
              </div>
              {currentPlanId !== "FREE" && (
                <span className="px-3 py-1 rounded-full bg-[#6357A0]/10 text-[#6357A0] text-xs font-semibold">Active</span>
              )}
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#6B6860]">Analyses this month</span>
                <span className="font-medium text-[#0D0D0D]">
                  {usage?.usedThisMonth ?? 0}{limit ? ` / ${limit}` : " (unlimited)"}
                </span>
              </div>
              {limit && (
                <div className="h-1.5 bg-[#E5E3DE] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#6357A0] rounded-full transition-all"
                    style={{ width: `${usedPct}%` }}
                  />
                </div>
              )}
              <p className="text-xs text-[#6B6860]">{usage?.totalEver ?? 0} total analyses all time</p>
            </div>
          </div>

          {/* Plan options */}
          <div>
            <h2 className="text-sm font-semibold text-[#0D0D0D] mb-4">Upgrade your plan</h2>
            <div className="grid grid-cols-3 gap-4">
              {PLANS.map((plan) => {
                const isCurrent = currentPlanId === plan.id.toUpperCase();
                return (
                  <div
                    key={plan.id}
                    className={`rounded-xl border p-5 flex flex-col ${
                      plan.highlight
                        ? "border-[#6357A0] bg-[#6357A0]/5"
                        : "border-[#E5E3DE] bg-white"
                    }`}
                  >
                    {plan.highlight && (
                      <div className="flex items-center gap-1 mb-3">
                        <Zap size={11} className="text-[#6357A0]" />
                        <span className="text-xs font-semibold text-[#6357A0] uppercase tracking-wider">Most popular</span>
                      </div>
                    )}
                    <p className="font-semibold text-[#0D0D0D] mb-1">{plan.name}</p>
                    <div className="flex items-baseline gap-1 mb-1">
                      <span
                        style={{ fontFamily: "var(--font-outfit)", fontWeight: 800 }}
                        className="text-2xl text-[#0D0D0D]"
                      >
                        ${plan.price}
                      </span>
                      <span className="text-xs text-[#6B6860]">/ {plan.period}</span>
                    </div>
                    <p className="text-xs text-[#6B6860] mb-4">{plan.limit}</p>

                    <ul className="flex flex-col gap-2 mb-5 flex-1">
                      {plan.features.map((f) => (
                        <li key={f} className="flex items-start gap-2">
                          <Check size={13} className="text-[#16A34A] mt-0.5 shrink-0" />
                          <span className="text-xs text-[#6B6860]">{f}</span>
                        </li>
                      ))}
                    </ul>

                    <Button
                      size="sm"
                      variant={plan.highlight ? "default" : "outline"}
                      disabled={isCurrent || checkingOut === plan.id}
                      onClick={() => handleUpgrade(plan.id)}
                      className="w-full"
                    >
                      {isCurrent ? "Current plan" : checkingOut === plan.id ? "Redirecting…" : `Upgrade to ${plan.name}`}
                    </Button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Pay per analysis */}
          <div className="bg-[#F0EEE9] rounded-xl border border-[#E5E3DE] p-5 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-[#0D0D0D] mb-0.5">Pay per analysis</p>
              <p className="text-xs text-[#6B6860]">$29 per analysis. No subscription required.</p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleUpgrade("pay_per")}
              disabled={checkingOut === "pay_per"}
            >
              {checkingOut === "pay_per" ? "Redirecting…" : "Buy one"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
