import Link from "next/link";
import { ArrowRight, Check, Zap, FileText, TrendingUp, Shield } from "lucide-react";
import { UnderwriteLogo } from "@/components/underwrite-logo";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const features = [
  {
    icon: Zap,
    title: "15-minute turnaround",
    description:
      "Paste a Zillow or Redfin URL. Our AI pipeline pulls comps, runs the model, and delivers a complete package while you grab coffee.",
  },
  {
    icon: FileText,
    title: "Investment-grade documents",
    description:
      "Financial model, market narrative, investor pitch deck, and renovation scope of work — ready to share with partners or lenders.",
  },
  {
    icon: TrendingUp,
    title: "Hyper-local market data",
    description:
      "AirDNA comps, Zillow price history, and STR regulation data synthesized into a single market verdict.",
  },
  {
    icon: Shield,
    title: "Replaces $2,000–5,000 consultants",
    description:
      "Get the same analysis a boutique STR consulting firm would deliver — in minutes, not weeks.",
  },
];

const plans = [
  {
    name: "Free",
    price: "$0",
    period: "",
    description: "One lifetime analysis to see what we're about.",
    features: ["1 analysis (lifetime)", "Full investment package", "PDF export"],
    cta: "Start free",
    highlight: false,
  },
  {
    name: "Starter",
    price: "$49",
    period: "/mo",
    description: "For investors evaluating a few deals per month.",
    features: ["3 analyses / month", "Full investment package", "PDF export", "Email support"],
    cta: "Get started",
    highlight: false,
  },
  {
    name: "Pro",
    price: "$149",
    period: "/mo",
    description: "For active investors running a growing portfolio.",
    features: [
      "10 analyses / month",
      "Full investment package",
      "PDF export",
      "Priority support",
      "Renovation scope of work",
    ],
    cta: "Get started",
    highlight: true,
  },
  {
    name: "Unlimited",
    price: "$299",
    period: "/mo",
    description: "For operators and funds who never stop underwriting.",
    features: [
      "Unlimited analyses",
      "Full investment package",
      "PDF export",
      "Priority support",
      "Renovation scope of work",
      "API access",
    ],
    cta: "Get started",
    highlight: false,
  },
];

const markets = [
  { label: "Scottsdale, AZ", tag: "Desert Luxury", img: "/images/hero-scottsdale.png", rev: "$87,400", occ: "74%" },
  { label: "Sedona, AZ", tag: "National Park Gateway", img: "/images/sedona-cabin.png", rev: "$63,200", occ: "68%" },
  { label: "Asheville, NC", tag: "Mountain Retreat", img: "/images/asheville-craftsman.png", rev: "$58,100", occ: "71%" },
  { label: "Nashville, TN", tag: "Urban Hotspot", img: "/images/nashville-townhouse.png", rev: "$72,800", occ: "78%" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#F7F6F3]">
      {/* Nav */}
      <header className="sticky top-0 z-50 bg-[#F7F6F3]/95 backdrop-blur border-b border-[#E5E3DE]">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <UnderwriteLogo />
          <nav className="hidden md:flex items-center gap-8 text-sm text-[#6B6860]">
            <Link href="#features" className="hover:text-[#0D0D0D] transition-colors">Features</Link>
            <Link href="#markets" className="hover:text-[#0D0D0D] transition-colors">Markets</Link>
            <Link href="#pricing" className="hover:text-[#0D0D0D] transition-colors">Pricing</Link>
          </nav>
          <div className="flex items-center gap-3">
            <Link href="/sign-in">
              <Button variant="ghost" size="sm">Sign in</Button>
            </Link>
            <Link href="/sign-up">
              <Button size="sm">Get started <ArrowRight size={14} /></Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-24 pb-16">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Left: copy */}
          <div>
            <Badge variant="purple" className="mb-6 text-xs font-medium px-3 py-1">
              AI-powered STR underwriting
            </Badge>
            <h1
              style={{
                fontFamily: "var(--font-outfit)",
                fontWeight: 800,
                fontSize: "clamp(2.5rem, 5vw, 3.75rem)",
                lineHeight: 1.05,
                letterSpacing: "-2px",
                color: "#0D0D0D",
              }}
              className="mb-6"
            >
              Investment-grade
              <br />
              STR analysis.
              <br />
              <span style={{ color: "#B8943F" }}>In 15 minutes.</span>
            </h1>
            <p className="text-[#6B6860] text-lg leading-relaxed mb-10 max-w-md">
              Paste any Zillow or Redfin URL. Underwrite delivers a full investment
              package — financial model, market narrative, pitch deck, and renovation
              scope — ready to share with partners or lenders.
            </p>
            <div className="flex flex-col sm:flex-row gap-3">
              <Link href="/sign-up">
                <Button size="lg" className="gap-2">
                  Analyze a property <ArrowRight size={16} />
                </Button>
              </Link>
              <Link href="#features">
                <Button variant="outline" size="lg">
                  See how it works
                </Button>
              </Link>
            </div>
            <p className="text-xs text-[#6B6860] mt-4">
              First analysis free — no credit card required.
            </p>
          </div>

          {/* Right: property card */}
          <div className="relative">
            <div className="rounded-2xl overflow-hidden shadow-2xl border border-[#E5E3DE] bg-white">
              <div className="relative h-64 overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/images/hero-scottsdale.png"
                  alt="Scottsdale luxury STR property"
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                <div className="absolute bottom-4 left-4 right-4">
                  <Badge variant="strong-buy" className="mb-2">↑ Strong Buy</Badge>
                  <p className="text-white font-semibold text-sm">8421 E Chaparral Rd, Scottsdale AZ</p>
                </div>
              </div>
              <div className="p-5 grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-[#6B6860] mb-0.5">Proj. Annual Revenue</p>
                  <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-xl font-semibold text-[#0D0D0D]">$87,400</p>
                </div>
                <div>
                  <p className="text-xs text-[#6B6860] mb-0.5">Cash-on-Cash Return</p>
                  <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-xl font-semibold text-[#16A34A]">14.7%</p>
                </div>
                <div>
                  <p className="text-xs text-[#6B6860] mb-0.5">List Price</p>
                  <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-xl font-semibold text-[#0D0D0D]">$749K</p>
                </div>
                <div>
                  <p className="text-xs text-[#6B6860] mb-0.5">Est. Occupancy</p>
                  <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-xl font-semibold text-[#0D0D0D]">74.2%</p>
                </div>
              </div>
              <div className="px-5 pb-5">
                <div className="h-px bg-[#E5E3DE] mb-4" />
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full bg-[#DCFCE7] flex items-center justify-center">
                    <Check size={10} className="text-[#16A34A]" />
                  </div>
                  <p className="text-xs text-[#6B6860]">Analysis complete — generated in 12 min 34 sec</p>
                </div>
              </div>
            </div>
            {/* Floating tag */}
            <div className="absolute -top-4 -right-4 bg-white rounded-xl shadow-lg border border-[#E5E3DE] px-4 py-3 hidden lg:block">
              <p className="text-xs text-[#6B6860]">vs. traditional consultant</p>
              <p style={{ fontFamily: "var(--font-outfit)", fontWeight: 800 }} className="text-lg text-[#16A34A]">Save $4,200</p>
            </div>
          </div>
        </div>
      </section>

      {/* Editorial photo strip */}
      <section className="w-full overflow-hidden my-8">
        <div className="relative h-48">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/images/lake-cabin.png"
            alt="Lake cabin panorama"
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-black/30" />
          <div className="absolute inset-0 flex items-center justify-center">
            <p
              style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-1px" }}
              className="text-white text-3xl md:text-5xl"
            >
              Every deal deserves real analysis.
            </p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="max-w-6xl mx-auto px-6 py-24">
        <div className="mb-16">
          <p className="text-xs font-medium text-[#6B6860] uppercase tracking-widest mb-3">How it works</p>
          <h2
            style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-1.5px" }}
            className="text-4xl md:text-5xl text-[#0D0D0D]"
          >
            From URL to investment package
            <br />
            in under 15 minutes.
          </h2>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {features.map(({ icon: Icon, title, description }) => (
            <div key={title}>
              <div className="w-10 h-10 rounded-lg bg-[#EDE9FE] flex items-center justify-center mb-4">
                <Icon size={18} className="text-[#6357A0]" />
              </div>
              <h3 className="font-semibold text-[#0D0D0D] mb-2">{title}</h3>
              <p className="text-sm text-[#6B6860] leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Markets grid */}
      <section id="markets" className="max-w-6xl mx-auto px-6 pb-24">
        <div className="mb-10">
          <p className="text-xs font-medium text-[#6B6860] uppercase tracking-widest mb-3">Top markets</p>
          <h2
            style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-1.5px" }}
            className="text-4xl text-[#0D0D0D]"
          >
            Where the numbers work.
          </h2>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {markets.map(({ label, tag, img, rev, occ }) => (
            <div key={label} className="rounded-xl overflow-hidden border border-[#E5E3DE] bg-white">
              <div className="relative h-36 overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={img} alt={label} className="w-full h-full object-cover" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
                <Badge variant="dark" className="absolute bottom-3 left-3 text-xs">{tag}</Badge>
              </div>
              <div className="p-4">
                <p className="font-semibold text-sm text-[#0D0D0D] mb-3">{label}</p>
                <div className="flex justify-between text-xs">
                  <div>
                    <p className="text-[#6B6860]">Avg. annual rev</p>
                    <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="font-medium text-[#0D0D0D]">{rev}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[#6B6860]">Avg. occupancy</p>
                    <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="font-medium text-[#0D0D0D]">{occ}</p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="bg-white border-t border-[#E5E3DE] py-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="mb-16 text-center">
            <p className="text-xs font-medium text-[#6B6860] uppercase tracking-widest mb-3">Pricing</p>
            <h2
              style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-1.5px" }}
              className="text-4xl md:text-5xl text-[#0D0D0D]"
            >
              Straightforward pricing.
            </h2>
            <p className="text-[#6B6860] mt-4">Or pay $199 per analysis. No subscription required.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`rounded-xl p-6 border ${
                  plan.highlight
                    ? "border-[#0D0D0D] bg-[#0D0D0D] text-white"
                    : "border-[#E5E3DE] bg-[#F7F6F3]"
                }`}
              >
                <p className={`text-xs font-medium uppercase tracking-widest mb-4 ${plan.highlight ? "text-[#9B8FCC]" : "text-[#6B6860]"}`}>
                  {plan.name}
                </p>
                <div className="flex items-baseline gap-1 mb-2">
                  <span
                    style={{ fontFamily: "var(--font-outfit)", fontWeight: 800 }}
                    className="text-3xl"
                  >
                    {plan.price}
                  </span>
                  <span className={`text-sm ${plan.highlight ? "text-[#9B8FCC]" : "text-[#6B6860]"}`}>{plan.period}</span>
                </div>
                <p className={`text-sm mb-6 ${plan.highlight ? "text-[#9B8FCC]" : "text-[#6B6860]"}`}>{plan.description}</p>
                <ul className="space-y-2 mb-8">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-sm">
                      <Check size={13} className={plan.highlight ? "text-[#9B8FCC]" : "text-[#16A34A]"} />
                      <span className={plan.highlight ? "text-[#E5E3DE]" : "text-[#6B6860]"}>{f}</span>
                    </li>
                  ))}
                </ul>
                <Link href="/sign-up">
                  <Button
                    variant={plan.highlight ? "accent" : "outline"}
                    className="w-full"
                    size="md"
                  >
                    {plan.cta}
                  </Button>
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA footer banner */}
      <section className="max-w-6xl mx-auto px-6 py-24 text-center">
        <h2
          style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-2px" }}
          className="text-5xl md:text-6xl text-[#0D0D0D] mb-6"
        >
          Stop guessing.
          <br />
          <span style={{ color: "#B8943F" }}>Start underwriting.</span>
        </h2>
        <p className="text-[#6B6860] text-lg mb-10">Your first analysis is free. No credit card required.</p>
        <Link href="/sign-up">
          <Button size="xl" className="gap-2">
            Analyze a property now <ArrowRight size={18} />
          </Button>
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#E5E3DE] py-8">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <UnderwriteLogo />
          <p className="text-xs text-[#6B6860]">© 2026 Underwrite. All rights reserved.</p>
          <div className="flex gap-6 text-xs text-[#6B6860]">
            <Link href="/privacy" className="hover:text-[#0D0D0D]">Privacy</Link>
            <Link href="/terms" className="hover:text-[#0D0D0D]">Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
