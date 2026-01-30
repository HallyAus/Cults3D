"""Constants for the Cults3D integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "cults3d"

# API Configuration
CULTS3D_GRAPHQL_ENDPOINT: Final = "https://cults3d.com/graphql"

# Config keys
CONF_USERNAME: Final = "username"
CONF_API_KEY: Final = "api_key"
CONF_TRACKED_CREATIONS: Final = "tracked_creations"

# Update interval
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=15)

# Sensor types - Profile stats
SENSOR_FOLLOWERS: Final = "followers"
SENSOR_FOLLOWING: Final = "following"
SENSOR_CREATIONS: Final = "creations"

# Sensor types - Sales stats (own sales via myself query)
SENSOR_TOTAL_SALES_AMOUNT: Final = "total_sales_amount"
SENSOR_TOTAL_SALES_COUNT: Final = "total_sales_count"
SENSOR_MONTHLY_SALES_AMOUNT: Final = "monthly_sales_amount"
SENSOR_MONTHLY_SALES_COUNT: Final = "monthly_sales_count"

# Sensor types - Featured creations (own)
SENSOR_LATEST_CREATION: Final = "latest_creation"
SENSOR_TOP_DOWNLOADED: Final = "top_downloaded"
SENSOR_TOP_VIEWED: Final = "top_viewed"

# Sensor types - Tracked creations (external)
SENSOR_TRACKED_CREATION: Final = "tracked_creation"

# Attribution
ATTRIBUTION: Final = "Data provided by Cults3D"

# Currency (Cults3D uses EUR)
CURRENCY_EUR: Final = "EUR"
