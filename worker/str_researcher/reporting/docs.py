"""Google Docs report builder for scope of work and marketing plans."""

from __future__ import annotations

from typing import Optional

from str_researcher.models.marketing import MarketingPlan
from str_researcher.models.report import AnalysisResult, ScopeOfWork
from str_researcher.utils.logging import get_logger

logger = get_logger("docs")


class DocsBuilder:
    """Builds Google Docs reports for scope of work and marketing plans."""

    def __init__(self, docs_service, drive_service):
        self._docs = docs_service
        self._drive = drive_service

    def create_scope_of_work_doc(
        self, result: AnalysisResult, title: Optional[str] = None
    ) -> str:
        """Create a Google Doc with the scope of work.

        Returns the document URL.
        """
        scope = result.scope_of_work
        if not scope:
            logger.warning("No scope of work for %s", result.property.full_address)
            return ""

        if title is None:
            title = f"Scope of Work - {result.property.full_address[:40]}"

        doc = self._docs.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]

        requests = self._build_scope_requests(result, scope)
        if requests:
            self._docs.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()

        url = f"https://docs.google.com/document/d/{doc_id}/edit"
        logger.info("Created scope of work doc: %s", url)
        return url

    def create_marketing_plan_doc(
        self, result: AnalysisResult, title: Optional[str] = None
    ) -> str:
        """Create a Google Doc with the marketing plan.

        Returns the document URL.
        """
        plan = result.marketing_plan
        if not plan:
            logger.warning("No marketing plan for %s", result.property.full_address)
            return ""

        if title is None:
            title = f"Marketing Plan - {result.property.full_address[:40]}"

        doc = self._docs.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]

        requests = self._build_marketing_requests(result, plan)
        if requests:
            self._docs.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()

        url = f"https://docs.google.com/document/d/{doc_id}/edit"
        logger.info("Created marketing plan doc: %s", url)
        return url

    def _build_scope_requests(
        self, result: AnalysisResult, scope: ScopeOfWork
    ) -> list[dict]:
        """Build Google Docs API requests for scope of work content."""
        requests: list[dict] = []
        idx = 1  # Current insertion index (1 = start of doc body)

        # Title
        idx = self._insert_heading(requests, idx, f"Scope of Work: {result.property.full_address}", "HEADING_1")

        # Property listing link
        if result.property.source_url:
            link_text = f"View listing on {result.property.source.title()}: {result.property.source_url}\n\n"
            idx = self._insert_text(requests, idx, link_text)

        # Investment Narrative
        if result.investment_narrative:
            idx = self._insert_heading(requests, idx, "Executive Summary", "HEADING_2")
            idx = self._insert_text(requests, idx, result.investment_narrative + "\n\n")

        # Suggested Offer
        offer = None
        for m in result.investment_metrics.values():
            if m.suggested_offer:
                offer = m.suggested_offer
                break
        if offer:
            idx = self._insert_heading(requests, idx, "Suggested Offer", "HEADING_2")
            offer_text = (
                f"Recommended Offer Price: ${offer.offer_price:,.0f} "
                f"({offer.discount_pct:.0%} below list price of "
                f"${result.property.list_price:,.0f})\n\n"
                f"{offer.rationale}\n\n"
            )
            idx = self._insert_text(requests, idx, offer_text)
            for factor, detail in offer.factors.items():
                idx = self._insert_text(requests, idx, f"• {factor}: {detail}\n")
            idx = self._insert_text(requests, idx, "\n")

        # Design Direction
        idx = self._insert_heading(requests, idx, "Design Direction", "HEADING_2")
        idx = self._insert_text(requests, idx, scope.design_direction + "\n\n")

        # Theme Concept
        idx = self._insert_heading(requests, idx, "Theme Concept", "HEADING_2")
        idx = self._insert_text(requests, idx, scope.theme_concept + "\n\n")

        # Target Guest Profile
        idx = self._insert_heading(requests, idx, "Target Guest Profile", "HEADING_2")
        idx = self._insert_text(requests, idx, scope.target_guest_profile + "\n\n")

        # Renovation Scope - grouped by priority
        idx = self._insert_heading(requests, idx, "Renovation Scope", "HEADING_2")

        for priority_label, priority_key in [
            ("Must-Have (Essential to Compete)", "must_have"),
            ("High-Impact (Significant ROI)", "high_impact"),
            ("Nice-to-Have (Enhancements)", "nice_to_have"),
        ]:
            items = [r for r in scope.recommendations if r.priority == priority_key]
            if not items:
                continue

            idx = self._insert_heading(requests, idx, priority_label, "HEADING_3")

            for item in items:
                text = (
                    f"[{item.category}] {item.recommendation}\n"
                    f"   Estimated Cost: ${item.estimated_cost_low:,.0f} - ${item.estimated_cost_high:,.0f}\n"
                    f"   Reasoning: {item.reasoning}\n\n"
                )
                idx = self._insert_text(requests, idx, text)

        # ── Purchase List (furnishing & renovation items) ──
        all_items = []
        for rec in scope.recommendations:
            for item in rec.purchase_items:
                all_items.append((rec.category, item))

        if all_items:
            idx = self._insert_heading(requests, idx, "Purchase List", "HEADING_2")
            idx = self._insert_text(
                requests, idx,
                "Complete list of items to purchase for furnishing and renovating "
                "the property. Links go to product search pages.\n\n",
            )

            # Group by category
            from collections import defaultdict
            by_category: dict[str, list] = defaultdict(list)
            for cat, item in all_items:
                by_category[cat].append(item)

            grand_total = 0.0
            for cat, items in by_category.items():
                idx = self._insert_heading(requests, idx, cat, "HEADING_3")
                cat_total = 0.0
                for item in items:
                    line_total = item.estimated_cost * item.quantity
                    cat_total += line_total
                    text = (
                        f"• {item.item_name}"
                        f"  (qty {item.quantity} × ${item.estimated_cost:,.0f}"
                        f" = ${line_total:,.0f})"
                    )
                    if item.store:
                        text += f"  — {item.store}"
                    if item.notes:
                        text += f"  [{item.notes}]"
                    text += "\n"
                    if item.product_url:
                        text += f"  Link: {item.product_url}\n"
                    idx = self._insert_text(requests, idx, text)

                idx = self._insert_text(
                    requests, idx,
                    f"  Category subtotal: ${cat_total:,.0f}\n\n",
                )
                grand_total += cat_total

            idx = self._insert_text(
                requests, idx,
                f"TOTAL PURCHASE LIST COST: ${grand_total:,.0f}\n\n",
            )

        # Amenity Gap Analysis
        if scope.amenity_gap_analysis:
            idx = self._insert_heading(requests, idx, "Amenity Gap Analysis", "HEADING_2")
            idx = self._insert_text(requests, idx, "Amenities more common in top 10% performers:\n\n")

            for am in scope.amenity_gap_analysis:
                if am.is_differentiator:
                    text = f"• {am.amenity_name}: {am.prevalence_top_pct:.0%} of top performers vs {am.prevalence_all_pct:.0%} overall\n"
                    idx = self._insert_text(requests, idx, text)
            idx = self._insert_text(requests, idx, "\n")

        # Budget Summary
        idx = self._insert_heading(requests, idx, "Budget Summary", "HEADING_2")
        budget_text = (
            f"Total Estimated Budget: ${scope.total_budget_low:,.0f} - ${scope.total_budget_high:,.0f}\n\n"
            f"Must-Have Items: ${sum(r.estimated_cost_low for r in scope.recommendations if r.priority == 'must_have'):,.0f} - "
            f"${sum(r.estimated_cost_high for r in scope.recommendations if r.priority == 'must_have'):,.0f}\n"
            f"High-Impact Items: ${sum(r.estimated_cost_low for r in scope.recommendations if r.priority == 'high_impact'):,.0f} - "
            f"${sum(r.estimated_cost_high for r in scope.recommendations if r.priority == 'high_impact'):,.0f}\n"
            f"Nice-to-Have Items: ${sum(r.estimated_cost_low for r in scope.recommendations if r.priority == 'nice_to_have'):,.0f} - "
            f"${sum(r.estimated_cost_high for r in scope.recommendations if r.priority == 'nice_to_have'):,.0f}\n"
        )
        idx = self._insert_text(requests, idx, budget_text)

        return requests

    def _build_marketing_requests(
        self, result: AnalysisResult, plan: MarketingPlan
    ) -> list[dict]:
        """Build Google Docs API requests for marketing plan content."""
        requests: list[dict] = []
        idx = 1

        # Title
        idx = self._insert_heading(requests, idx, f"Marketing Plan: {plan.property_address}", "HEADING_1")

        # Property listing link
        if result.property.source_url:
            link_text = f"View listing on {result.property.source.title()}: {result.property.source_url}\n\n"
            idx = self._insert_text(requests, idx, link_text)

        # ── Section 1: Listing Optimization ──
        ls = plan.listing_strategy
        idx = self._insert_heading(requests, idx, "1. Listing Optimization", "HEADING_2")

        idx = self._insert_heading(requests, idx, "Optimized Title", "HEADING_3")
        idx = self._insert_text(requests, idx, ls.optimized_title + "\n\n")

        idx = self._insert_heading(requests, idx, "Listing Description", "HEADING_3")
        idx = self._insert_text(requests, idx, ls.listing_description + "\n\n")

        idx = self._insert_heading(requests, idx, "Photo Shot List", "HEADING_3")
        for shot in ls.photo_shot_list:
            idx = self._insert_text(requests, idx, f"• {shot}\n")
        idx = self._insert_text(requests, idx, "\n")

        idx = self._insert_heading(requests, idx, "Pricing Strategy", "HEADING_3")
        pricing_text = (
            f"Base Nightly Rate: ${ls.base_nightly_rate:,.0f}\n"
            f"Weekend Premium: {ls.weekend_premium_pct:.0%}\n"
            f"Minimum Stay: {ls.minimum_stay_nights} nights\n"
            f"Last-Minute Discount: {ls.last_minute_discount_pct:.0%}\n\n"
            "Seasonal Adjustments:\n"
        )
        for season, mult in ls.seasonal_adjustments.items():
            pricing_text += f"  • {season}: {mult:.0%} of base rate (${ls.base_nightly_rate * mult:,.0f}/night)\n"
        idx = self._insert_text(requests, idx, pricing_text + "\n")

        idx = self._insert_heading(requests, idx, "SEO Keywords", "HEADING_3")
        idx = self._insert_text(requests, idx, ", ".join(ls.seo_keywords) + "\n\n")

        # ── Section 2: Channel Strategy ──
        cs = plan.channel_strategy
        idx = self._insert_heading(requests, idx, "2. Channel Strategy", "HEADING_2")

        idx = self._insert_heading(requests, idx, "Recommended Platforms", "HEADING_3")
        idx = self._insert_text(
            requests, idx,
            f"Primary: {cs.primary_platform}\n"
            f"All Channels: {', '.join(cs.recommended_platforms)}\n\n"
        )

        idx = self._insert_heading(requests, idx, "Pricing by Channel", "HEADING_3")
        for channel, strategy in cs.pricing_by_channel.items():
            idx = self._insert_text(requests, idx, f"• {channel}: {strategy}\n")
        idx = self._insert_text(requests, idx, "\n")

        idx = self._insert_heading(requests, idx, "Channel-Specific Tips", "HEADING_3")
        for channel, tips in cs.channel_specific_tips.items():
            idx = self._insert_text(requests, idx, f"{channel}:\n")
            for tip in tips:
                idx = self._insert_text(requests, idx, f"  • {tip}\n")
            idx = self._insert_text(requests, idx, "\n")

        if cs.recommended_channel_manager:
            idx = self._insert_heading(requests, idx, "Channel Manager", "HEADING_3")
            idx = self._insert_text(requests, idx, cs.recommended_channel_manager + "\n\n")

        idx = self._insert_heading(requests, idx, "Launch Timeline", "HEADING_3")
        for step in cs.launch_timeline:
            idx = self._insert_text(requests, idx, f"• {step}\n")
        idx = self._insert_text(requests, idx, "\n")

        # ── Section 3: Brand & Identity ──
        bi = plan.brand_identity
        idx = self._insert_heading(requests, idx, "3. Brand & Identity", "HEADING_2")

        idx = self._insert_heading(requests, idx, "Property Name Options", "HEADING_3")
        for opt in bi.property_name_options:
            name = opt.get("name", "")
            rationale = opt.get("rationale", "")
            idx = self._insert_text(requests, idx, f"• {name} — {rationale}\n")
        idx = self._insert_text(requests, idx, "\n")

        idx = self._insert_heading(requests, idx, "Brand Voice", "HEADING_3")
        idx = self._insert_text(requests, idx, bi.brand_voice + "\n\n")

        idx = self._insert_heading(requests, idx, "Messaging Pillars", "HEADING_3")
        for pillar in bi.messaging_pillars:
            idx = self._insert_text(requests, idx, f"• {pillar}\n")
        idx = self._insert_text(requests, idx, "\n")

        idx = self._insert_heading(requests, idx, "Social Media Strategy", "HEADING_3")
        idx = self._insert_text(requests, idx, bi.social_media_strategy + "\n\n")

        idx = self._insert_heading(requests, idx, "Content Ideas", "HEADING_3")
        for idea in bi.content_ideas:
            idx = self._insert_text(requests, idx, f"• {idea}\n")
        idx = self._insert_text(requests, idx, "\n")

        idx = self._insert_heading(requests, idx, "Direct Booking Website", "HEADING_3")
        idx = self._insert_text(requests, idx, bi.direct_booking_site_concept + "\n")
        if bi.domain_suggestions:
            idx = self._insert_text(requests, idx, f"Domain suggestions: {', '.join(bi.domain_suggestions)}\n\n")

        # Guest Communications
        idx = self._insert_heading(requests, idx, "Guest Communication Templates", "HEADING_3")
        gc = bi.guest_communications
        for label, template in [
            ("Pre-Booking Inquiry Response", gc.pre_booking_inquiry),
            ("Booking Confirmation", gc.booking_confirmation),
            ("Pre-Arrival Message", gc.pre_arrival),
            ("Post-Checkout Review Request", gc.post_checkout_review_request),
        ]:
            if template:
                idx = self._insert_text(requests, idx, f"\n{label}:\n")
                idx = self._insert_text(requests, idx, template + "\n")

        idx = self._insert_text(requests, idx, "\n")

        idx = self._insert_heading(requests, idx, "Repeat Guest Strategy", "HEADING_3")
        idx = self._insert_text(requests, idx, bi.repeat_guest_strategy + "\n")

        return requests

    # ── Document Building Helpers ──

    @staticmethod
    def _insert_heading(
        requests: list[dict], idx: int, text: str, style: str
    ) -> int:
        """Insert a heading and return the new index."""
        content = text + "\n"
        requests.append({
            "insertText": {"location": {"index": idx}, "text": content}
        })
        end_idx = idx + len(content)
        requests.append({
            "updateParagraphStyle": {
                "range": {"startIndex": idx, "endIndex": end_idx},
                "paragraphStyle": {"namedStyleType": style},
                "fields": "namedStyleType",
            }
        })
        return end_idx

    @staticmethod
    def _insert_text(requests: list[dict], idx: int, text: str) -> int:
        """Insert plain text and return the new index."""
        requests.append({
            "insertText": {"location": {"index": idx}, "text": text}
        })
        return idx + len(text)
