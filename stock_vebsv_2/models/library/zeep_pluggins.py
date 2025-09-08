import logging
from zeep import Plugin
from lxml import etree

_logger = logging.getLogger(__name__)

class ZeepLoggingPlugin(Plugin):
    def ingress(self, envelope, http_headers, operation):
        _logger.debug(etree.tostring(envelope, pretty_print=False))
        return envelope, http_headers

    def egress(self, envelope, http_headers, operation, binding_options):
        _logger.debug(etree.tostring(envelope, pretty_print=False))
        return envelope, http_headers
