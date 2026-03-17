"""Marketing plan data models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ListingStrategy(BaseModel):
    """Listing optimization strategy for STR platforms."""

    optimized_title: str
    listing_description: str
    photo_shot_list: list[str] = Field(default_factory=list)
    base_nightly_rate: float
    seasonal_adjustments: dict[str, float] = Field(
        default_factory=dict
    )  # e.g. {"summer": 1.3, "winter": 0.8}
    weekend_premium_pct: float = 0.20
    minimum_stay_nights: int = 2
    last_minute_discount_pct: float = 0.10
    seo_keywords: list[str] = Field(default_factory=list)


class ChannelStrategy(BaseModel):
    """Multi-channel distribution strategy."""

    recommended_platforms: list[str] = Field(
        default_factory=lambda: ["Airbnb", "VRBO"]
    )
    primary_platform: str = "Airbnb"
    pricing_by_channel: dict[str, str] = Field(
        default_factory=dict
    )  # e.g. {"Airbnb": "base", "Direct": "-5%"}
    channel_specific_tips: dict[str, list[str]] = Field(default_factory=dict)
    recommended_channel_manager: str = ""
    launch_timeline: list[str] = Field(default_factory=list)


class GuestCommunicationTemplates(BaseModel):
    """Templates for guest communication at each touchpoint."""

    pre_booking_inquiry: str = ""
    booking_confirmation: str = ""
    pre_arrival: str = ""
    post_checkout_review_request: str = ""


class BrandIdentity(BaseModel):
    """Brand and identity strategy for the property."""

    property_name_options: list[dict[str, str]] = Field(
        default_factory=list
    )  # [{"name": "...", "rationale": "..."}]
    brand_voice: str = ""
    messaging_pillars: list[str] = Field(default_factory=list)
    social_media_strategy: str = ""
    content_ideas: list[str] = Field(default_factory=list)
    direct_booking_site_concept: str = ""
    domain_suggestions: list[str] = Field(default_factory=list)
    guest_communications: GuestCommunicationTemplates = Field(
        default_factory=GuestCommunicationTemplates
    )
    repeat_guest_strategy: str = ""


class MarketingPlan(BaseModel):
    """Complete marketing plan for an STR property."""

    property_address: str
    listing_strategy: ListingStrategy
    channel_strategy: ChannelStrategy
    brand_identity: BrandIdentity
