"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Download,
  Share2,
  FileText,
  BarChart3,
  Presentation,
  Hammer,
  Database,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { formatCurrency, formatPercent } from "@/lib/utils";

interface FinancialModel {
  gross_revenue_base: number;
  gross_revenue_conservative: number;
  gross_revenue_optimistic: number;
  operating_expenses_base: number;
  operating_expenses_conservative: number;
  operating_expenses_optimistic: number;
  noi_base: number;
  noi_conservative: number;
  noi_optimistic: number;
  coc_return_base: number;
  coc_return_conservative: number;
  coc_return_optimistic: number;
  cap_rate_base: number;
  cap_rate_conservative: number;
  cap_rate_optimistic: number;
  irr_base: number;
  irr_conservative: number;
  irr_optimistic: number;
  adr_base: number;
  adr_conservative: number;
  adr_optimistic: number;
  occupancy_base: number;
  occupancy_conservative: number;
  occupancy_optimistic: number;
  breakeven_occupancy: number;
  down_payment_assumed: number;
  mortgage_rate_assumed: number;
  mortgage_payment_monthly: number;
  assumptions: string;
}

interface RenoItem {
  category: string;
  item: string;
  estimated_cost: number;
  roi_impact: "high" | "medium" | "low";
  notes: string;
}

interface ReportJson {
  financialModel: FinancialModel;
  marketNarrative: string;
  pitchDeck: Array<{
    slide: number;
    title: string;
    headline: string;
    bullets: string[];
    callout: string | null;
  }>;
  renovationScope: RenoItem[];
  comps: Record<string, unknown>;
  property: Record<string, unknown>;
}

interface Analysis {
  id: string;
  address: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  listPrice: number | null;
  beds: number | null;
  baths: number | null;
  sqft: number | null;
  verdict: string | null;
  projRevenue: number | null;
  cocReturn: number | null;
  capRate: number | null;
  irr: number | null;
  occupancy: number | null;
  noi: number | null;
  adr: number | null;
  status: string;
  reportJson: ReportJson | null;
}

const fmt$ = (v: number | null) => (v != null ? formatCurrency(v) : "—");
const fmtPct = (v: number | null) => (v != null ? formatPercent(v) : "—");

export default function ReportViewerPage() {
  const { id } = useParams<{ id: string }>();
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("report");

  useEffect(() => {
    fetch(`/api/analyses/${id}`)
      .then((r) => r.json())
      .then((data) => { setAnalysis(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-[#6B6860]" />
      </div>
    );
  }

  if (!analysis || !analysis.reportJson) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-[#6B6860]">
          {analysis?.status === "FAILED"
            ? "Analysis failed. Please try again."
            : "Analysis not yet complete. Please check back shortly."}
        </p>
      </div>
    );
  }

  const fm = analysis.reportJson.financialModel;
  const locationStr = [analysis.city, analysis.state].filter(Boolean).join(", ");
  const verdictLabel: Record<string, string> = {
    STRONG_BUY: "Strong Buy", BUY: "Buy", HOLD: "Hold", PASS: "Pass",
  };
  const verdictVariant: Record<string, "strong-buy" | "green" | "accent" | "default"> = {
    STRONG_BUY: "strong-buy", BUY: "green", HOLD: "accent", PASS: "default",
  };

  const financialRows = [
    { label: "Gross Revenue (Y1)", base: fmt$(fm.gross_revenue_base), conservative: fmt$(fm.gross_revenue_conservative), optimistic: fmt$(fm.gross_revenue_optimistic) },
    { label: "Operating Expenses", base: fmt$(fm.operating_expenses_base), conservative: fmt$(fm.operating_expenses_conservative), optimistic: fmt$(fm.operating_expenses_optimistic) },
    { label: "Net Operating Income", base: fmt$(fm.noi_base), conservative: fmt$(fm.noi_conservative), optimistic: fmt$(fm.noi_optimistic) },
    { label: "Cash-on-Cash Return", base: fmtPct(fm.coc_return_base), conservative: fmtPct(fm.coc_return_conservative), optimistic: fmtPct(fm.coc_return_optimistic) },
    { label: "Cap Rate", base: fmtPct(fm.cap_rate_base), conservative: fmtPct(fm.cap_rate_conservative), optimistic: fmtPct(fm.cap_rate_optimistic) },
    { label: "IRR (10-yr)", base: fmtPct(fm.irr_base), conservative: fmtPct(fm.irr_conservative), optimistic: fmtPct(fm.irr_optimistic) },
    { label: "Avg. Nightly Rate", base: `$${fm.adr_base}`, conservative: `$${fm.adr_conservative}`, optimistic: `$${fm.adr_optimistic}` },
    { label: "Annual Occupancy", base: fmtPct(fm.occupancy_base), conservative: fmtPct(fm.occupancy_conservative), optimistic: fmtPct(fm.occupancy_optimistic) },
    { label: "Break-even Occupancy", base: fmtPct(fm.breakeven_occupancy), conservative: "—", optimistic: "—" },
  ];

  const renoItems = analysis.reportJson.renovationScope ?? [];
  const renoTotal = renoItems.reduce((sum, item) => sum + (item.estimated_cost ?? 0), 0);

  return (
    <div className="flex h-full">
      {/* Left: tabbed content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-[#E5E3DE] bg-[#F7F6F3]">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <Badge variant={verdictVariant[analysis.verdict ?? ""] ?? "default"} className="text-xs">
                ↑ {verdictLabel[analysis.verdict ?? ""] ?? analysis.verdict}
              </Badge>
            </div>
            <h1
              style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }}
              className="text-xl text-[#0D0D0D]"
            >
              {analysis.address}
            </h1>
            <p className="text-sm text-[#6B6860]">{locationStr}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-1.5">
              <Share2 size={13} /> Share
            </Button>
            <Button size="sm" className="gap-1.5">
              <Download size={13} /> Download PDF
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <div className="px-6 bg-[#F7F6F3]">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="report"><FileText size={13} />Report</TabsTrigger>
              <TabsTrigger value="financial"><BarChart3 size={13} />Financial Model</TabsTrigger>
              <TabsTrigger value="deck"><Presentation size={13} />Pitch Deck</TabsTrigger>
              <TabsTrigger value="scope"><Hammer size={13} />Reno Scope</TabsTrigger>
              <TabsTrigger value="raw"><Database size={13} />Raw Data</TabsTrigger>
            </TabsList>

            <div className="overflow-y-auto" style={{ height: "calc(100vh - 220px)" }}>
              {/* ─── Report Tab ─── */}
              <TabsContent value="report">
                <div className="py-6 max-w-2xl">
                  <div className="grid grid-cols-3 gap-3 mb-8">
                    {[
                      { label: "Annual Revenue", value: fmt$(analysis.projRevenue), color: "#0D0D0D" },
                      { label: "Cash-on-Cash", value: fmtPct(analysis.cocReturn), color: "#16A34A" },
                      { label: "Cap Rate", value: fmtPct(analysis.capRate), color: "#0D0D0D" },
                      { label: "10-yr IRR", value: fmtPct(analysis.irr), color: "#16A34A" },
                      { label: "Occupancy", value: fmtPct(analysis.occupancy), color: "#0D0D0D" },
                      { label: "List Price", value: fmt$(analysis.listPrice), color: "#0D0D0D" },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="bg-white rounded-xl border border-[#E5E3DE] p-4">
                        <p className="text-xs text-[#6B6860] mb-1">{label}</p>
                        <p style={{ fontFamily: "var(--font-jetbrains-mono)", color }} className="text-xl font-semibold">
                          {value}
                        </p>
                      </div>
                    ))}
                  </div>

                  <div className="mb-6">
                    <h2 className="font-semibold text-sm text-[#0D0D0D] mb-3">Investment Thesis</h2>
                    <div className="text-sm text-[#6B6860] leading-relaxed space-y-3">
                      {analysis.reportJson.marketNarrative.split("\n\n").map((para, i) => (
                        <p key={i}>{para}</p>
                      ))}
                    </div>
                  </div>

                  {fm.assumptions && (
                    <div className="mb-6">
                      <h2 className="font-semibold text-sm text-[#0D0D0D] mb-3">Model Assumptions</h2>
                      <p className="text-sm text-[#6B6860] leading-relaxed">{fm.assumptions}</p>
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* ─── Financial Model Tab ─── */}
              <TabsContent value="financial">
                <div className="py-6">
                  <p className="text-xs text-[#6B6860] mb-4">
                    Base case: {fm.mortgage_rate_assumed}% mortgage, ${fm.down_payment_assumed?.toLocaleString()} down, ${fm.mortgage_payment_monthly?.toLocaleString()}/mo payment.
                  </p>
                  <div className="bg-white rounded-xl border border-[#E5E3DE] overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-[#E5E3DE]">
                          <th className="text-left px-5 py-3 text-xs font-medium text-[#6B6860] uppercase tracking-wider">Metric</th>
                          <th className="text-right px-5 py-3 text-xs font-medium text-[#B8943F] uppercase tracking-wider">Conservative</th>
                          <th className="text-right px-5 py-3 text-xs font-medium text-[#6357A0] uppercase tracking-wider">Base</th>
                          <th className="text-right px-5 py-3 text-xs font-medium text-[#16A34A] uppercase tracking-wider">Optimistic</th>
                        </tr>
                      </thead>
                      <tbody>
                        {financialRows.map((row, i) => (
                          <tr key={row.label} className={`border-b border-[#E5E3DE] ${i % 2 === 0 ? "bg-white" : "bg-[#F7F6F3]"}`}>
                            <td className="px-5 py-3 text-[#0D0D0D] font-medium">{row.label}</td>
                            <td style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-right px-5 py-3 text-[#6B6860]">{row.conservative}</td>
                            <td style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-right px-5 py-3 text-[#0D0D0D] font-semibold">{row.base}</td>
                            <td style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-right px-5 py-3 text-[#16A34A]">{row.optimistic}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </TabsContent>

              {/* ─── Pitch Deck Tab ─── */}
              <TabsContent value="deck">
                <div className="py-6 flex flex-col items-start gap-4">
                  <p className="text-sm text-[#6B6860]">View the investor-ready pitch deck for this property.</p>
                  <Link href={`/reports/${id}/deck`}>
                    <Button className="gap-2">
                      <Presentation size={15} />
                      Open pitch deck <ExternalLink size={13} />
                    </Button>
                  </Link>
                </div>
              </TabsContent>

              {/* ─── Reno Scope Tab ─── */}
              <TabsContent value="scope">
                <div className="py-6">
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-xs text-[#6B6860]">STR-optimized renovation scope — prioritized by ROI impact.</p>
                    <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-sm font-semibold text-[#0D0D0D]">
                      Total: {fmt$(renoTotal)}
                    </p>
                  </div>
                  <div className="bg-white rounded-xl border border-[#E5E3DE] overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-[#E5E3DE]">
                          <th className="text-left px-5 py-3 text-xs font-medium text-[#6B6860] uppercase tracking-wider">Category</th>
                          <th className="text-left px-5 py-3 text-xs font-medium text-[#6B6860] uppercase tracking-wider">Item</th>
                          <th className="text-left px-5 py-3 text-xs font-medium text-[#6B6860] uppercase tracking-wider">Impact</th>
                          <th className="text-right px-5 py-3 text-xs font-medium text-[#6B6860] uppercase tracking-wider">Est. Cost</th>
                        </tr>
                      </thead>
                      <tbody>
                        {renoItems.map((row, i) => (
                          <tr key={i} className={`border-b border-[#E5E3DE] ${i % 2 === 0 ? "bg-white" : "bg-[#F7F6F3]"}`}>
                            <td className="px-5 py-3">
                              <Badge variant="default" className="text-xs">{row.category}</Badge>
                            </td>
                            <td className="px-5 py-3 text-[#6B6860]">
                              <div>{row.item}</div>
                              {row.notes && <div className="text-xs text-[#9B9790] mt-0.5">{row.notes}</div>}
                            </td>
                            <td className="px-5 py-3">
                              <Badge
                                variant={row.roi_impact === "high" ? "green" : row.roi_impact === "medium" ? "accent" : "default"}
                                className="text-xs"
                              >
                                {row.roi_impact}
                              </Badge>
                            </td>
                            <td style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-right px-5 py-3 text-[#0D0D0D] font-medium">
                              {fmt$(row.estimated_cost)}
                            </td>
                          </tr>
                        ))}
                        <tr className="bg-[#F7F6F3] border-t-2 border-[#E5E3DE]">
                          <td colSpan={3} className="px-5 py-3 text-sm font-semibold text-[#0D0D0D]">Total</td>
                          <td style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-right px-5 py-3 font-bold text-[#0D0D0D]">
                            {fmt$(renoTotal)}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </TabsContent>

              {/* ─── Raw Data Tab ─── */}
              <TabsContent value="raw">
                <div className="py-6">
                  <p className="text-xs text-[#6B6860] mb-4">Raw comp and property data from scraping and AI analysis.</p>
                  <div className="bg-[#111111] rounded-xl p-5 overflow-x-auto">
                    <pre
                      style={{ fontFamily: "var(--font-jetbrains-mono)", fontSize: "12px" }}
                      className="text-[#9B8FCC] leading-relaxed"
                    >
                      {JSON.stringify({ property: analysis.reportJson.property, comps: analysis.reportJson.comps }, null, 2)}
                    </pre>
                  </div>
                </div>
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </div>

      {/* Right: quick stats panel */}
      <div className="hidden xl:flex w-72 flex-col border-l border-[#E5E3DE] bg-white">
        <div className="p-5 flex flex-col gap-4 mt-4">
          <div>
            <p className="text-xs text-[#6B6860] mb-0.5">List price</p>
            <p style={{ fontFamily: "var(--font-outfit)", fontWeight: 800 }} className="text-2xl text-[#0D0D0D]">
              {fmt$(analysis.listPrice)}
            </p>
          </div>
          <div className="h-px bg-[#E5E3DE]" />
          {[
            { label: "Projected annual revenue", value: fmt$(analysis.projRevenue) },
            { label: "Cash-on-cash return", value: fmtPct(analysis.cocReturn), green: true },
            { label: "Cap rate", value: fmtPct(analysis.capRate) },
            { label: "10-year IRR", value: fmtPct(analysis.irr), green: true },
            { label: "Est. occupancy", value: fmtPct(analysis.occupancy) },
            { label: "Net operating income", value: fmt$(analysis.noi) },
          ].map(({ label, value, green }) => (
            <div key={label} className="flex items-center justify-between">
              <p className="text-xs text-[#6B6860]">{label}</p>
              <p
                style={{ fontFamily: "var(--font-jetbrains-mono)" }}
                className={`text-sm font-semibold ${green ? "text-[#16A34A]" : "text-[#0D0D0D]"}`}
              >
                {value}
              </p>
            </div>
          ))}
          <div className="h-px bg-[#E5E3DE]" />
          <Link href={`/reports/${id}/deck`}>
            <Button variant="outline" size="sm" className="w-full gap-1.5">
              <Presentation size={13} /> Open pitch deck
            </Button>
          </Link>
          {(analysis.beds || analysis.baths || analysis.sqft) && (
            <p className="text-xs text-[#9B9790]">
              {[
                analysis.beds && `${analysis.beds} bed`,
                analysis.baths && `${analysis.baths} bath`,
                analysis.sqft && `${analysis.sqft.toLocaleString()} sqft`,
              ].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
