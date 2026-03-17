"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PlusCircle, ArrowRight, TrendingUp, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatPercent } from "@/lib/utils";

interface Analysis {
  id: string;
  address: string | null;
  city: string | null;
  state: string | null;
  listPrice: number | null;
  beds: number | null;
  verdict: string | null;
  projRevenue: number | null;
  cocReturn: number | null;
  occupancy: number | null;
  status: string;
  createdAt: string;
}

const verdictVariant: Record<string, "strong-buy" | "buy" | "hold" | "pass"> = {
  STRONG_BUY: "strong-buy",
  BUY: "buy",
  HOLD: "hold",
  PASS: "pass",
};

const verdictLabel: Record<string, string> = {
  STRONG_BUY: "Strong Buy",
  BUY: "Buy",
  HOLD: "Hold",
  PASS: "Pass",
};

const verdictColor: Record<string, string> = {
  STRONG_BUY: "bg-[#16A34A]",
  BUY: "bg-[#65A30D]",
  HOLD: "bg-[#D97706]",
  PASS: "bg-[#DC2626]",
};

export default function DashboardPage() {
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [firstName, setFirstName] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/analyses").then((r) => r.json()),
      fetch("/api/user").then((r) => r.json()),
    ]).then(([analysesData, userData]) => {
      setAnalyses(Array.isArray(analysesData) ? analysesData : []);
      setFirstName(userData.firstName ?? null);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const complete = analyses.filter((a) => a.status === "COMPLETE");
  const recent = complete.slice(0, 6);

  const now = new Date();
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const thisMonth = analyses.filter((a) => new Date(a.createdAt) >= startOfMonth).length;

  const cocValues = complete.filter((a) => a.cocReturn != null).map((a) => a.cocReturn as number);
  const avgCoc = cocValues.length > 0 ? cocValues.reduce((s, v) => s + v, 0) / cocValues.length : null;

  const bestOccupancy = complete.reduce<Analysis | null>((best, a) => {
    if (a.occupancy == null) return best;
    if (!best || (best.occupancy ?? 0) < a.occupancy) return a;
    return best;
  }, null);

  const stats = [
    { label: "Total analyses", value: loading ? "—" : String(analyses.length), sub: "all time" },
    {
      label: "Avg. CoC return",
      value: loading ? "—" : avgCoc != null ? formatPercent(avgCoc) : "—",
      sub: "completed analyses",
      positive: avgCoc != null && avgCoc > 0,
    },
    {
      label: "Top occupancy",
      value: loading ? "—" : bestOccupancy?.occupancy != null ? formatPercent(bestOccupancy.occupancy) : "—",
      sub: bestOccupancy ? (bestOccupancy.city || bestOccupancy.address || "—") : "no data yet",
    },
    { label: "This month", value: loading ? "—" : String(thisMonth), sub: `${thisMonth === 1 ? "analysis" : "analyses"} run` },
  ];

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1
            style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }}
            className="text-2xl text-[#0D0D0D]"
          >
            Dashboard
          </h1>
          <p className="text-sm text-[#6B6860] mt-0.5">
            {firstName ? `Welcome back, ${firstName}.` : "Welcome back."}
          </p>
        </div>
        <Link href="/new">
          <Button size="lg" className="gap-2">
            <PlusCircle size={15} />
            New analysis
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {stats.map(({ label, value, sub, positive }) => (
          <div key={label} className="bg-white rounded-xl border border-[#E5E3DE] p-5">
            <p className="text-xs text-[#6B6860] mb-2">{label}</p>
            <p
              style={{ fontFamily: "var(--font-outfit)", fontWeight: 800 }}
              className={`text-2xl mb-1 ${positive ? "text-[#16A34A]" : "text-[#0D0D0D]"}`}
            >
              {value}
            </p>
            <p className="text-xs text-[#6B6860]">{sub}</p>
          </div>
        ))}
      </div>

      {/* Recent */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-[#0D0D0D]">Recent analyses</h2>
        {complete.length > 6 && (
          <Link href="/reports" className="text-xs text-[#6B6860] hover:text-[#0D0D0D] flex items-center gap-1">
            View all <ArrowRight size={12} />
          </Link>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 size={24} className="animate-spin text-[#6B6860]" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {recent.map((a) => (
            <Link key={a.id} href={`/reports/${a.id}`}>
              <div className="bg-white rounded-xl border border-[#E5E3DE] overflow-hidden hover:shadow-md transition-shadow cursor-pointer group">
                <div className={`h-1.5 ${verdictColor[a.verdict ?? ""] ?? "bg-[#E5E3DE]"}`} />
                <div className="p-5">
                  <div className="flex items-start justify-between gap-2 mb-4">
                    <div className="min-w-0">
                      <p className="font-semibold text-sm text-[#0D0D0D] truncate">{a.address || "—"}</p>
                      <p className="text-xs text-[#6B6860] truncate">
                        {[a.city, a.state].filter(Boolean).join(", ") || "—"}
                      </p>
                    </div>
                    {a.verdict && (
                      <Badge variant={verdictVariant[a.verdict] ?? "hold"} className="shrink-0 text-xs">
                        {verdictLabel[a.verdict] ?? a.verdict}
                      </Badge>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-xs text-[#6B6860]">Annual revenue</p>
                      <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-sm font-semibold text-[#0D0D0D]">
                        {a.projRevenue != null ? formatCurrency(a.projRevenue) : "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-[#6B6860]">CoC return</p>
                      <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-sm font-semibold text-[#16A34A]">
                        {a.cocReturn != null ? formatPercent(a.cocReturn) : "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-[#6B6860]">List price</p>
                      <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-sm font-semibold text-[#0D0D0D]">
                        {a.listPrice != null ? formatCurrency(a.listPrice) : "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-[#6B6860]">Occupancy</p>
                      <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-sm font-semibold text-[#0D0D0D]">
                        {a.occupancy != null ? formatPercent(a.occupancy) : "—"}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-[#E5E3DE] flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <TrendingUp size={12} className="text-[#16A34A]" />
                      <span className="text-xs text-[#6B6860]">
                        {new Date(a.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                      </span>
                    </div>
                    <span className="text-xs text-[#6357A0] font-medium group-hover:underline">View report →</span>
                  </div>
                </div>
              </div>
            </Link>
          ))}

          <Link href="/new">
            <div className="bg-[#F0EEE9] rounded-xl border border-dashed border-[#E5E3DE] min-h-[220px] flex flex-col items-center justify-center gap-3 hover:bg-[#EAE8E2] transition-colors cursor-pointer group">
              <div className="w-10 h-10 rounded-full bg-[#E5E3DE] flex items-center justify-center group-hover:bg-[#D4D2CB] transition-colors">
                <PlusCircle size={18} className="text-[#6B6860]" />
              </div>
              <p className="text-sm font-medium text-[#6B6860]">New analysis</p>
              <p className="text-xs text-[#6B6860]/60">Paste any Zillow or Redfin URL</p>
            </div>
          </Link>
        </div>
      )}
    </div>
  );
}
