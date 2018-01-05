"""Support for MyChevy sensors."""

from logging import getLogger
from datetime import datetime as dt
from datetime import timedelta
import time
import threading

from homeassistant.components.mychevy import (
    EVSensorConfig, DOMAIN, MYCHEVY_ERROR, MYCHEVY_SUCCESS,
    NOTIFICATION_ID, NOTIFICATION_TITLE
)
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.helpers.entity import Entity
from homeassistant.util import (Throttle, slugify)


SENSORS = [
    EVSensorConfig("Mileage", "mileage", "miles", "mdi:speedometer"),
    EVSensorConfig("Range", "range", "miles", "mdi:speedometer"),
    EVSensorConfig("Charging", "charging"),
    EVSensorConfig("Charge Mode", "charge_mode"),
    EVSensorConfig("EVCharge", "percent", "%", "mdi:battery")
]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MyChevy sensors."""
    if discovery_info is None:
        return

    hub = hass.data[DOMAIN]
    sensors = [MyChevyStatus(hub)]
    for sconfig in SENSORS:
        sensors.append(EVSensor(hub, sconfig))

    add_devices(sensors)


class MyChevyStatus(Entity):
    """A string representing the charge mode."""

    _name = "MyChevy Status"
    _icon = "mdi:car-connected"

    def __init__(self, connection):
        """Initialize sensor with car connection."""
        self._state = None
        self._last_update = dt.now()
        self._conn = connection
        connection.status = self

    def success(self):
        """Update state, trigger updates."""
        if self._state != MYCHEVY_SUCCESS:
            _LOGGER.info("Successfully connected to mychevy website")
            self._state = MYCHEVY_SUCCESS
        self.schedule_update_ha_state()

    def error(self):
        """Update state, trigger updates."""
        if self._state != MYCHEVY_ERROR:
            self.hass.components.persistent_notification.create(
                "Error:<br/>Connection to mychevy website failed. "
                "This probably means the mychevy to OnStar link is down.",
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)
            self._state = MYCHEVY_ERROR
        self.schedule_update_ha_state()

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling state."""
        return False


class EVSensor(Entity):
    """Base EVSensor class.

    The only real difference between sensors is which units and what
    attribute from the car object they are returning. All logic can be
    built with just setting subclass attributes.

    """
    def __init__(self, connection, config):
        """Initialize sensor with car connection."""
        self._conn = connection
        connection.sensors.append(self)
        self.car = connection.car
        self._name = config.name
        self._attr = config.attr
        self._unit_of_measurement = config.unit_of_measurement
        self._icon = config.icon

        self.entity_id = ENTITY_ID_FORMAT.format(
            '{}_{}'.format(DOMAIN, slugify(self._name)))

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        if self.car is not None:
            return getattr(self.car, self._attr, None)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the state is expressed in."""
        return self._unit_of_measurement

    @property
    def hidden(self):
        if self.state == None:
            return True
        return False

    @property
    def should_poll(self):
        """Return the polling state."""
        return False
