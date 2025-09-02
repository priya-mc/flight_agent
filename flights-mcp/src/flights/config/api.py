"""Duffel API configuration."""

import os
from typing import Final
from dotenv import load_dotenv

load_dotenv('/Users/pdwivedi/Documents/Projects/flight_agent/.env')

# API Constants
DUFFEL_API_URL: Final = "https://api.duffel.com"
DUFFEL_API_VERSION: Final = "v2"
DUFFEL_API_KEY: Final = os.getenv("DUFFEL_API_KEY_LIVE")

def get_api_token() -> str:
    """Get Duffel API token from environment."""
    # Try both possible environment variable names
    token = DUFFEL_API_KEY
    if not token:
        raise ValueError("DUFFEL_API_KEY_LIVE or DUFFEL_API_KEY environment variable not set")
    return token 