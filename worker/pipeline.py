"""
Underwrite Analysis Pipeline
Step-by-step orchestration using Claude claude-sonnet-4-6 + web scraping.
"""

import asyncio
import os
import json
import httpx
import anthropic
from typing import Optional
from scraper import scrape_property, scrape_str_comps

client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


async def run_analysis_pipeline(
    analysis_id: str,
    property_url: str,
    property_type: str,
    strategy: str,
    renovation_budget: Optional[int],
    notes: Optional[str],
) -> dict:
    print(f"[{analysis_id}] Starting pipeline for {property_url}")

    # ── Step 1: Scrape property listing ──────────────────────────────────
    print(f"[{analysis_id}] Step 1: Scraping property data")
    property_data = await scrape_property(property_url)

    # ── Step 2: Pull STR comps ────────────────────────────────────────────
    print(f"[{analysis_id}] Step 2: Pulling STR comps")
    comps = await scrape_str_comps(
        lat=property_data.get("lat"),
        lon=property_data.get("lon"),
        beds=property_data.get("beds", 3),
    )

    # ── Step 3: AI — Build financial model ───────────────────────────────
    print(f"[{analysis_id}] Step 3: Building financial model")
    financial_model = await _build_financial_model(
        property_data, comps, strategy, renovation_budget, notes
    )

    # ── Step 4: AI — Write market narrative ──────────────────────────────
    print(f"[{analysis_id}] Step 4: Writing market narrative")
    market_narrative = await _write_market_narrative(property_data, comps, financial_model)

    # ── Step 5: AI — Generate pitch deck content ──────────────────────────
    print(f"[{analysis_id}] Step 5: Generating pitch deck")
    pitch_deck = await _generate_pitch_deck(property_data, financial_model, market_narrative)

    # ── Step 6: AI — Scope renovation ────────────────────────────────────
    print(f"[{analysis_id}] Step 6: Scoping renovation")
    reno_scope = await _scope_renovation(
        property_data, property_type, renovation_budget, financial_model
    )

    # ── Step 7: Determine verdict ─────────────────────────────────────────
    verdict = _determine_verdict(financial_model)

    print(f"[{analysis_id}] Pipeline complete. Verdict: {verdict}")

    return {
        "address": property_data.get("address"),
        "city": property_data.get("city"),
        "state": property_data.get("state"),
        "zip": property_data.get("zip"),
        "listPrice": property_data.get("list_price"),
        "beds": property_data.get("beds"),
        "baths": property_data.get("baths"),
        "sqft": property_data.get("sqft"),
        "verdict": verdict,
        "projRevenue": financial_model.get("gross_revenue_base"),
        "cocReturn": financial_model.get("coc_return_base"),
        "capRate": financial_model.get("cap_rate_base"),
        "irr": financial_model.get("irr_base"),
        "occupancy": financial_model.get("occupancy_base"),
        "noi": financial_model.get("noi_base"),
        "adr": financial_model.get("adr_base"),
        "reportJson": {
            "financialModel": financial_model,
            "marketNarrative": market_narrative,
            "pitchDeck": pitch_deck,
            "renovationScope": reno_scope,
            "comps": comps,
            "property": property_data,
        },
    }


async def _build_financial_model(
    property_data: dict,
    comps: dict,
    strategy: str,
    renovation_budget: Optional[int],
    notes: Optional[str],
) -> dict:
    prompt = f"""You are an expert STR investment analyst. Build a detailed financial model.

PROPERTY:
{json.dumps(property_data, indent=2)}

STR COMPS (1-mile radius):
{json.dumps(comps, indent=2)}

INVESTOR CONTEXT:
- Strategy: {strategy}
- Renovation budget: ${renovation_budget:,} if renovation_budget else 'None specified'
- Notes: {notes or 'None'}

Return a JSON object with these exact keys (numbers only, no $ signs or % signs):
{{
  "gross_revenue_base": <int, annual>,
  "gross_revenue_conservative": <int>,
  "gross_revenue_optimistic": <int>,
  "operating_expenses_base": <int>,
  "operating_expenses_conservative": <int>,
  "operating_expenses_optimistic": <int>,
  "noi_base": <int>,
  "noi_conservative": <int>,
  "noi_optimistic": <int>,
  "coc_return_base": <float, e.g. 14.7>,
  "coc_return_conservative": <float>,
  "coc_return_optimistic": <float>,
  "cap_rate_base": <float>,
  "cap_rate_conservative": <float>,
  "cap_rate_optimistic": <float>,
  "irr_base": <float, 10-year>,
  "irr_conservative": <float>,
  "irr_optimistic": <float>,
  "adr_base": <int, nightly rate>,
  "adr_conservative": <int>,
  "adr_optimistic": <int>,
  "occupancy_base": <float, e.g. 74.2>,
  "occupancy_conservative": <float>,
  "occupancy_optimistic": <float>,
  "breakeven_occupancy": <float>,
  "down_payment_assumed": <int>,
  "mortgage_rate_assumed": <float>,
  "mortgage_payment_monthly": <int>,
  "assumptions": <string, 2-3 sentences>
}}

Assume 20% down payment and 7.25% 30-year fixed mortgage unless notes specify otherwise.
Return ONLY valid JSON.
"""

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text  # type: ignore
    # Extract JSON from response
    start = text.find("{")
    end = text.rfind("}") + 1
    return json.loads(text[start:end])


async def _write_market_narrative(
    property_data: dict,
    comps: dict,
    financial_model: dict,
) -> str:
    prompt = f"""You are a senior STR investment analyst writing a market narrative for an investor report.

PROPERTY: {property_data.get('address')}, {property_data.get('city')}, {property_data.get('state')}
LIST PRICE: ${property_data.get('list_price', 0):,}
FINANCIAL MODEL (base case): CoC {financial_model.get('coc_return_base')}%, NOI ${financial_model.get('noi_base', 0):,}, Occupancy {financial_model.get('occupancy_base')}%
STR COMPS: {json.dumps(comps, indent=2)}

Write a 3-paragraph investment narrative covering:
1. Why this market works for STR (demand drivers, seasonality, regulation)
2. Why this specific property has an edge (features that command a premium ADR)
3. Risk factors and how they're mitigated

Tone: authoritative, data-driven, institutional. No fluff. This is for sophisticated investors.
Write in plain text (no markdown headers). 3 paragraphs separated by double newlines.
"""

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text  # type: ignore


async def _generate_pitch_deck(
    property_data: dict,
    financial_model: dict,
    market_narrative: str,
) -> list[dict]:
    """Returns structured content for each of the 8 pitch deck slides."""
    prompt = f"""You are creating slide content for an 8-slide STR investment pitch deck.

PROPERTY: {property_data.get('address')}, {property_data.get('city')}, {property_data.get('state')}
KEY METRICS: CoC {financial_model.get('coc_return_base')}%, Revenue ${financial_model.get('gross_revenue_base', 0):,}/yr, Price ${property_data.get('list_price', 0):,}
MARKET NARRATIVE: {market_narrative[:500]}

Return a JSON array of 8 slide objects. Each object: {{ "slide": <int>, "title": <str>, "headline": <str>, "bullets": [<str>, ...] (max 4), "callout": <str or null> }}

Slides: 1=Cover, 2=Executive Summary, 3=Market Overview, 4=Property Details, 5=Financial Scenarios, 6=Revenue Projections, 7=Highlights & Risks, 8=Next Steps

Return ONLY valid JSON array.
"""

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text  # type: ignore
    start = text.find("[")
    end = text.rfind("]") + 1
    return json.loads(text[start:end])


async def _scope_renovation(
    property_data: dict,
    property_type: str,
    renovation_budget: Optional[int],
    financial_model: dict,
) -> list[dict]:
    budget_note = f"Target budget: ${renovation_budget:,}" if renovation_budget else "No budget specified — recommend optimal scope."
    prompt = f"""You are an STR renovation specialist. Create a line-item scope of work optimized for STR revenue maximization.

PROPERTY: {property_data.get('address')} — {property_type}, {property_data.get('beds')} bed / {property_data.get('baths')} bath, {property_data.get('sqft')} sqft
{budget_note}
Current ADR target: ${financial_model.get('adr_base')}/night

Return a JSON array of renovation line items. Each item: {{ "category": <str>, "item": <str>, "estimated_cost": <int>, "roi_impact": "high"|"medium"|"low", "notes": <str> }}

Categories: Interior, Kitchen, Bathrooms, Outdoor/Pool, Tech/Smart Home, Photography/Launch, Contingency

Prioritize by STR ROI impact. Return ONLY valid JSON array.
"""

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text  # type: ignore
    start = text.find("[")
    end = text.rfind("]") + 1
    return json.loads(text[start:end])


def _determine_verdict(financial_model: dict) -> str:
    coc = financial_model.get("coc_return_base", 0)
    irr = financial_model.get("irr_base", 0)

    if coc >= 14 and irr >= 16:
        return "STRONG_BUY"
    elif coc >= 10 and irr >= 12:
        return "BUY"
    elif coc >= 6:
        return "HOLD"
    else:
        return "PASS"
