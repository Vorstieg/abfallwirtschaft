from odoo import http
from odoo.http import request


class WeighbridgeCaptureController(http.Controller):
    @http.route("/weighbridge/capture/challenge", type="jsonrpc", auth="user", methods=["POST"], csrf=True)
    def capture_challenge(self, ticket_id, station_id=None):
        return request.env["weighbridge.capture.challenge"].issue(ticket_id, station_id)

    @http.route("/weighbridge/capture/commit", type="jsonrpc", auth="user", methods=["POST"], csrf=True)
    def capture_commit(self, challenge, capture):
        return request.env["weighbridge.capture.challenge"].commit(challenge, capture)

