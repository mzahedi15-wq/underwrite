"""Settings page - API keys and configuration management."""

from pathlib import Path

import streamlit as st
import yaml

from str_researcher.config import CONFIG_DIR


st.title("Settings")

# API Keys
st.header("API Keys")
st.caption("API keys are stored in the .env file in the project root.")

env_path = Path(__file__).parent.parent.parent.parent / ".env"
env_exists = env_path.exists()

if env_exists:
    st.success(".env file found")
else:
    st.warning(".env file not found. Create one from .env.example")

with st.expander("Edit API Keys", expanded=not env_exists):
    airdna_key = st.text_input("AirDNA API Key", type="password", key="airdna")
    anthropic_key = st.text_input("Anthropic API Key", type="password", key="anthropic")
    google_creds = st.text_input(
        "Google Credentials Path",
        value="credentials.json",
        key="google_creds",
    )
    proxy_url = st.text_input(
        "Proxy URL (optional)",
        placeholder="http://user:pass@proxy:8080",
        key="proxy",
    )

    if st.button("Save API Keys"):
        lines = []
        if airdna_key:
            lines.append(f"AIRDNA_API_KEY={airdna_key}")
        if anthropic_key:
            lines.append(f"ANTHROPIC_API_KEY={anthropic_key}")
        if google_creds:
            lines.append(f"GOOGLE_CREDENTIALS_PATH={google_creds}")
        if proxy_url:
            lines.append(f"PROXY_URL={proxy_url}")

        if lines:
            env_path.write_text("\n".join(lines) + "\n")
            st.success("API keys saved to .env")
        else:
            st.warning("No keys to save")

st.divider()

# Google Authentication
st.header("Google Authentication")
st.caption("Required for Google Sheets & Docs report generation.")

from str_researcher.reporting.google_auth import GoogleAuthManager, TOKEN_PATH

google_creds_path = Path(
    st.session_state.get("google_creds", "credentials.json")
)
token_exists = TOKEN_PATH.exists()

if token_exists:
    st.success("✅ Google account connected — reports will be generated automatically.")
    if st.button("Re-authenticate Google Account"):
        try:
            TOKEN_PATH.unlink(missing_ok=True)
            auth = GoogleAuthManager(str(google_creds_path))
            auth.authenticate(interactive=True)
            st.success("Re-authenticated successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Authentication failed: {e}")
else:
    st.warning("Not connected — report generation will be skipped during analysis.")
    if google_creds_path.exists():
        if st.button("Connect Google Account", type="primary"):
            try:
                auth = GoogleAuthManager(str(google_creds_path))
                auth.authenticate(interactive=True)
                st.success("Connected! Google Sheets & Docs reports will now be generated.")
                st.rerun()
            except Exception as e:
                st.error(f"Authentication failed: {e}")
    else:
        st.info(
            f"Google credentials file not found at `{google_creds_path}`. "
            "Download OAuth client credentials from Google Cloud Console and "
            "save as `credentials.json` in the project root."
        )

st.divider()

# Region Management
st.header("Saved Regions")

regions_dir = CONFIG_DIR / "regions"
if regions_dir.exists():
    region_files = list(regions_dir.glob("*.yaml"))
    if region_files:
        for rf in region_files:
            with open(rf) as f:
                data = yaml.safe_load(f) or {}
            region = data.get("region", {})
            name = region.get("name", rf.stem)

            with st.expander(f"{name} ({rf.name})"):
                st.json(data)
    else:
        st.info("No region configs found. Add YAML files to config/regions/")
else:
    st.info("config/regions/ directory not found.")

st.divider()

# Default Configuration
st.header("Default Configuration")
defaults_path = CONFIG_DIR / "defaults.yaml"
if defaults_path.exists():
    with open(defaults_path) as f:
        defaults = yaml.safe_load(f) or {}
    with st.expander("View/Edit defaults.yaml"):
        st.json(defaults)
else:
    st.warning("defaults.yaml not found.")
