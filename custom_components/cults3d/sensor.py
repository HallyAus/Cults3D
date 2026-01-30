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
    SENSOR_MOST_PROFITABLE,
    SENSOR_TOP_DOWNLOADED,
    SENSOR_TOTAL_SALES_AMOUNT,
    SENSOR_TOTAL_SALES_COUNT,
    SENSOR_TOTAL_VIEWS,
)
from .coordinator import Cults3DCoordinator, Cults3DData


@dataclass(frozen=True, kw_only=True)
class Cults3DSensorEntityDescription(SensorEntityDescription):
    """Describes a Cults3D sensor entity."""

    value_fn: Callable[[Cults3DData], Any]
    extra_attrs_fn: Callable[[Cults3DData], dict[str, Any]] | None = None


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
    Cults3DSensorEntityDescription(
        key=SENSOR_TOTAL_VIEWS,
        translation_key=SENSOR_TOTAL_VIEWS,
        icon="mdi:eye",
        native_unit_of_measurement="views",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.total_views_count,
    ),
    # Sales stats
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
    # Featured creations
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
            "sales_amount": data.latest_creation.total_sales_amount,
            "sales_count": data.latest_creation.sales_count,
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
            "sales_amount": data.top_downloaded.total_sales_amount,
            "sales_count": data.top_downloaded.sales_count,
        },
    ),
    Cults3DSensorEntityDescription(
        key=SENSOR_MOST_PROFITABLE,
        translation_key=SENSOR_MOST_PROFITABLE,
        icon="mdi:cash-multiple",
        value_fn=lambda data: data.most_profitable.name,
        extra_attrs_fn=lambda data: {
            "url": data.most_profitable.url,
            "image_url": data.most_profitable.image_url,
            "views": data.most_profitable.views_count,
            "downloads": data.most_profitable.downloads_count,
            "likes": data.most_profitable.likes_count,
            "sales_amount": data.most_profitable.total_sales_amount,
            "sales_count": data.most_profitable.sales_count,
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

    async_add_entities(
        Cults3DSensor(coordinator, description, entry.entry_id)
        for description in SENSOR_DESCRIPTIONS
    )


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
            "manufacturer": "Cults3D",
            "model": "Creator Profile",
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
