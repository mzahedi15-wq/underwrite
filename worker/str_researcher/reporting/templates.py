"""Layout and formatting definitions for Google Sheets and Docs reports."""

from __future__ import annotations

# ── Google Sheets Tab Definitions ──

SHEET_TABS = [
    "Executive Summary",
    "Monthly Cashflow",
    "Financing Scenarios",
    "Sensitivity Analysis",
    "Purchase Comps",
    "STR Comps",
    "Amenity Matrix",
    "Revenue Scenarios",
]

# Column definitions for each tab
EXECUTIVE_SUMMARY_LAYOUT = {
    "headers": [
        "Metric", "Value",
    ],
    "rows": [
        "Address", "List Price", "Beds / Baths", "Sqft", "Year Built",
        "", "--- Revenue Estimates ---",
        "Conservative Revenue", "Moderate Revenue", "Aggressive Revenue",
        "Moderate ADR", "Moderate Occupancy",
        "", "--- Best Financing Scenario ---",
        "Financing Type", "Down Payment", "Monthly Payment",
        "Cash-on-Cash Return", "Cap Rate", "DSCR",
        "Break-even Occupancy",
        "", "--- Investment ---",
        "Investment Score", "Investment Rank",
    ],
}

MONTHLY_CASHFLOW_HEADERS = [
    "Month", "Revenue", "Occupancy",
    "Management Fee", "Cleaning", "Platform Fees",
    "Property Tax", "Insurance", "HOA", "Utilities",
    "Maintenance", "Mortgage", "Vacancy Reserve",
    "Total Expenses", "Net Cashflow",
]

FINANCING_SCENARIO_HEADERS = [
    "Metric", "Conventional", "DSCR", "Cash",
]

FINANCING_ROWS = [
    "Down Payment %", "Down Payment $", "Interest Rate",
    "Loan Amount", "Monthly Payment",
    "Closing Costs", "Renovation & Furnishing",
    "Total Cash Needed",
    "", "--- Annual Returns ---",
    "Gross Revenue", "Total Expenses", "NOI",
    "Annual Debt Service", "Cash Flow",
    "Cap Rate", "Cash-on-Cash Return", "DSCR",
    "Break-even Occupancy",
    "", "--- Suggested Offer ---",
    "Suggested Offer Price", "Offer Rationale",
]

PURCHASE_COMP_HEADERS = [
    "Address", "Sale Price", "Beds", "Baths", "Sqft",
    "Sale Date", "Distance (mi)", "Adjustments", "Adjusted Price",
]

STR_COMP_HEADERS = [
    "Title", "Platform", "Beds", "Avg Nightly Rate",
    "Est. Annual Revenue", "Review Score", "Reviews",
    "Superhost", "Top 10%", "Key Amenities",
]

AMENITY_MATRIX_HEADERS = [
    "Amenity", "Top 10% Have It", "All Comps Have It",
    "Gap", "Differentiator?",
]

REVENUE_SCENARIO_HEADERS = [
    "Source / Scenario", "Annual Revenue", "ADR", "Occupancy",
    "Monthly Projections (Jan-Dec)",
]

# ── Color Palette ──

COLORS = {
    "header_bg": {"red": 0.2, "green": 0.4, "blue": 0.6},
    "header_text": {"red": 1.0, "green": 1.0, "blue": 1.0},
    "good": {"red": 0.85, "green": 0.95, "blue": 0.85},
    "moderate": {"red": 1.0, "green": 0.95, "blue": 0.8},
    "poor": {"red": 1.0, "green": 0.85, "blue": 0.85},
    "section_divider": {"red": 0.9, "green": 0.9, "blue": 0.9},
    "top_performer": {"red": 0.85, "green": 0.95, "blue": 0.85},
}

# ── Google Docs Section Templates ──

SCOPE_OF_WORK_SECTIONS = [
    "Executive Summary",
    "Design Direction",
    "Theme Concept",
    "Target Guest Profile",
    "Renovation Scope",
    "Amenity Recommendations",
    "Budget Summary",
]

MARKETING_PLAN_SECTIONS = [
    "Listing Optimization",
    "Channel Strategy",
    "Brand & Identity",
]

# ── Master Ranking Sheet ──

RANKING_HEADERS = [
    "Rank", "Address", "Price", "Beds", "Baths",
    "Moderate Revenue", "Aggressive Revenue",
    "Best CoC", "Cap Rate", "Investment Score",
    "Listing URL", "Report Link", "Scope Doc Link", "Marketing Doc Link",
]
