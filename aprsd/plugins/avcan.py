import lxml.html
import textwrap
import logging
import re

from oslo_config import cfg

from aprsd import plugin, plugin_utils
from aprsd.utils import trace


CONF = cfg.CONF
LOG = logging.getLogger("APRSD")


class AvcanPlugin(plugin.APRSDRegexCommandPluginBase):
    """Avalanche Canada Forecast Command

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
            "avcan: Send {} to get avcan danger ratings "
            "from your location".format(self.command_regex),
            "subcommand hl for highlights"
        ]
        return _help

    @trace.trace
    def process(self, packet):
        fromcall = packet.from_call
        message = packet.get("message_text", None)
        # ack = packet.get("msgNo", "0")
        LOG.info(f"Avcan Plugin '{message}'")
        a = re.search(r"^.*\s+([h][l]|[h][l]\s|highlight)", message)
        if a is not None:
            command = "highlights"
        else:
            command = "danger"
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

        lines = []
        if command == "highlights":
            if av_data["report"]["highlights"] is not None:
                highlights = lxml.html.fromstring(av_data["report"]["highlights"]).text_content()
                lines = textwrap.wrap(highlights, 60)
            else:
                return "No forecast for {},{}".format(lat, lon)
        else:
            if av_data["report"]["dangerRatings"] is not None:
                for day in av_data["report"]["dangerRatings"]:
                    lines.append("{}: alp:{}, tl:{}, btl:{}".format(
                        day["date"]["display"][0:3],
                        day["ratings"]["alp"]["rating"]["value"],
                        day["ratings"]["tln"]["rating"]["value"],
                        day["ratings"]["btl"]["rating"]["value"],
                    ))

            else:
                return "No forecast for {},{}".format(lat, lon)

        return lines
