"""Claude API integration for marketing plan generation."""

from __future__ import annotations

import json
from typing import Optional

import anthropic

from str_researcher.models.comp import STRComp
from str_researcher.models.marketing import (
    BrandIdentity,
    ChannelStrategy,
    GuestCommunicationTemplates,
    ListingStrategy,
    MarketingPlan,
)
from str_researcher.models.property import PropertyListing
from str_researcher.models.report import ScopeOfWork
from str_researcher.models.str_performance import DualRevenueEstimate, MarketMetrics
from str_researcher.utils.logging import get_logger

logger = get_logger("marketing")


class MarketingPlanGenerator:
    """Uses Claude API to generate comprehensive marketing plans for STR properties."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate_marketing_plan(
        self,
        prop: PropertyListing,
        top_comps: list[STRComp],
        market: MarketMetrics,
        revenue: DualRevenueEstimate,
        scope: Optional[ScopeOfWork] = None,
    ) -> MarketingPlan:
        """Generate a full marketing plan for a property."""
        # Run all three sections in sequence (each is a separate Claude call)
        listing = await self._generate_listing_strategy(
            prop, top_comps, market, revenue, scope
        )
        channel = await self._generate_channel_strategy(
            prop, market, revenue, listing
        )
        brand = await self._generate_brand_identity(
            prop, market, scope, listing
        )

        plan = MarketingPlan(
            property_address=prop.full_address,
            listing_strategy=listing,
            channel_strategy=channel,
            brand_identity=brand,
        )

        logger.info("Generated marketing plan for %s", prop.full_address)
        return plan

    async def _generate_listing_strategy(
        self,
        prop: PropertyListing,
        top_comps: list[STRComp],
        market: MarketMetrics,
        revenue: DualRevenueEstimate,
        scope: Optional[ScopeOfWork] = None,
    ) -> ListingStrategy:
        """Generate listing optimization strategy."""
        comp_titles = [
            {"title": c.title[:60], "rate": c.nightly_rate_avg, "reviews": c.review_count, "score": c.review_score}
            for c in top_comps[:8]
            if c.is_top_performer
        ]

        theme_info = ""
        if scope:
            theme_info = f"""
DESIGN THEME (after renovation):
- Design Direction: {scope.design_direction}
- Theme Concept: {scope.theme_concept}
- Target Guest: {scope.target_guest_profile}
"""

        prompt = f"""You are an expert STR (short-term rental) marketing strategist specializing in Airbnb and VRBO listing optimization.

Create a listing optimization strategy for this property.

PROPERTY:
- Address: {prop.full_address}
- Beds: {prop.beds}, Baths: {prop.baths}, Sqft: {prop.sqft or 'Unknown'}
- Description: {(prop.description or 'Not available')[:400]}
{theme_info}
MARKET:
- Market: {market.market_name}
- Average ADR: ${market.adr:.0f}
- Occupancy: {market.occupancy_rate:.0%}

REVENUE TARGET:
- Moderate: ${revenue.moderate_revenue:,.0f}/year
- Top 10% target: ${revenue.aggressive_revenue:,.0f}/year
- Suggested base ADR: ${revenue.moderate_adr:.0f}

TOP COMPETITOR LISTINGS:
{json.dumps(comp_titles, indent=2)}

Provide a comprehensive listing strategy. Respond with valid JSON:
{{
    "optimized_title": "An attention-grabbing, keyword-rich listing title (max 50 chars)",
    "listing_description": "Full listing description (400-600 words, storytelling approach, highlight unique features, local attractions, guest experience)",
    "photo_shot_list": ["List of 15-20 specific photos to take with staging tips (e.g., 'Living room wide shot - afternoon light, fire lit, throws on couch')"],
    "base_nightly_rate": 0,
    "seasonal_adjustments": {{"peak_summer": 1.3, "holidays": 1.5, "shoulder": 1.0, "off_season": 0.75}},
    "weekend_premium_pct": 0.20,
    "minimum_stay_nights": 2,
    "last_minute_discount_pct": 0.10,
    "seo_keywords": ["10-15 keywords guests search for on Airbnb/VRBO"]
}}"""

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            data = self._parse_json(response.content[0].text)

            return ListingStrategy(
                optimized_title=data.get("optimized_title", ""),
                listing_description=data.get("listing_description", ""),
                photo_shot_list=data.get("photo_shot_list", []),
                base_nightly_rate=data.get("base_nightly_rate", revenue.moderate_adr),
                seasonal_adjustments=data.get("seasonal_adjustments", {}),
                weekend_premium_pct=data.get("weekend_premium_pct", 0.20),
                minimum_stay_nights=data.get("minimum_stay_nights", 2),
                last_minute_discount_pct=data.get("last_minute_discount_pct", 0.10),
                seo_keywords=data.get("seo_keywords", []),
            )
        except Exception as e:
            logger.error("Failed to generate listing strategy: %s", e)
            return ListingStrategy(
                optimized_title=f"{prop.beds}BR Home in {prop.city}",
                listing_description="Listing description unavailable.",
                base_nightly_rate=revenue.moderate_adr,
            )

    async def _generate_channel_strategy(
        self,
        prop: PropertyListing,
        market: MarketMetrics,
        revenue: DualRevenueEstimate,
        listing: ListingStrategy,
    ) -> ChannelStrategy:
        """Generate channel distribution strategy."""
        prompt = f"""You are an expert STR distribution strategist.

Create a channel distribution strategy for this property.

PROPERTY: {prop.full_address} | {prop.beds}BR/{prop.baths}BA
MARKET: {market.market_name} | ADR: ${market.adr:.0f} | Occupancy: {market.occupancy_rate:.0%}
BASE RATE: ${listing.base_nightly_rate:.0f}/night
REVENUE TARGET: ${revenue.moderate_revenue:,.0f}/year

Respond with valid JSON:
{{
    "recommended_platforms": ["Airbnb", "VRBO", "Booking.com", "Direct"],
    "primary_platform": "Airbnb",
    "pricing_by_channel": {{
        "Airbnb": "Base rate (platform handles guest service fee)",
        "VRBO": "Base rate + 3% (to offset higher host fees)",
        "Booking.com": "Base rate + 5% (15% commission)",
        "Direct": "Base rate - 8% (no platform fees, incentivize direct)"
    }},
    "channel_specific_tips": {{
        "Airbnb": ["3-5 specific optimization tips for Airbnb including Superhost strategy"],
        "VRBO": ["3-5 tips for VRBO including Premier Host"],
        "Direct": ["2-3 tips for direct booking"]
    }},
    "recommended_channel_manager": "Specific channel manager recommendation with reasoning",
    "launch_timeline": [
        "Week 1: Launch on Airbnb with introductory pricing (20% below target)",
        "Week 2-3: ...",
        "Month 2: ...",
        "Month 3+: ..."
    ]
}}"""

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
            data = self._parse_json(response.content[0].text)

            return ChannelStrategy(
                recommended_platforms=data.get("recommended_platforms", ["Airbnb", "VRBO"]),
                primary_platform=data.get("primary_platform", "Airbnb"),
                pricing_by_channel=data.get("pricing_by_channel", {}),
                channel_specific_tips=data.get("channel_specific_tips", {}),
                recommended_channel_manager=data.get("recommended_channel_manager", ""),
                launch_timeline=data.get("launch_timeline", []),
            )
        except Exception as e:
            logger.error("Failed to generate channel strategy: %s", e)
            return ChannelStrategy()

    async def _generate_brand_identity(
        self,
        prop: PropertyListing,
        market: MarketMetrics,
        scope: Optional[ScopeOfWork],
        listing: ListingStrategy,
    ) -> BrandIdentity:
        """Generate brand identity and guest communication strategy."""
        theme_info = ""
        if scope:
            theme_info = f"Theme: {scope.theme_concept}\nTarget Guest: {scope.target_guest_profile}\n"

        prompt = f"""You are an expert STR branding and guest experience strategist.

Create a complete brand identity for this property.

PROPERTY: {prop.full_address} | {prop.beds}BR/{prop.baths}BA
MARKET: {market.market_name}
LISTING TITLE: {listing.optimized_title}
{theme_info}

Respond with valid JSON:
{{
    "property_name_options": [
        {{"name": "Creative property name", "rationale": "Why this name works"}},
        {{"name": "Second option", "rationale": "Why this name works"}},
        {{"name": "Third option", "rationale": "Why this name works"}}
    ],
    "brand_voice": "Description of the brand voice and tone (2-3 sentences)",
    "messaging_pillars": ["3-4 key messaging themes"],
    "social_media_strategy": "Instagram/TikTok strategy (2-3 sentences: content types, posting cadence, hashtag strategy)",
    "content_ideas": ["8-10 specific social media content ideas with descriptions"],
    "direct_booking_site_concept": "Direct booking website concept (key pages, booking engine recommendation, 2-3 sentences)",
    "domain_suggestions": ["3 available-style domain name suggestions"],
    "guest_communications": {{
        "pre_booking_inquiry": "Template response to booking inquiries (warm, informative, 100-150 words)",
        "booking_confirmation": "Template booking confirmation message (excitement, key details, 100-150 words)",
        "pre_arrival": "Template pre-arrival message with check-in instructions and local tips (150-200 words)",
        "post_checkout_review_request": "Template post-checkout message requesting a review (warm, brief, 80-100 words)"
    }},
    "repeat_guest_strategy": "Strategy for building repeat guests (discount codes, email list, loyalty perks, 2-3 sentences)"
}}"""

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            data = self._parse_json(response.content[0].text)

            comms = data.get("guest_communications", {})
            guest_comms = GuestCommunicationTemplates(
                pre_booking_inquiry=comms.get("pre_booking_inquiry", ""),
                booking_confirmation=comms.get("booking_confirmation", ""),
                pre_arrival=comms.get("pre_arrival", ""),
                post_checkout_review_request=comms.get("post_checkout_review_request", ""),
            )

            return BrandIdentity(
                property_name_options=data.get("property_name_options", []),
                brand_voice=data.get("brand_voice", ""),
                messaging_pillars=data.get("messaging_pillars", []),
                social_media_strategy=data.get("social_media_strategy", ""),
                content_ideas=data.get("content_ideas", []),
                direct_booking_site_concept=data.get("direct_booking_site_concept", ""),
                domain_suggestions=data.get("domain_suggestions", []),
                guest_communications=guest_comms,
                repeat_guest_strategy=data.get("repeat_guest_strategy", ""),
            )
        except Exception as e:
            logger.error("Failed to generate brand identity: %s", e)
            return BrandIdentity()

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Extract and parse JSON from Claude's response."""
        json_str = text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        return json.loads(json_str.strip())
