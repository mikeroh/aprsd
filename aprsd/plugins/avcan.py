import json
import logging
import re

from oslo_config import cfg
#import requests

from aprsd import plugin, plugin_utils
from aprsd.utils import trace


CONF = cfg.CONF
LOG = logging.getLogger("APRSD")


class AvcanPlugin(plugin.APRSDRegexCommandPluginBase):
    """Avalanceh Canada Forecast Command

    This provides avalanche forecast data  near the caller or callsign.

    How to Call: Send a message to aprsd
    "avcan" - returns the avalanche forecast near the calling callsign
    "avcan CALLSIGN" - returns the avalanceh forecast near CALLSIGN

    This plugin uses the avalanche canada API to fetch
    location and weather information.

    """

    command_regex = r"^([a][v]|[a][v]\s|avcan)"
    command_name = "avcan"
    short_description = "Avalanche Canada forecast"

    def setup(self):
        self.enabled = True

    def help(self):
        _help = [
            "avcan: Send {} to get weather "
            "from your location".format(self.command_regex),
            "avcan: Send {} <callsign> to get "
            "weather from <callsign>".format(self.command_regex),
        ]
        return _help

    @trace.trace
    def process(self, packet):
        fromcall = packet.get("from")
        message = packet.get("message_text", None)
        # ack = packet.get("msgNo", "0")
        LOG.info(f"Avcan Plugin '{message}'")
        a = re.search(r"^.*\s+(.*)", message)
        if a is not None:
            searchcall = a.group(1)
            searchcall = searchcall.upper()
        else:
            searchcall = fromcall

        api_key = CONF.aprs_fi.apiKey

        try:
            aprs_data = plugin_utils.get_aprs_fi(api_key, searchcall)
        except Exception as ex:
            LOG.error(f"Failed to fetch aprs.fi data {ex}")
            return "Failed to fetch location"

        # LOG.debug("LocationPlugin: aprs_data = {}".format(aprs_data))
        if not len(aprs_data["entries"]):
            LOG.error("Found no entries from aprs.fi!")
            return "Failed to fetch location"

        lat = aprs_data["entries"][0]["lat"]
        lon = aprs_data["entries"][0]["lng"]

        try:
            av_data = plugin_utils.fetch_avcan(
                lat,
                lon,
            )
        except Exception as ex:
            LOG.error(f"Couldn't fetch avcan api '{ex}'")
            return "Unable to get avalanche forecast"

        LOG.info("AvcanPlugin: av_data = {}".format(av_data))

        if "id" in av_data:
            today = "{} alp:{}, tl:{}, btl:{}".format(
                av_data["report"]["dangerRatings"][0]["date"]["display"],
                av_data["report"]["dangerRatings"][0]["ratings"]["alp"]["rating"]["value"],
                av_data["report"]["dangerRatings"][0]["ratings"]["tln"]["rating"]["value"],
                av_data["report"]["dangerRatings"][0]["ratings"]["btl"]["rating"]["value"],
            )
        else:
            return "No forecast for {},{}".format(lat,lon)

        # # LOG.debug(wx_data["current"])
        # # LOG.debug(wx_data["daily"])
        # reply = "{} {:.1f}{}/{:.1f}{} Wind {} {}%".format(
        #     wx_data["current"]["weather"][0]["description"],
        #     wx_data["current"]["temp"],
        #     degree,
        #     wx_data["current"]["dew_point"],
        #     degree,
        #     wind,
        #     wx_data["current"]["humidity"],
        # )

        return today
