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
            "avcan: Send {} to get danger ratings".format(self.command_regex),
            "subcommands: highlights summary snowpack weather"
        ]
        return _help

    @trace.trace
    def process(self, packet):
        fromcall = packet.from_call
        message = packet.get("message_text", None)
        # ack = packet.get("msgNo", "0")
        LOG.info(f"Avcan Plugin '{message}'")
        command = "danger"
        a = re.search(r"^.*\s+([h][l]|[h][l]\s|highlights)", message)
        if a is not None:
            command = "highlights"

        a = re.search(r"^.*\s+([a][s]|[a][s]\s|summary)", message)
        if a is not None:
            command = "avsum"

        a = re.search(r"^.*\s+([s][s]|[s][s]\s|snowpack)", message)
        if a is not None:
            command = "snowsum"

        a = re.search(r"^.*\s+([w][s]|[w][s]\s|weather)", message)
        if a is not None:
            command = "weathersum"

        LOG.info("AvcanPlugin: command = {}".format(command))
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

        LOG.info("AvcanPlugin: lat,lon = {},{}".format(lat,lon))
        try:
            av_data = plugin_utils.fetch_avcan(
                lat,
                lon,
            )
        except Exception as ex:
            LOG.error(f"Couldn't fetch avcan api '{ex}'")
            return "Unable to get avalanche forecast"

        lines = []
        if av_data["report"]["highlights"] is None:
            return "No forecast for {},{}".format(lat, lon)

        if command == "highlights":
            if av_data["report"]["highlights"] is not None:
                highlights = lxml.html.fromstring(av_data["report"]["highlights"]).text_content()
                lines = textwrap.wrap(highlights, 67)

        elif command == "avsum":
            if av_data["report"]["summaries"] is not None:
                for summary in av_data["report"]["summaries"]:
                    if summary["type"]["value"] == "avalanche-summary":
                        avsum = lxml.html.fromstring(summary["content"]).text_content()
                        lines = textwrap.wrap(avsum, 67)
                        break

        elif command == "snowsum":
            if av_data["report"]["summaries"] is not None:
                for summary in av_data["report"]["summaries"]:
                    if summary["type"]["value"] == "snowpack-summary":
                        snowsum = lxml.html.fromstring(summary["content"]).text_content()
                        lines = textwrap.wrap(snowsum, 67)
                        break

        elif command == "weathersum":
            if av_data["report"]["summaries"] is not None:
                for summary in av_data["report"]["summaries"]:
                    if summary["type"]["value"] == "weather-summary":
                        weathersum = lxml.html.fromstring(summary["content"]).text_content()
                        lines = textwrap.wrap(weathersum, 67)
                        break
        else:
            if av_data["report"]["dangerRatings"] is not None:
                for day in av_data["report"]["dangerRatings"]:
                    lines.append("{}: alp:{}, tl:{}, btl:{}".format(
                        day["date"]["display"][0:3],
                        day["ratings"]["alp"]["rating"]["value"],
                        day["ratings"]["tln"]["rating"]["value"],
                        day["ratings"]["btl"]["rating"]["value"],
                    ))

        return lines
