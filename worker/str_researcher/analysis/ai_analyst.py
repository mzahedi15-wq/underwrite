"""Claude API integration for AI-powered analysis, scope of work, and narratives."""

from __future__ import annotations

import json
from typing import Optional

import anthropic

from str_researcher.models.comp import AmenityMatrix, STRComp
from str_researcher.models.property import PropertyListing
from str_researcher.models.report import DesignRecommendation, PurchaseItem, ScopeOfWork
from str_researcher.models.str_performance import DualRevenueEstimate, MarketMetrics
from str_researcher.utils.logging import get_logger

logger = get_logger("ai_analyst")


class AIAnalyst:
    """Uses Claude API for design recommendations and investment narratives."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate_scope_of_work(
        self,
        prop: PropertyListing,
        top_comps: list[STRComp],
        amenity_matrix: list[AmenityMatrix],
        market: MarketMetrics,
        revenue: DualRevenueEstimate,
    ) -> ScopeOfWork:
        """Generate a detailed scope of work using Claude."""
        # Build context for Claude
        top_amenities = [
            a for a in amenity_matrix if a.is_differentiator or a.prevalence_top_pct > 0.5
        ]
        top_comp_summary = [
            {
                "title": c.title[:50],
                "beds": c.beds,
                "rate": c.nightly_rate_avg,
                "revenue": c.annual_revenue_est,
                "score": c.review_score,
                "reviews": c.review_count,
                "amenities": c.amenities[:15],
                "superhost": c.superhost,
            }
            for c in top_comps[:10]
            if c.is_top_performer
        ]

        prompt = f"""You are an expert STR (short-term rental) consultant specializing in property design and renovation for maximum rental performance.

Analyze this property and the competitive landscape to create a detailed renovation scope of work with a specific purchase list.

SUBJECT PROPERTY:
- Address: {prop.full_address}
- Listing: {prop.source_url}
- Beds: {prop.beds}, Baths: {prop.baths}, Sqft: {prop.sqft or 'Unknown'}
- Year Built: {prop.year_built or 'Unknown'}
- List Price: ${prop.list_price:,}
- Description: {(prop.description or 'Not available')[:500]}

MARKET CONTEXT:
- Market: {market.market_name}
- Average ADR: ${market.adr:.0f}
- Average Occupancy: {market.occupancy_rate:.0%}
- Revenue Estimate (moderate): ${revenue.moderate_revenue:,.0f}
- Top 10% Revenue: ${revenue.aggressive_revenue:,.0f}

TOP PERFORMING COMPS (what we're competing against):
{json.dumps(top_comp_summary, indent=2)}

KEY DIFFERENTIATING AMENITIES (much more common in top 10%):
{json.dumps([{{"name": a.amenity_name, "top_pct": f"{a.prevalence_top_pct:.0%}", "all_pct": f"{a.prevalence_all_pct:.0%}"}} for a in top_amenities[:15]], indent=2)}

Based on this data, provide:

1. DESIGN DIRECTION: A clear design theme and style direction for this property (2-3 sentences)
2. THEME CONCEPT: A specific, memorable theme concept name and description
3. TARGET GUEST PROFILE: Who is the ideal guest for this property
4. RECOMMENDATIONS: A list of specific renovation and design items, each with:
   - category: "Interior", "Amenity", "Outdoor", or "Theme"
   - recommendation: Specific actionable item
   - estimated_cost_low: Low end cost estimate in dollars
   - estimated_cost_high: High end cost estimate in dollars
   - priority: "must_have" (essential to compete), "high_impact" (significant ROI), or "nice_to_have"
   - reasoning: Why this matters based on the comp data
   - purchase_items: A specific list of items to purchase for this recommendation.
     For each item include:
     - item_name: Exact product description (e.g., "King Size Platform Bed Frame - Solid Wood")
     - quantity: How many to buy (based on {prop.beds} bedrooms, {prop.baths} bathrooms)
     - estimated_cost: Price per unit in dollars
     - product_url: A real Amazon or Wayfair search URL for the item.
       Use format: "https://www.amazon.com/s?k=<search+terms>" or "https://www.wayfair.com/keyword.html?keyword=<search+terms>"
     - store: "Amazon", "Wayfair", "Home Depot", "Costco", etc.
     - notes: Size, color, or style notes

IMPORTANT: The purchase_items should be a COMPLETE furnishing list — everything needed to
make this property guest-ready. Include ALL furniture (beds, mattresses, nightstands, dressers,
sofas, dining table/chairs, TV stands), ALL linens (sheets, towels, pillows, comforters),
ALL kitchen essentials (cookware, dishes, utensils, appliances), bathroom essentials,
décor, and any amenity-specific items (hot tub, fire pit, game room equipment, etc.).
The total cost of purchase_items should roughly match the estimated_cost_low to estimated_cost_high range.

Include 12-18 recommendations covering interior design, amenity additions, outdoor improvements,
and unique experience elements. Be thorough on purchase items — an investor should be able to
use this as a shopping list.

Respond with valid JSON in this exact format:
{{
    "design_direction": "...",
    "theme_concept": "...",
    "target_guest_profile": "...",
    "recommendations": [
        {{
            "category": "...",
            "recommendation": "...",
            "estimated_cost_low": 0,
            "estimated_cost_high": 0,
            "priority": "must_have|high_impact|nice_to_have",
            "reasoning": "...",
            "purchase_items": [
                {{
                    "item_name": "...",
                    "quantity": 1,
                    "estimated_cost": 0,
                    "product_url": "https://www.amazon.com/s?k=...",
                    "store": "Amazon",
                    "notes": "..."
                }}
            ]
        }}
    ]
}}"""

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=16000,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

            # Extract JSON from response
            json_str = content
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            recommendations = []
            for r in data.get("recommendations", []):
                # Parse purchase items if present
                items = []
                for item_data in r.pop("purchase_items", []):
                    try:
                        items.append(PurchaseItem(**item_data))
                    except Exception:
                        pass  # Skip malformed items
                rec = DesignRecommendation(**r, purchase_items=items)
                recommendations.append(rec)

            scope = ScopeOfWork(
                design_direction=data.get("design_direction", ""),
                theme_concept=data.get("theme_concept", ""),
                target_guest_profile=data.get("target_guest_profile", ""),
                recommendations=recommendations,
                amenity_gap_analysis=top_amenities,
            )
            scope.calculate_totals()

            logger.info(
                "Generated scope of work: %d recommendations, budget $%s-$%s",
                len(recommendations),
                f"{scope.total_budget_low:,.0f}",
                f"{scope.total_budget_high:,.0f}",
            )

            return scope

        except Exception as e:
            logger.error("Failed to generate scope of work: %s", e)
            return ScopeOfWork(
                design_direction="Analysis unavailable",
                theme_concept="N/A",
                target_guest_profile="N/A",
            )

    async def generate_investment_narrative(
        self,
        prop: PropertyListing,
        revenue: DualRevenueEstimate,
        market: MarketMetrics,
        best_coc: float,
        cap_rate: float,
        score: float,
    ) -> str:
        """Generate a 2-3 paragraph investment thesis."""
        prompt = f"""Write a concise 2-3 paragraph investment thesis for this short-term rental property.

Property: {prop.full_address}
Price: ${prop.list_price:,} | {prop.beds}BR/{prop.baths}BA | {prop.sqft or 'N/A'} sqft
Market: {market.market_name}
Revenue Estimate: ${revenue.moderate_revenue:,.0f}/year (moderate)
Revenue Range: ${revenue.conservative_revenue:,.0f} - ${revenue.aggressive_revenue:,.0f}
Cash-on-Cash Return: {best_coc:.1%}
Cap Rate: {cap_rate:.1%}
Investment Score: {score:.0f}/100
Market ADR: ${market.adr:.0f} | Occupancy: {market.occupancy_rate:.0%}
{"Revenue estimates diverge significantly - exercise caution" if revenue.needs_manual_review else ""}

Be direct, data-driven, and mention specific numbers. Include both the opportunity and key risks. Do not use headers or bullet points — write flowing paragraphs."""

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()

        except Exception as e:
            logger.error("Failed to generate narrative: %s", e)
            return "Investment narrative unavailable."
