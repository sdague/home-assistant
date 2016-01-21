
import json
import logging
from homeassistant.helpers.entity import Entity
import homeassistant.components.mqtt as mqtt
from homeassistant.const import (TEMP_FAHRENHEIT)
from homeassistant.util import slugify

DEPENDENCIES = ['mqtt']

DOMAIN = "arwn"
TOPIC = 'arwn/#'
SENSORS = {}

_LOGGER = logging.getLogger(__name__)


def discover_sensors(topic):
    parts = topic.split('/')
    domain = parts[1]
    if domain == "temperature":
        name = parts[2]
        return (ArwnSensor(name, 'temp', TEMP_FAHRENHEIT),)
    if domain == "barometer":
        return (ArwnSensor("Barometer", 'pressure', 'mbar'),)
    if domain == "wind":
        return (ArwnSensor("Wind Speed", 'speed', 'mph'),
                ArwnSensor("Wind Gust", 'gust', 'mph'),
                ArwnSensor("Wind Direction", 'direction', '°'))


def _slug(name):
    return "sensor.arwn_%s" % slugify(name)


def setup_platform(hass, config, add_devices, discovery_info=None):

    def sensor_event_received(topic, payload, qos):
        """When a new sensor event is received"""
        _LOGGER.info("Topic: %s => %s" % (topic, payload))

        sensors = discover_sensors(topic)
        if not sensors:
            return

        event = json.loads(payload)
        if 'timestamp' in event:
            del event['timestamp']

        for sensor in sensors:
            if sensor.name not in SENSORS:
                sensor.hass = hass
                sensor._set_event(event)
                SENSORS[sensor.name] = sensor
                _LOGGER.info("Registering new sensor %s => %s" %
                             (sensor.name, event))
                add_devices((sensor,))
            else:
                SENSORS[sensor.name]._set_event(event)
            SENSORS[sensor.name].update_ha_state()

    mqtt.subscribe(hass, TOPIC, sensor_event_received, 0)
    return True


class ArwnSensor(Entity):
    """ Represents an ARWN sensor. """

    def __init__(self, name, state_key, units):
        self.hass = None
        self.entity_id = _slug(name)
        self._name = name
        self._state_key = state_key
        self.event = {}
        self._unit_of_measurement = units

    def _set_event(self, event):
        self.event = {}
        self.event.update(event)

    @property
    def state(self):
        """ Returns the state of the device. """
        return self.event.get(self._state_key, None)

    @property
    def name(self):
        """ Get the name of the sensor. """
        return self._name

    @property
    def state_attributes(self):
        return self.event

    @property
    def unit_of_measurement(self):
        """ Unit this state is expressed in. """
        return self._unit_of_measurement

    @property
    def should_poll(self):
        return False
