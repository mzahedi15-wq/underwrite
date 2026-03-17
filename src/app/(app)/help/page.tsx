"use client";

import { useState } from "react";
import { ChevronDown, Mail, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

const faqs = [
  {
    q: "What listing URLs are supported?",
    a: "Zillow and Redfin property detail pages are fully supported. Paste the direct URL to a specific listing (e.g., zillow.com/homedetails/…) — search result pages won't work.",
  },
  {
    q: "How long does an analysis take?",
    a: "Most analyses complete in 10–20 minutes. The pipeline scrapes real Airbnb and VRBO comp data, runs a full financial model, and generates an AI-written scope of work and investment narrative.",
  },
  {
    q: "What's included in each analysis?",
    a: "Every analysis includes: a 10-year DCF financial model with conservative/base/optimistic scenarios, Airbnb + VRBO comp data from the surrounding market, a line-item renovation scope of work, an AI-written investment narrative, and an investment score (0–100).",
  },
  {
    q: "How accurate is the revenue projection?",
    a: "Revenue is estimated from real Airbnb and VRBO listings within a 5-mile radius, matched to the subject property's bedroom count. The model blends median comp performance with top-10% comp performance to produce three scenarios. Actual results will vary based on listing quality, management, and market conditions.",
  },
  {
    q: "What does the investment score mean?",
    a: "The score (0–100) weights six factors: cash-on-cash return (25%), cap rate (20%), revenue upside vs. comps (20%), renovation efficiency (15%), market strength (10%), and entry price vs. comps (10%). A score above 70 typically indicates a strong opportunity.",
  },
  {
    q: "Can I analyze any property type?",
    a: "Yes — single family, condo, townhouse, cabin/retreat, and multi-family are all supported. Select the appropriate type on the analysis form; it informs the renovation scope and comp matching.",
  },
  {
    q: "What if the analysis fails?",
    a: "The most common cause is an unsupported URL or a listing that has been taken down. Try resubmitting with a fresh Zillow or Redfin URL. If the problem persists, contact support.",
  },
  {
    q: "How do I upgrade or change my plan?",
    a: "Go to Billing in the sidebar. You can upgrade to Starter ($49/mo), Pro ($99/mo), or Unlimited ($249/mo). You can also purchase individual analyses for $29 each.",
  },
  {
    q: "Is my data secure?",
    a: "All analyses are private to your account. We use Clerk for authentication and Supabase (PostgreSQL) for data storage. No analysis data is shared with other users or third parties.",
  },
];

function FAQ({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-[#E5E3DE] last:border-0">
      <button
        className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left hover:bg-[#F7F6F3] transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span className="text-sm font-medium text-[#0D0D0D]">{q}</span>
        <ChevronDown
          size={16}
          className={cn("text-[#6B6860] shrink-0 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <p className="px-5 pb-4 text-sm text-[#6B6860] leading-relaxed">{a}</p>
      )}
    </div>
  );
}

export default function HelpPage() {
  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-8">
        <h1
          style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }}
          className="text-2xl text-[#0D0D0D] mb-1"
        >
          Help
        </h1>
        <p className="text-sm text-[#6B6860]">Answers to common questions.</p>
      </div>

      <div className="flex flex-col gap-6">
        {/* FAQ */}
        <div className="bg-white rounded-xl border border-[#E5E3DE] overflow-hidden">
          {faqs.map((faq) => (
            <FAQ key={faq.q} {...faq} />
          ))}
        </div>

        {/* Contact */}
        <div className="bg-[#F0EEE9] rounded-xl border border-[#E5E3DE] p-5 flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-[#0D0D0D] mb-0.5">Still have questions?</p>
            <p className="text-xs text-[#6B6860]">Email us and we&apos;ll get back to you within 24 hours.</p>
          </div>
          <a
            href="mailto:support@underwriteapp.com"
            className="inline-flex items-center gap-2 bg-[#0D0D0D] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#1a1a1a] transition-colors"
          >
            <Mail size={14} />
            Contact support
          </a>
        </div>
      </div>
    </div>
  );
}
