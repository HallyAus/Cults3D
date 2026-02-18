"""Sensor platform for Cults3D integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Cults3DConfigEntry
from .const import (
    ATTRIBUTION,
    CURRENCY_EUR,
    DOMAIN,
    SENSOR_CREATIONS,
    SENSOR_FOLLOWERS,
    SENSOR_FOLLOWING,
    SENSOR_LATEST_CREATION,
    SENSOR_MONTHLY_SALES_AMOUNT,
    SENSOR_MONTHLY_SALES_COUNT,
    SENSOR_TOP_DOWNLOADED,
    SENSOR_TOTAL_SALES_AMOUNT,
    SENSOR_TOTAL_SALES_COUNT,
)
from .coordinator import Cults3DCoordinator, Cults3DData, TrackedCreationData


@dataclass(frozen=True, kw_only=True)
class Cults3DSensorEntityDescription(SensorEntityDescription):
    """Describes a Cults3D sensor entity."""

    value_fn: Callable[[Cults3DData], Any]
    extra_attrs_fn: Callable[[Cults3DData], dict[str, Any]] | None = None


# Sensors for own profile and creations
SENSOR_DESCRIPTIONS: tuple[Cults3DSensorEntityDescription, ...] = (
    # Profile stats
    Cults3DSensorEntityDescription(
        key=SENSOR_FOLLOWERS,
        translation_key=SENSOR_FOLLOWERS,
        icon="mdi:account-multiple",
        native_unit_of_measurement="followers",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.followers_count,
    ),
    Cults3DSensorEntityDescription(
        key=SENSOR_FOLLOWING,
        translation_key=SENSOR_FOLLOWING,
        icon="mdi:account-multiple-outline",
        native_unit_of_measurement="following",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.following_count,
    ),
    Cults3DSensorEntityDescription(
        key=SENSOR_CREATIONS,
        translation_key=SENSOR_CREATIONS,
        icon="mdi:cube-outline",
        native_unit_of_measurement="creations",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.creations_count,
    ),
    # Sales stats (own sales via myself query)
    Cults3DSensorEntityDescription(
        key=SENSOR_TOTAL_SALES_AMOUNT,
        translation_key=SENSOR_TOTAL_SALES_AMOUNT,
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EUR,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: round(data.total_sales_amount, 2),
    ),
    Cults3DSensorEntityDescription(
        key=SENSOR_TOTAL_SALES_COUNT,
        translation_key=SENSOR_TOTAL_SALES_COUNT,
        icon="mdi:cart",
        native_unit_of_measurement="sales",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.total_sales_count,
    ),
    Cults3DSensorEntityDescription(
        key=SENSOR_MONTHLY_SALES_AMOUNT,
        translation_key=SENSOR_MONTHLY_SALES_AMOUNT,
        icon="mdi:calendar-month",
        native_unit_of_measurement=CURRENCY_EUR,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: round(data.monthly_sales_amount, 2),
    ),
    Cults3DSensorEntityDescription(
        key=SENSOR_MONTHLY_SALES_COUNT,
        translation_key=SENSOR_MONTHLY_SALES_COUNT,
        icon="mdi:calendar-check",
        native_unit_of_measurement="sales",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.monthly_sales_count,
    ),
    # Featured creations (own)
    Cults3DSensorEntityDescription(
        key=SENSOR_LATEST_CREATION,
        translation_key=SENSOR_LATEST_CREATION,
        icon="mdi:new-box",
        value_fn=lambda data: data.latest_creation.name,
        extra_attrs_fn=lambda data: {
            "url": data.latest_creation.url,
            "image_url": data.latest_creation.image_url,
            "views": data.latest_creation.views_count,
            "downloads": data.latest_creation.downloads_count,
            "likes": data.latest_creation.likes_count,
            "published_at": data.latest_creation.published_at.isoformat()
            if data.latest_creation.published_at
            else None,
        },
    ),
    Cults3DSensorEntityDescription(
        key=SENSOR_TOP_DOWNLOADED,
        translation_key=SENSOR_TOP_DOWNLOADED,
        icon="mdi:trending-up",
        value_fn=lambda data: data.top_downloaded.name,
        extra_attrs_fn=lambda data: {
            "url": data.top_downloaded.url,
            "image_url": data.top_downloaded.image_url,
            "views": data.top_downloaded.views_count,
            "downloads": data.top_downloaded.downloads_count,
            "likes": data.top_downloaded.likes_count,
            "published_at": data.top_downloaded.published_at.isoformat()
            if data.top_downloaded.published_at
            else None,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Cults3DConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cults3D sensor entities based on a config entry."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = []

    # Add standard sensors
    entities.extend(
        Cults3DSensor(coordinator, description, entry.entry_id)
        for description in SENSOR_DESCRIPTIONS
    )

    # Add tracked creation sensors
    for slug, tracked_data in coordinator.data.tracked_creations.items():
        entities.append(
            TrackedCreationSensor(coordinator, entry.entry_id, slug, tracked_data)
        )

    async_add_entities(entities)


class Cults3DSensor(CoordinatorEntity[Cults3DCoordinator], SensorEntity):
    """Representation of a Cults3D sensor."""

    entity_description: Cults3DSensorEntityDescription
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: Cults3DCoordinator,
        description: Cults3DSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"Cults3D ({coordinator.data.username})",
            "manufacturer": "PrintForge",
            "model": "Cults3D Integration",
            "entry_type": "service",
            "configuration_url": f"https://cults3d.com/en/users/{coordinator.data.username}",
        }

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.extra_attrs_fn:
            return self.entity_description.extra_attrs_fn(self.coordinator.data)
        return None


class TrackedCreationSensor(CoordinatorEntity[Cults3DCoordinator], SensorEntity):
    """Sensor for a tracked external creation with 30-day post-release metrics.

    IMPORTANT: Actual sales data for creations you don't own is NOT available
    via the Cults3D API. This sensor provides proxy metrics (views, downloads,
    likes) which correlate with popularity but are NOT sales figures.

    The 30-day window is calculated from publishedAt to publishedAt + 30 days.
    """

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:chart-timeline-variant"

    def __init__(
        self,
        coordinator: Cults3DCoordinator,
        entry_id: str,
        slug: str,
        initial_data: TrackedCreationData,
    ) -> None:
        """Initialize the tracked creation sensor."""
        super().__init__(coordinator)
        self._slug = slug
        self._attr_unique_id = f"{entry_id}_tracked_{slug}"
        self._attr_translation_key = "tracked_creation"

        # Use a separate device for tracked creations
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_tracked")},
            "name": "Cults3D Tracked Creations",
            "manufacturer": "PrintForge",
            "model": "Cults3D Tracked Creations",
            "entry_type": "service",
            "via_device": (DOMAIN, entry_id),
        }

    @property
    def _tracked_data(self) -> TrackedCreationData | None:
        """Get the tracked creation data."""
        return self.coordinator.data.tracked_creations.get(self._slug)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        data = self._tracked_data
        if data and data.name:
            return f"Tracked: {data.name}"
        return f"Tracked: {self._slug}"

    @property
    def native_value(self) -> int | None:
        """Return the downloads count as the primary metric (proxy for popularity).

        Note: This is downloads count, NOT sales. Sales data for non-owned
        creations is not available via the Cults3D API.
        """
        data = self._tracked_data
        if data:
            return data.downloads_count
        return None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "downloads"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes with all available metrics.

        Note: All metrics are cumulative totals, not filtered to 30-day window.
        The Cults3D API does not provide date-filtered statistics for individual
        creations. The 30-day window info is provided for reference only.
        """
        data = self._tracked_data
        if not data:
            return {"error": "Creation not found"}

        attrs: dict[str, Any] = {
            "slug": data.slug,
            "name": data.name,
            "creator": data.creator,
            "url": data.url,
            "image_url": data.image_url,
            # Cumulative metrics (NOT 30-day filtered - API limitation)
            "views_total": data.views_count,
            "downloads_total": data.downloads_count,
            "likes_total": data.likes_count,
            # 30-day window info
            "published_at": data.published_at.isoformat() if data.published_at else None,
            "window_start": data.window_start.isoformat() if data.window_start else None,
            "window_end": data.window_end.isoformat() if data.window_end else None,
            "is_within_30_day_window": data.is_within_30_days,
            # Documentation
            "_note": (
                "Sales data for non-owned creations is NOT available via API. "
                "Downloads/likes shown are cumulative totals and serve as proxy "
                "metrics for popularity. The 30-day window indicates the first "
                "30 days post-release period, but metrics are NOT filtered to "
                "that window due to API limitations."
            ),
        }

        return attrs
