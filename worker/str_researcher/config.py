"""Configuration management using Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env early, overriding empty shell env vars
_env_file = Path(__file__).parent.parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file, override=True)


CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class RegionConfig(BaseModel):
    name: str
    center_lat: float
    center_lng: float
    radius_miles: float = 15.0
    zillow_search_url: str = ""
    redfin_search_url: str = ""
    min_beds: int = 1
    max_beds: int = 10
    min_price: int = 0
    max_price: int = 5_000_000
    property_types: list[str] = Field(
        default_factory=lambda: ["single_family", "cabin", "condo", "townhouse"]
    )


class FinancingConfig(BaseModel):
    conventional_down_pct: float = 0.20
    conventional_rate: float = 0.07
    conventional_term_years: int = 30
    dscr_down_pct: float = 0.25
    dscr_rate: float = 0.08
    dscr_term_years: int = 30
    closing_cost_pct: float = 0.03


class CostAssumptions(BaseModel):
    property_tax_rate: float = 0.01
    insurance_annual: float = 2400.0
    hoa_monthly: float = 0.0
    utilities_monthly: float = 300.0
    management_fee_pct: float = 0.20
    maintenance_pct: float = 0.05
    furnishing_per_bed: float = 5000.0
    cleaning_per_turn: float = 150.0
    platform_fee_pct: float = 0.03
    vacancy_buffer_pct: float = 0.05


class ScoringWeights(BaseModel):
    cash_on_cash: float = 0.25
    cap_rate: float = 0.20
    revenue_upside: float = 0.20
    renovation_efficiency: float = 0.15
    market_strength: float = 0.10
    entry_price_vs_comps: float = 0.10


class APIKeys(BaseSettings):
    airdna_api_key: str = ""
    anthropic_api_key: str = ""
    google_credentials_path: str = "credentials.json"
    proxy_url: Optional[str] = None

    model_config = SettingsConfigDict(env_file_encoding="utf-8")


class AppConfig(BaseModel):
    region: RegionConfig
    financing: FinancingConfig = FinancingConfig()
    costs: CostAssumptions = CostAssumptions()
    scoring_weights: ScoringWeights = ScoringWeights()
    api_keys: APIKeys = Field(default_factory=APIKeys)
    cache_ttl_hours: int = 24
    max_listings_to_analyze: int = 50
    top_performer_percentile: float = 0.90
    top_n_for_full_reports: int = 5
    revenue_blend_airdna_weight: float = 0.50
    revenue_blend_comp_weight: float = 0.50


def load_defaults() -> dict:
    """Load default configuration from defaults.yaml."""
    defaults_path = CONFIG_DIR / "defaults.yaml"
    if defaults_path.exists():
        with open(defaults_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def load_region_config(region_name: str) -> dict:
    """Load a region-specific configuration file."""
    regions_dir = CONFIG_DIR / "regions"
    for yaml_file in regions_dir.glob("*.yaml"):
        with open(yaml_file) as f:
            data = yaml.safe_load(f) or {}
            region = data.get("region", {})
            if region.get("name", "").lower() == region_name.lower():
                return data
    raise FileNotFoundError(f"No region config found for '{region_name}'")


def list_available_regions() -> list[str]:
    """List all available region configuration names."""
    regions_dir = CONFIG_DIR / "regions"
    regions = []
    if regions_dir.exists():
        for yaml_file in regions_dir.glob("*.yaml"):
            with open(yaml_file) as f:
                data = yaml.safe_load(f) or {}
                region = data.get("region", {})
                name = region.get("name")
                if name:
                    regions.append(name)
    return regions


def build_config(region_name: str) -> AppConfig:
    """Build a complete AppConfig by merging defaults with region-specific overrides."""
    defaults = load_defaults()
    region_data = load_region_config(region_name)

    # Start with defaults
    config_dict: dict = {}

    # Apply default financing
    config_dict["financing"] = defaults.get("financing", {})

    # Apply default costs, then override with region costs
    default_costs = defaults.get("costs", {})
    region_costs = region_data.get("costs", {})
    config_dict["costs"] = {**default_costs, **region_costs}

    # Scoring weights
    config_dict["scoring_weights"] = defaults.get("scoring_weights", {})

    # Region config
    config_dict["region"] = region_data["region"]

    # Top-level settings from defaults
    for key in [
        "cache_ttl_hours",
        "max_listings_to_analyze",
        "top_performer_percentile",
        "top_n_for_full_reports",
        "revenue_blend_airdna_weight",
        "revenue_blend_comp_weight",
    ]:
        if key in defaults:
            config_dict[key] = defaults[key]

    # API keys loaded from environment
    config_dict["api_keys"] = APIKeys()

    return AppConfig(**config_dict)
