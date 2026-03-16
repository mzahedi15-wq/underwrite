"use client";

import { useState } from "react";
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

/* ─── mock data ─── */
const property = {
  address: "8421 E Chaparral Rd",
  city: "Scottsdale, AZ 85250",
  verdict: "Strong Buy",
  listPrice: "$749,000",
  projRevenue: "$87,400",
  coc: "14.7%",
  capRate: "6.8%",
  occupancy: "74.2%",
  noi: "$50,990",
  irr: "18.2%",
  img: "/images/hero-scottsdale.png",
};

const financialRows = [
  { label: "Gross Revenue (Y1)", base: "$87,400", conservative: "$72,100", optimistic: "$98,700" },
  { label: "Operating Expenses", base: "$36,410", conservative: "$38,200", optimistic: "$34,800" },
  { label: "Net Operating Income", base: "$50,990", conservative: "$33,900", optimistic: "$63,900" },
  { label: "Cash-on-Cash Return", base: "14.7%", conservative: "9.8%", optimistic: "18.4%" },
  { label: "Cap Rate", base: "6.8%", conservative: "4.5%", optimistic: "8.5%" },
  { label: "IRR (10-yr)", base: "18.2%", conservative: "12.1%", optimistic: "23.7%" },
  { label: "Avg. Nightly Rate", base: "$319", conservative: "$280", optimistic: "$365" },
  { label: "Annual Occupancy", base: "74.2%", conservative: "65%", optimistic: "81%" },
  { label: "Break-even Occupancy", base: "47.1%", conservative: "52.3%", optimistic: "41.2%" },
  { label: "5-yr Equity Build", base: "$198,400", conservative: "$142,300", optimistic: "$247,800" },
];

const renovationItems = [
  { category: "Interior", item: "Master bedroom STR upgrade (linens, staging, smart lock)", cost: "$4,200" },
  { category: "Interior", item: "Kitchen refresh (appliances, hardware, countertops)", cost: "$8,500" },
  { category: "Interior", item: "Living room furniture package (STR-optimized)", cost: "$6,800" },
  { category: "Outdoor", item: "Pool heater + LED lighting installation", cost: "$3,200" },
  { category: "Outdoor", item: "Outdoor lounge furniture & shade structure", cost: "$4,100" },
  { category: "Tech", item: "Smart home package (Nest, Ring, keypad locks ×4)", cost: "$1,850" },
  { category: "Tech", item: 'TV upgrade ×4 (65" 4K + streaming setup)', cost: "$2,400" },
  { category: "Misc", item: "Professional photography & 3D tour", cost: "$950" },
  { category: "Misc", item: "Contingency (10%)", cost: "$3,200" },
];
const renovationTotal = "$35,200";

export default function ReportViewerPage() {
  const [tab, setTab] = useState("report");

  return (
    <div className="flex h-full">
      {/* Left: tabbed content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-[#E5E3DE] bg-[#F7F6F3]">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <Badge variant="strong-buy" className="text-xs">↑ Strong Buy</Badge>
            </div>
            <h1
              style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }}
              className="text-xl text-[#0D0D0D]"
            >
              {property.address}
            </h1>
            <p className="text-sm text-[#6B6860]">{property.city}</p>
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
              <TabsTrigger value="deck">
                <Presentation size={13} />Pitch Deck
              </TabsTrigger>
              <TabsTrigger value="scope"><Hammer size={13} />Reno Scope</TabsTrigger>
              <TabsTrigger value="raw"><Database size={13} />Raw Data</TabsTrigger>
            </TabsList>

            <div className="overflow-y-auto" style={{ height: "calc(100vh - 220px)" }}>
              {/* ─── Report Tab ─── */}
              <TabsContent value="report">
                <div className="py-6 max-w-2xl">
                  {/* Key metrics */}
                  <div className="grid grid-cols-3 gap-3 mb-8">
                    {[
                      { label: "Annual Revenue", value: property.projRevenue, color: "#0D0D0D" },
                      { label: "Cash-on-Cash", value: property.coc, color: "#16A34A" },
                      { label: "Cap Rate", value: property.capRate, color: "#0D0D0D" },
                      { label: "10-yr IRR", value: property.irr, color: "#16A34A" },
                      { label: "Occupancy", value: property.occupancy, color: "#0D0D0D" },
                      { label: "List Price", value: property.listPrice, color: "#0D0D0D" },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="bg-white rounded-xl border border-[#E5E3DE] p-4">
                        <p className="text-xs text-[#6B6860] mb-1">{label}</p>
                        <p
                          style={{ fontFamily: "var(--font-jetbrains-mono)", color }}
                          className="text-xl font-semibold"
                        >
                          {value}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Investment thesis */}
                  <div className="mb-6">
                    <h2 className="font-semibold text-sm text-[#0D0D0D] mb-3">Investment Thesis</h2>
                    <div className="text-sm text-[#6B6860] leading-relaxed space-y-3">
                      <p>
                        8421 E Chaparral Rd represents a compelling STR acquisition opportunity in one of Arizona&apos;s
                        most resilient luxury vacation rental markets. Situated in the Camelback Corridor submarket,
                        the property benefits from year-round demand driven by golf tourism, corporate retreats,
                        and proximity to Old Town Scottsdale.
                      </p>
                      <p>
                        Comparable STR properties within a 1-mile radius achieved a median nightly rate of $312 over
                        the trailing 90 days, with an average occupancy of 71.4%. Our base case projects this
                        property at a slight premium ($319 ADR) due to its pool, 4-bedroom layout, and mountain views —
                        attributes that consistently command 8–12% ADR premiums in this submarket.
                      </p>
                      <p>
                        At a 14.7% cash-on-cash return (base case, 20% down), this deal clears our 12% minimum
                        threshold with meaningful upside in the optimistic scenario (18.4% CoC). The break-even
                        occupancy of 47.1% provides substantial cushion against demand softening.
                      </p>
                    </div>
                  </div>

                  {/* Risk factors */}
                  <div className="mb-6">
                    <h2 className="font-semibold text-sm text-[#0D0D0D] mb-3">Key Risks</h2>
                    <div className="flex flex-col gap-2">
                      {[
                        { risk: "STR regulation", detail: "Scottsdale requires STR permit ($250/yr). No current density restrictions in this zone.", severity: "low" },
                        { risk: "Seasonality", detail: "June–August occupancy dips to ~55% due to heat. Model accounts for this.", severity: "medium" },
                        { risk: "HOA restrictions", detail: "No HOA. Property is fee simple.", severity: "low" },
                        { risk: "Interest rate sensitivity", detail: "At 7.5% mortgage rate, CoC drops to 11.2% — still above threshold.", severity: "medium" },
                      ].map(({ risk, detail, severity }) => (
                        <div key={risk} className="flex items-start gap-3 bg-white rounded-lg border border-[#E5E3DE] p-3">
                          <div className={`mt-0.5 w-1.5 h-1.5 rounded-full shrink-0 ${severity === "low" ? "bg-[#16A34A]" : "bg-[#B8943F]"}`} />
                          <div>
                            <p className="text-sm font-medium text-[#0D0D0D]">{risk}</p>
                            <p className="text-xs text-[#6B6860]">{detail}</p>
                          </div>
                          <Badge variant={severity === "low" ? "green" : "accent"} className="ml-auto shrink-0 text-xs">
                            {severity}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </TabsContent>

              {/* ─── Financial Model Tab ─── */}
              <TabsContent value="financial">
                <div className="py-6">
                  <p className="text-xs text-[#6B6860] mb-4">
                    Base case assumes 20% down ($149,800), 30-yr mortgage at 7.25%, and Year 1 projections.
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
                            <td
                              style={{ fontFamily: "var(--font-jetbrains-mono)" }}
                              className="text-right px-5 py-3 text-[#6B6860]"
                            >{row.conservative}</td>
                            <td
                              style={{ fontFamily: "var(--font-jetbrains-mono)" }}
                              className="text-right px-5 py-3 text-[#0D0D0D] font-semibold"
                            >{row.base}</td>
                            <td
                              style={{ fontFamily: "var(--font-jetbrains-mono)" }}
                              className="text-right px-5 py-3 text-[#16A34A]"
                            >{row.optimistic}</td>
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
                  <Link href="/reports/demo/deck">
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
                    <p className="text-xs text-[#6B6860]">STR-optimized renovation scope of work — prioritized by ROI impact.</p>
                    <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-sm font-semibold text-[#0D0D0D]">
                      Total: {renovationTotal}
                    </p>
                  </div>
                  <div className="bg-white rounded-xl border border-[#E5E3DE] overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-[#E5E3DE]">
                          <th className="text-left px-5 py-3 text-xs font-medium text-[#6B6860] uppercase tracking-wider">Category</th>
                          <th className="text-left px-5 py-3 text-xs font-medium text-[#6B6860] uppercase tracking-wider">Item</th>
                          <th className="text-right px-5 py-3 text-xs font-medium text-[#6B6860] uppercase tracking-wider">Est. Cost</th>
                        </tr>
                      </thead>
                      <tbody>
                        {renovationItems.map((row, i) => (
                          <tr key={i} className={`border-b border-[#E5E3DE] ${i % 2 === 0 ? "bg-white" : "bg-[#F7F6F3]"}`}>
                            <td className="px-5 py-3">
                              <Badge variant="default" className="text-xs">{row.category}</Badge>
                            </td>
                            <td className="px-5 py-3 text-[#6B6860]">{row.item}</td>
                            <td
                              style={{ fontFamily: "var(--font-jetbrains-mono)" }}
                              className="text-right px-5 py-3 text-[#0D0D0D] font-medium"
                            >{row.cost}</td>
                          </tr>
                        ))}
                        <tr className="bg-[#F7F6F3] border-t-2 border-[#E5E3DE]">
                          <td colSpan={2} className="px-5 py-3 text-sm font-semibold text-[#0D0D0D]">Total</td>
                          <td
                            style={{ fontFamily: "var(--font-jetbrains-mono)" }}
                            className="text-right px-5 py-3 font-bold text-[#0D0D0D]"
                          >{renovationTotal}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </TabsContent>

              {/* ─── Raw Data Tab ─── */}
              <TabsContent value="raw">
                <div className="py-6">
                  <p className="text-xs text-[#6B6860] mb-4">Raw comp data pulled from AirDNA and Zillow. Last updated Mar 14, 2026.</p>
                  <div className="bg-[#111111] rounded-xl p-5 overflow-x-auto">
                    <pre
                      style={{ fontFamily: "var(--font-jetbrains-mono)", fontSize: "12px" }}
                      className="text-[#9B8FCC] leading-relaxed"
                    >{`{
  "property": {
    "address": "8421 E Chaparral Rd, Scottsdale AZ 85250",
    "beds": 4, "baths": 3.5, "sqft": 2840,
    "lot_sqft": 9200, "year_built": 2018,
    "list_price": 749000, "price_per_sqft": 263.7
  },
  "str_comps": {
    "radius_miles": 1.0, "comp_count": 12,
    "median_adr": 312, "median_occupancy": 0.714,
    "median_annual_revenue": 81340,
    "percentile_75_revenue": 94200
  },
  "market": {
    "str_permit_required": true,
    "permit_cost_annual": 250,
    "density_restrictions": false,
    "demand_drivers": ["golf", "corporate retreats", "Old Town proximity"],
    "seasonality_peak": ["Jan", "Feb", "Mar", "Oct", "Nov"],
    "seasonality_trough": ["Jun", "Jul", "Aug"]
  }
}`}</pre>
                  </div>
                </div>
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </div>

      {/* Right: photo + quick stats panel */}
      <div className="hidden xl:flex w-72 flex-col border-l border-[#E5E3DE] bg-white">
        <div className="relative h-52 overflow-hidden shrink-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={property.img}
            alt={property.address}
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
        </div>
        <div className="p-5 flex flex-col gap-4">
          <div>
            <p className="text-xs text-[#6B6860] mb-0.5">List price</p>
            <p style={{ fontFamily: "var(--font-outfit)", fontWeight: 800 }} className="text-2xl text-[#0D0D0D]">
              {property.listPrice}
            </p>
          </div>
          <div className="h-px bg-[#E5E3DE]" />
          {[
            { label: "Projected annual revenue", value: property.projRevenue },
            { label: "Cash-on-cash return", value: property.coc, green: true },
            { label: "Cap rate", value: property.capRate },
            { label: "10-year IRR", value: property.irr, green: true },
            { label: "Est. occupancy", value: property.occupancy },
            { label: "Net operating income", value: property.noi },
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
          <Link href="/reports/demo/deck">
            <Button variant="outline" size="sm" className="w-full gap-1.5">
              <Presentation size={13} /> Open pitch deck
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
