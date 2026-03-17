"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PlusCircle, Loader2, AlertCircle, ArrowUpRight } from "lucide-react";
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
  baths: number | null;
  verdict: string | null;
  projRevenue: number | null;
  cocReturn: number | null;
  capRate: number | null;
  occupancy: number | null;
  status: string;
  propertyType: string | null;
  strategy: string | null;
  createdAt: string;
}

const statusLabel: Record<string, string> = {
  PENDING: "Queued",
  PROCESSING: "Processing",
  COMPLETE: "Complete",
  FAILED: "Failed",
};

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

export default function MyReportsPage() {
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/analyses")
      .then((r) => r.json())
      .then((data) => { setAnalyses(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const complete = analyses.filter((a) => a.status === "COMPLETE");
  const inProgress = analyses.filter((a) => a.status === "PENDING" || a.status === "PROCESSING");
  const failed = analyses.filter((a) => a.status === "FAILED");

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1
            style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }}
            className="text-2xl text-[#0D0D0D]"
          >
            My Reports
          </h1>
          <p className="text-sm text-[#6B6860] mt-0.5">
            {loading ? "Loading…" : `${analyses.length} total ${analyses.length === 1 ? "analysis" : "analyses"}`}
          </p>
        </div>
        <Link href="/new">
          <Button size="lg" className="gap-2">
            <PlusCircle size={15} />
            New analysis
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 size={24} className="animate-spin text-[#6B6860]" />
        </div>
      ) : analyses.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <div className="w-12 h-12 rounded-full bg-[#F0EEE9] flex items-center justify-center">
            <PlusCircle size={20} className="text-[#6B6860]" />
          </div>
          <p className="text-sm font-medium text-[#0D0D0D]">No analyses yet</p>
          <p className="text-xs text-[#6B6860]">Paste a Zillow or Redfin URL to get started</p>
          <Link href="/new">
            <Button size="lg" className="mt-2">Start your first analysis</Button>
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {/* In progress */}
          {inProgress.length > 0 && (
            <section>
              <h2 className="text-xs font-medium text-[#6B6860] uppercase tracking-wider mb-3">
                In progress
              </h2>
              <div className="flex flex-col gap-2">
                {inProgress.map((a) => (
                  <Link key={a.id} href={`/processing/${a.id}`}>
                    <div className="bg-white border border-[#E5E3DE] rounded-xl px-5 py-4 flex items-center gap-4 hover:shadow-sm transition-shadow">
                      <div className="w-2 h-2 rounded-full bg-[#6357A0] animate-pulse shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-[#0D0D0D] truncate">
                          {a.address || a.id}
                        </p>
                        <p className="text-xs text-[#6B6860]">{a.status === "PROCESSING" ? "Processing…" : "Queued"}</p>
                      </div>
                      <span className="text-xs text-[#6357A0] font-medium shrink-0">View status →</span>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* Complete */}
          {complete.length > 0 && (
            <section>
              <h2 className="text-xs font-medium text-[#6B6860] uppercase tracking-wider mb-3">
                Completed
              </h2>
              <div className="bg-white border border-[#E5E3DE] rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#E5E3DE]">
                      {["Property", "Verdict", "Revenue", "CoC", "Cap Rate", "Occupancy", ""].map((h) => (
                        <th key={h} className="text-left px-5 py-3 text-xs font-medium text-[#6B6860] uppercase tracking-wider">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {complete.map((a, i) => (
                      <tr
                        key={a.id}
                        className={`${i < complete.length - 1 ? "border-b border-[#E5E3DE]" : ""} hover:bg-[#F7F6F3] transition-colors`}
                      >
                        <td className="px-5 py-4">
                          <p className="font-medium text-[#0D0D0D]">{a.address || "—"}</p>
                          <p className="text-xs text-[#6B6860]">{[a.city, a.state].filter(Boolean).join(", ") || a.propertyType || "—"}</p>
                        </td>
                        <td className="px-5 py-4">
                          {a.verdict ? (
                            <Badge variant={verdictVariant[a.verdict] ?? "hold"}>
                              {verdictLabel[a.verdict] ?? a.verdict}
                            </Badge>
                          ) : "—"}
                        </td>
                        <td className="px-5 py-4 font-mono text-sm">
                          {a.projRevenue != null ? formatCurrency(a.projRevenue) : "—"}
                        </td>
                        <td className="px-5 py-4 font-mono text-sm text-[#16A34A]">
                          {a.cocReturn != null ? formatPercent(a.cocReturn) : "—"}
                        </td>
                        <td className="px-5 py-4 font-mono text-sm">
                          {a.capRate != null ? formatPercent(a.capRate) : "—"}
                        </td>
                        <td className="px-5 py-4 font-mono text-sm">
                          {a.occupancy != null ? formatPercent(a.occupancy) : "—"}
                        </td>
                        <td className="px-5 py-4">
                          <Link href={`/reports/${a.id}`} className="inline-flex items-center gap-1 text-xs text-[#6357A0] font-medium hover:underline">
                            View <ArrowUpRight size={12} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Failed */}
          {failed.length > 0 && (
            <section>
              <h2 className="text-xs font-medium text-[#6B6860] uppercase tracking-wider mb-3">
                Failed
              </h2>
              <div className="flex flex-col gap-2">
                {failed.map((a) => (
                  <div key={a.id} className="bg-white border border-[#E5E3DE] rounded-xl px-5 py-4 flex items-center gap-4">
                    <AlertCircle size={16} className="text-red-500 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[#0D0D0D] truncate">{a.address || a.id}</p>
                      <p className="text-xs text-[#6B6860]">Analysis failed — try resubmitting the URL</p>
                    </div>
                    <Link href="/new">
                      <Button size="sm" variant="outline">Retry</Button>
                    </Link>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
