"""
Support for WUnderground weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.wunderground/
"""
from datetime import timedelta
import json
import logging

import re
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD
    )
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

import websocket

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)
SCAN_INTERVAL = timedelta(seconds=10)
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_4) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/42.0.2311.90 Safari/537.36")
WF_LOGIN_URL = 'https://symphony.mywaterfurnace.com/account/login'

class WFSensorConfig(object):
    """Water Furnace Sensor configuration."""

SENSORS = [

]

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the WUnderground sensor."""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    unit = config.get("unit")

    rest = WaterFurnaceData(
        hass, username, password, unit)
    sensors = []
    sensors.append(WaterFurnaceSensor(rest, "mode"))
    sensors.append(WaterFurnaceSensor(rest, "totalunitpower", "W"))
    sensors.append(WaterFurnaceSensor(rest, "tstatactivesetpoint", "F"))

    rest.update()
    if not rest.data:
        raise PlatformNotReady

    add_devices(sensors)
    return True

FURNACE_MODE = (
    'Standby',
    'Fan Only',
    'Cooling 1',
    'Cooling 2',
    'Reheat',
    'Heating 1',
    'Heating 2',
    'E-Heat',
    'Aux Heat',
    'Lockout')

class FurnaceReading(object):

    def __init__(self, data={}):
        self.zone = data.get('zone', 0)
        self.err = data.get('err', '')
        self.awlid = data.get('awlid', '')
        self.tid = data.get('tid', 0)

        # power (Watts)
        self.compressorpower = data.get('compressorpower', 0)
        self.fanpower = data.get('fanpower', 0)
        self.auxpower = data.get('auxpower', 0)
        self.looppumppower = data.get('looppumppower', 0)
        self.totalunitpower = data.get('totalunitpower', 0)

        # modes (0 - 10)
        self.modeofoperation = data.get('modeofoperation', 0)

        # fan speed (0 - 10)
        self.airflowcurrentspeed = data.get('airflowcurrentspeed', 0)

        # humidity (%)
        self.tstatdehumidsetpoint = data.get('tstatdehumidsetpoint', 0)
        self.tstathumidsetpoint = data.get('tstathumidsetpoint', 0)
        self.tstatrelativehumidity = data.get('tstatrelativehumidity', 0)

        # temps (degrees F)
        self.leavingairtemp = data.get('leavingairtemp', 0)
        self.tstatroomtemp = data.get('tstatroomtemp', 0)
        self.enteringwatertemp = data.get('enteringwatertemp', 0)

        # setpoints (degrees F)
        self.tstatheatingsetpoint = data.get('tstatheatingsetpoint', 0)
        self.tstatcoolingsetpoint = data.get('tstatcoolingsetpoint', 0)
        self.tstatactivesetpoint = data.get('tstatactivesetpoint', 0)

    @property
    def mode(self):
        return FURNACE_MODE[self.modeofoperation]

    def __str__(self):
        return ("<FurnaceReading power=%d, mode=%s, looptemp=%.1f, "
                "airtemp=%.1f, roomtemp=%.1f, setpoint=%d>" % (
                    self.totalunitpower,
                    self.mode,
                    self.enteringwatertemp,
                    self.leavingairtemp,
                    self.tstatroomtemp,
                    self.tstatactivesetpoint))


class WaterFurnaceSensor(Entity):
    """Implementing the WUnderground sensor."""

    def __init__(self, rest, attr, unit=None):
        """Initialize the sensor."""
        self.rest = rest
        self._attr = attr
        self._state = None
        self._icon = None
        self._entity_picture = None
        self._attributes = {}
        self._unit_of_measurement = unit

    @property
    def name(self):
        """Return the name of the sensor."""
        return "WF_" + self._attr

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Return icon."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity picture."""
        return self._entity_picture

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Update current conditions."""
        self.rest.update()

        if not self.rest.data:
            # no data, return
            return

        self._state = getattr(self.rest.data, self._attr, None)


class WaterFurnaceData(object):
    def __init__(self, hass, user, passwd, unit):
        """Initialize the data object."""
        self._hass = hass
        self._user = user
        self._passwd = passwd
        self._unit = unit
        self.data = None
        self.session_id = None
        self.login()

    def _get_session_id(self):
        data = dict(emailaddress=self._user, password=self._passwd, op="login")
        headers = {"user-agent": USER_AGENT}
        res = requests.post(WF_LOGIN_URL, data=data, headers=headers,
                            allow_redirects=False)
        self.sessionid = res.cookies["sessionid"]

    def _login_ws(self):
        self.ws = websocket.create_connection(
            "wss://awlclientproxy.mywaterfurnace.com/")
        login = {"cmd": "login", "tid": 2, "source": "consumer dashboard",
                 "sessionid": self.sessionid}
        self.ws.send(json.dumps(login))
        data = self.ws.recv()

    def login(self):
        self._get_session_id()
        self._login_ws()

    def read(self):
        req = {
            "cmd": "read",
            "tid": 3,
            "awlid": self._unit,
            "zone": 0,
            "rlist": ["compressorpower","fanpower","auxpower","looppumppower",
                      "totalunitpower","AWLABCType","ModeOfOperation",
                      "ActualCompressorSpeed","AirflowCurrentSpeed",
                      "AuroraOutputEH1","AuroraOutputEH2","AuroraOutputCC",
                      "AuroraOutputCC2","TStatDehumidSetpoint", "TStatHumidSetpoint",
                      "TStatRelativeHumidity","LeavingAirTemp","TStatRoomTemp",
                      "EnteringWaterTemp","AOCEnteringWaterTemp",
                      "lockoutstatus","lastfault","lastlockout",
                      "humidity_offset_settings","humidity","outdoorair",
                      "homeautomationalarm1","homeautomationalarm2","roomtemp",
                      "activesettings","TStatActiveSetpoint","TStatMode",
                      "TStatHeatingSetpoint","TStatCoolingSetpoint",
                      "AWLTStatType"],
            "source":"consumer dashboard"}
        self.ws.send(json.dumps(req))
        data = self.ws.recv()
        datadecoded = json.loads(data)
        self.data = FurnaceReading(datadecoded)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Symphony websocket."""
        try:
            # self.login()
            self.read()
            return True
        except ConnectionError as err:
            self.login()
            _LOGGER.error("Lost our connection, trying again")
            self.data = None
        except requests.RequestException as err:
            self.login()
            _LOGGER.error("Error fetching Waterfurnace data: %s", repr(err))
            self.data = None
