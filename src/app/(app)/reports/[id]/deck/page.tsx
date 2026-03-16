"use client";

import { useState } from "react";
import { Download, Share2, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { UnderwriteLogo } from "@/components/underwrite-logo";

const slides = [
  { id: 1, title: "Cover" },
  { id: 2, title: "Executive Summary" },
  { id: 3, title: "Market Overview" },
  { id: 4, title: "Property Details" },
  { id: 5, title: "Financial Scenarios" },
  { id: 6, title: "Revenue Projections" },
  { id: 7, title: "Highlights & Risks" },
  { id: 8, title: "Next Steps" },
];

function Slide1Cover() {
  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/images/hero-scottsdale.png"
        alt="Scottsdale property"
        className="absolute inset-0 w-full h-full object-cover"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-black/20" />
      <div className="relative h-full flex flex-col p-8">
        <div className="flex items-center justify-between">
          <UnderwriteLogo dark />
          <Badge variant="strong-buy" className="text-xs">↑ Strong Buy</Badge>
        </div>
        <div className="mt-auto">
          <p className="text-white/50 text-xs uppercase tracking-widest mb-2">Investment Analysis</p>
          <h2
            style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-1px" }}
            className="text-white text-4xl leading-tight mb-6"
          >
            8421 E Chaparral Rd
            <br />
            Scottsdale, AZ 85250
          </h2>
          <div className="grid grid-cols-4 gap-4 pt-4 border-t border-white/20">
            {[
              { label: "Proj. Annual Revenue", value: "$87,400", color: "text-white" },
              { label: "Cash-on-Cash Return", value: "14.7%", color: "text-[#4ade80]" },
              { label: "List Price", value: "$749K", color: "text-white" },
              { label: "Est. Occupancy", value: "74.2%", color: "text-white" },
            ].map(({ label, value, color }) => (
              <div key={label}>
                <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className={`text-xl font-semibold ${color}`}>{value}</p>
                <p className="text-white/50 text-xs mt-0.5">{label}</p>
              </div>
            ))}
          </div>
        </div>
        <p
          style={{ fontFamily: "var(--font-jetbrains-mono)" }}
          className="absolute bottom-4 right-6 text-white/20 text-xs"
        >01/08</p>
      </div>
    </div>
  );
}

function Slide2Executive() {
  return (
    <div className="relative w-full h-full rounded-xl bg-white flex flex-col p-8 overflow-hidden">
      <div className="flex items-center justify-between mb-6">
        <UnderwriteLogo />
        <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-xs text-[#6B6860]">02/08</p>
      </div>
      <h2 style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }} className="text-3xl text-[#0D0D0D] mb-2">
        Executive Summary
      </h2>
      <p className="text-[#6B6860] text-sm mb-6">Scottsdale Camelback Corridor · 4BD / 3.5BA · 2,840 sqft</p>

      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { label: "Verdict", value: "Strong Buy", color: "#16A34A", sub: "Based on 12 comp analysis" },
          { label: "Annual Revenue", value: "$87,400", color: "#0D0D0D", sub: "Base case projection" },
          { label: "CoC Return", value: "14.7%", color: "#16A34A", sub: "20% down, 30-yr @ 7.25%" },
        ].map(({ label, value, color, sub }) => (
          <div key={label} className="bg-[#F7F6F3] rounded-xl p-4">
            <p className="text-xs text-[#6B6860] mb-1">{label}</p>
            <p style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, color }} className="text-2xl">{value}</p>
            <p className="text-xs text-[#6B6860] mt-1">{sub}</p>
          </div>
        ))}
      </div>

      <div className="bg-[#F0EEE9] rounded-xl p-5 flex-1">
        <p className="text-xs font-medium text-[#6B6860] uppercase tracking-wider mb-3">Investment Thesis</p>
        <p className="text-sm text-[#6B6860] leading-relaxed">
          8421 E Chaparral Rd is a premier STR acquisition in the Scottsdale Camelback Corridor,
          one of Arizona&apos;s most resilient luxury vacation rental submarkets. With a projected 14.7%
          cash-on-cash return, a break-even occupancy of 47%, and strong year-round demand from golf
          tourism and corporate retreats, this property clears every investment threshold with room to spare.
        </p>
      </div>
    </div>
  );
}

function SlideGeneric({ num, title }: { num: number; title: string }) {
  return (
    <div className="relative w-full h-full rounded-xl bg-white flex flex-col p-8">
      <div className="flex items-center justify-between mb-6">
        <UnderwriteLogo />
        <p style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-xs text-[#6B6860]">
          {String(num).padStart(2, "0")}/08
        </p>
      </div>
      <h2 style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }} className="text-3xl text-[#0D0D0D] mb-4">
        {title}
      </h2>
      <div className="flex-1 flex items-center justify-center">
        <p className="text-[#6B6860] text-sm">Slide content — {title}</p>
      </div>
    </div>
  );
}

export default function PitchDeckPage() {
  const [current, setCurrent] = useState(0);

  function prev() { setCurrent((c) => Math.max(0, c - 1)); }
  function next() { setCurrent((c) => Math.min(slides.length - 1, c + 1)); }

  return (
    <div className="flex h-full">
      {/* Left: slide navigator */}
      <div className="w-48 shrink-0 bg-[#161616] flex flex-col py-5">
        <div className="px-4 mb-5">
          <UnderwriteLogo dark iconOnly />
        </div>
        <p className="px-4 text-xs text-[#444] uppercase tracking-widest mb-2">Slides</p>
        <div className="flex flex-col gap-0.5 px-2 flex-1 overflow-y-auto">
          {slides.map((slide, i) => (
            <button
              key={slide.id}
              onClick={() => setCurrent(i)}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-colors text-sm ${
                i === current
                  ? "bg-[#B8943F]/20 text-[#B8943F]"
                  : "text-[#666] hover:text-white hover:bg-[#1F1F1F]"
              }`}
            >
              <span style={{ fontFamily: "var(--font-jetbrains-mono)" }} className="text-xs opacity-40">
                {String(slide.id).padStart(2, "0")}
              </span>
              {slide.title}
            </button>
          ))}
        </div>
      </div>

      {/* Main: slide area */}
      <div className="flex-1 flex flex-col bg-[#0D0D0D]">
        {/* Top bar */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-[#1F1F1F]">
          <p className="text-sm text-[#666]">
            8421 E Chaparral Rd · Scottsdale, AZ
            <span className="text-[#333] mx-2">·</span>
            <span className="text-[#666]">Slide {current + 1} of 8</span>
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-1.5 border-[#333] bg-transparent text-[#999] hover:text-white hover:bg-[#1F1F1F]">
              <Download size={13} /> Download PDF
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5 border-[#333] bg-transparent text-[#999] hover:text-white hover:bg-[#1F1F1F]">
              <Share2 size={13} /> Share link
            </Button>
          </div>
        </div>

        {/* Slide canvas */}
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="w-full max-w-3xl" style={{ aspectRatio: "16/9" }}>
            {current === 0 && <Slide1Cover />}
            {current === 1 && <Slide2Executive />}
            {current > 1 && <SlideGeneric num={current + 1} title={slides[current].title} />}
          </div>
        </div>

        {/* Bottom nav */}
        <div className="flex items-center justify-center gap-6 py-4 border-t border-[#1F1F1F]">
          <button
            onClick={prev}
            disabled={current === 0}
            className="w-8 h-8 rounded-full bg-[#1F1F1F] flex items-center justify-center text-[#666] hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={16} />
          </button>
          <div className="flex gap-1.5">
            {slides.map((_, i) => (
              <button
                key={i}
                onClick={() => setCurrent(i)}
                className={`rounded-full transition-all ${
                  i === current
                    ? "w-6 h-1.5 bg-[#B8943F]"
                    : "w-1.5 h-1.5 bg-[#333] hover:bg-[#555]"
                }`}
              />
            ))}
          </div>
          <button
            onClick={next}
            disabled={current === slides.length - 1}
            className="w-8 h-8 rounded-full bg-[#1F1F1F] flex items-center justify-center text-[#666] hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
