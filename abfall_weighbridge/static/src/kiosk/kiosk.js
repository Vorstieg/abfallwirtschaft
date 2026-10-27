/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

export class WeighbridgeKiosk extends Component {
    static template = "abfall_weighbridge.Kiosk";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            busy: false, stationId: 0, partnerId: 0, productId: 0,
            direction: "incoming", commercialRole: "purchase", ticketId: 0,
            stations: [], partners: [], products: [], openTickets: [], ticket: null,
            live: { connection: "unknown", weight: "—", unit: "kg", settled: false, stale: true },
            error: "", message: "",
        });
        this.socket = null;
        this.statusTimer = null;
        onWillStart(() => this.load());
        onWillUnmount(() => this.disconnectEdge());
    }

    async load() {
        const [stations, partners, products] = await Promise.all([
            this.orm.searchRead("weighbridge.station", [["active", "=", true]], ["name", "edge_url", "terminal_number", "scale_number"]),
            this.orm.searchRead("res.partner", [["active", "=", true]], ["display_name"], { limit: 200, order: "name, id" }),
            this.orm.searchRead("product.product", [["active", "=", true], ["type", "!=", "service"]], ["display_name"], { limit: 200, order: "name, id" }),
        ]);
        this.state.stations = stations;
        this.state.partners = partners;
        this.state.products = products;
        if (!this.state.stationId && stations.length) this.state.stationId = stations[0].id;
        await this.loadOpenTickets();
        this.connectEdge();
    }

    async loadOpenTickets() {
        const domain = [["state", "=", "first_weighed"]];
        if (this.state.stationId) domain.push(["station_id", "=", this.state.stationId]);
        this.state.openTickets = await this.orm.searchRead("weighbridge.ticket", domain, ["name", "partner_id", "product_id", "state", "measured_net_kg"], { order: "id desc", limit: 100 });
    }

    disconnectEdge() {
        if (this.socket) this.socket.close();
        this.socket = null;
        if (this.statusTimer) clearInterval(this.statusTimer);
        this.statusTimer = null;
    }

    station() { return this.state.stations.find((station) => station.id === Number(this.state.stationId)); }

    connectEdge() {
        this.disconnectEdge();
        const station = this.station();
        if (!station) return;
        const wsUrl = station.edge_url.replace(/^http:/, "ws:").replace(/^https:/, "wss:").replace(/\/$/, "") + "/v1/stream";
        try {
            this.socket = new WebSocket(wsUrl);
            this.socket.onmessage = (event) => Object.assign(this.state.live, JSON.parse(event.data));
            this.socket.onopen = () => { this.state.live.connection = "connected"; };
            this.socket.onerror = () => { this.state.live.connection = "disconnected"; this.state.live.stale = true; };
            this.socket.onclose = () => { this.state.live.connection = "disconnected"; this.state.live.stale = true; };
        } catch (_error) {
            this.state.live.connection = "disconnected";
        }
    }

    async onStationChange(event) {
        this.state.stationId = Number(event.target.value);
        this.state.ticketId = 0;
        this.state.ticket = null;
        await this.loadOpenTickets();
        this.connectEdge();
    }

    async createTicket() {
        if (!this.state.stationId || !this.state.partnerId || !this.state.productId) {
            this.state.error = "Station, partner and product are required.";
            return;
        }
        const values = this.ticketValues();
        const ids = await this.orm.create("weighbridge.ticket", [values]);
        this.state.ticketId = ids[0];
        await this.reloadTicket();
    }

    ticketValues() {
        return {
            station_id: this.state.stationId, partner_id: this.state.partnerId,
            product_id: this.state.productId, direction: this.state.direction,
            commercial_role: this.state.commercialRole,
        };
    }

    async onPartnerChange(event) { this.state.partnerId = Number(event.target.value); await this.onCommercialContextChanged(); }
    async onProductChange(event) { this.state.productId = Number(event.target.value); await this.onCommercialContextChanged(); }
    async onRoleChange(event) { this.state.commercialRole = event.target.value; await this.onCommercialContextChanged(); }
    async onCommercialContextChanged() {}

    async selectTicket(event) {
        this.state.ticketId = Number(event.target.value);
        await this.reloadTicket();
    }

    async reloadTicket() {
        if (!this.state.ticketId) { this.state.ticket = null; return; }
        const rows = await this.orm.read("weighbridge.ticket", [this.state.ticketId], ["name", "state", "partner_id", "product_id", "measured_net_kg", "deduction_kg", "payable_weight_kg"]);
        this.state.ticket = rows[0] || null;
    }

    async capture() {
        if (this.state.busy || !this.state.ticketId) return;
        this.state.busy = true;
        this.state.error = "";
        this.state.message = "Requesting one-time capture challenge…";
        try {
            const issued = await rpc("/weighbridge/capture/challenge", { ticket_id: this.state.ticketId, station_id: this.state.stationId });
            this.state.message = "Waiting for settled certified weight…";
            const response = await fetch(issued.edge_url.replace(/\/$/, "") + "/v1/captures", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ challenge: issued.challenge }),
            });
            const capture = await response.json();
            if (!response.ok) throw new Error(capture.message || capture.error || `Edge service error ${response.status}`);
            const committed = await rpc("/weighbridge/capture/commit", { challenge: issued.challenge, capture });
            this.state.message = "Certified weight saved.";
            await this.reloadTicket();
            await this.loadOpenTickets();
        } catch (error) {
            this.state.error = error.data?.message || error.message || String(error);
            this.state.message = "";
        } finally {
            this.state.busy = false;
        }
    }

    printTicket() {
        if (!this.state.ticketId) return;
        this.action.doAction({ type: "ir.actions.report", report_type: "qweb-pdf", report_name: `abfall_weighbridge.report_weighbridge_ticket/${this.state.ticketId}` });
    }
}

registry.category("actions").add("abfall_weighbridge.kiosk", WeighbridgeKiosk);
