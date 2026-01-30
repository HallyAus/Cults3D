"""Constants for the Cults3D integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "cults3d"

# API Configuration
CULTS3D_GRAPHQL_ENDPOINT: Final = "https://cults3d.com/graphql"

# Config keys
CONF_USERNAME: Final = "username"
CONF_API_KEY: Final = "api_key"

# Update interval (in seconds)
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=15)

# Sensor types
SENSOR_FOLLOWERS: Final = "followers"
SENSOR_FOLLOWING: Final = "following"
SENSOR_CREATIONS: Final = "creations"
SENSOR_LATEST_CREATION: Final = "latest_creation"

# Attribution
ATTRIBUTION: Final = "Data provided by Cults3D"
