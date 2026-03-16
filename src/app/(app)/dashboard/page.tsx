import Link from "next/link";
import { PlusCircle, ArrowRight, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const analyses = [
  {
    id: "1",
    address: "8421 E Chaparral Rd",
    city: "Scottsdale, AZ 85250",
    img: "/images/hero-scottsdale.png",
    verdict: "strong-buy" as const,
    verdictLabel: "Strong Buy",
    revenue: "$87,400",
    coc: "14.7%",
    listPrice: "$749K",
    occupancy: "74.2%",
    date: "Mar 14, 2026",
    status: "complete",
  },
  {
    id: "2",
    address: "789 Canyon Rim Dr",
    city: "Sedona, AZ 86336",
    img: "/images/sedona-cabin.png",
    verdict: "hold" as const,
    verdictLabel: "Hold",
    revenue: "$63,200",
    coc: "9.1%",
    listPrice: "$520K",
    occupancy: "68.4%",
    date: "Mar 12, 2026",
    status: "complete",
  },
  {
    id: "3",
    address: "204 Biltmore Ave",
    city: "Asheville, NC 28803",
    img: "/images/asheville-craftsman.png",
    verdict: "strong-buy" as const,
    verdictLabel: "Strong Buy",
    revenue: "$58,100",
    coc: "12.3%",
    listPrice: "$410K",
    occupancy: "71.0%",
    date: "Mar 10, 2026",
    status: "complete",
  },
  {
    id: "4",
    address: "1812 Music Row",
    city: "Nashville, TN 37203",
    img: "/images/nashville-townhouse.png",
    verdict: "strong-buy" as const,
    verdictLabel: "Strong Buy",
    revenue: "$72,800",
    coc: "11.8%",
    listPrice: "$589K",
    occupancy: "78.1%",
    date: "Mar 8, 2026",
    status: "complete",
  },
  {
    id: "5",
    address: "44 Ski View Rd",
    city: "Gatlinburg, TN 37738",
    img: "/images/gatlinburg-snow.png",
    verdict: "hold" as const,
    verdictLabel: "Hold",
    revenue: "$51,400",
    coc: "8.4%",
    listPrice: "$395K",
    occupancy: "65.3%",
    date: "Mar 5, 2026",
    status: "complete",
  },
];

const stats = [
  { label: "Total analyses", value: "5", sub: "this month" },
  { label: "Avg. CoC return", value: "11.3%", sub: "across all analyses", positive: true },
  { label: "Top market", value: "Nashville", sub: "78.1% occupancy" },
  { label: "Analyses remaining", value: "5 / 10", sub: "Pro plan" },
];

export default function DashboardPage() {
  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1
            style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }}
            className="text-2xl text-[#0D0D0D]"
          >
            Dashboard
          </h1>
          <p className="text-sm text-[#6B6860] mt-0.5">Welcome back, Melad.</p>
        </div>
        <Link href="/new">
          <Button size="md" className="gap-2">
            <PlusCircle size={15} />
            New analysis
          </Button>
        </Link>
      </div>

      {/* Stats row */}
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

      {/* Section label */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-[#0D0D0D]">Recent analyses</h2>
        <button className="text-xs text-[#6B6860] hover:text-[#0D0D0D] flex items-center gap-1">
          View all <ArrowRight size={12} />
        </button>
      </div>

      {/* Analysis cards grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {analyses.map((a) => (
          <Link key={a.id} href={`/reports/${a.id}`}>
            <div className="bg-white rounded-xl border border-[#E5E3DE] overflow-hidden hover:shadow-md transition-shadow cursor-pointer group">
              {/* Photo */}
              <div className="relative h-40 overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={a.img}
                  alt={a.address}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
                <Badge
                  variant={a.verdict}
                  className="absolute top-3 left-3 text-xs"
                >
                  {a.verdict === "strong-buy" ? "↑" : "→"} {a.verdictLabel}
                </Badge>
              </div>

              {/* Content */}
              <div className="p-4">
                <p className="font-semibold text-sm text-[#0D0D0D]">{a.address}</p>
                <p className="text-xs text-[#6B6860] mb-4">{a.city}</p>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-xs text-[#6B6860]">Annual revenue</p>
                    <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-sm font-semibold text-[#0D0D0D]">{a.revenue}</p>
                  </div>
                  <div>
                    <p className="text-xs text-[#6B6860]">CoC return</p>
                    <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-sm font-semibold text-[#16A34A]">{a.coc}</p>
                  </div>
                  <div>
                    <p className="text-xs text-[#6B6860]">List price</p>
                    <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-sm font-semibold text-[#0D0D0D]">{a.listPrice}</p>
                  </div>
                  <div>
                    <p className="text-xs text-[#6B6860]">Occupancy</p>
                    <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-sm font-semibold text-[#0D0D0D]">{a.occupancy}</p>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#E5E3DE] flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <TrendingUp size={12} className="text-[#16A34A]" />
                    <span className="text-xs text-[#6B6860]">{a.date}</span>
                  </div>
                  <span className="text-xs text-[#6357A0] font-medium group-hover:underline">
                    View report →
                  </span>
                </div>
              </div>
            </div>
          </Link>
        ))}

        {/* New analysis CTA card */}
        <Link href="/new">
          <div className="bg-[#F0EEE9] rounded-xl border border-dashed border-[#E5E3DE] h-full min-h-[280px] flex flex-col items-center justify-center gap-3 hover:bg-[#EAE8E2] transition-colors cursor-pointer group">
            <div className="w-10 h-10 rounded-full bg-[#E5E3DE] flex items-center justify-center group-hover:bg-[#D4D2CB] transition-colors">
              <PlusCircle size={18} className="text-[#6B6860]" />
            </div>
            <p className="text-sm font-medium text-[#6B6860]">New analysis</p>
            <p className="text-xs text-[#6B6860]/60">Paste any Zillow or Redfin URL</p>
          </div>
        </Link>
      </div>
    </div>
  );
}
