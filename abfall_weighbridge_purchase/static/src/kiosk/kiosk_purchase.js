/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WeighbridgeKiosk } from "@abfall_weighbridge/kiosk/kiosk";

patch(WeighbridgeKiosk.prototype, {
    setup() {
        super.setup();
        this.state.purchaseLines = [];
        this.state.purchaseLineId = 0;
    },

    async onCommercialContextChanged() {
        await super.onCommercialContextChanged(...arguments);
        this.state.purchaseLineId = 0;
        this.state.purchaseLines = [];
        if (this.state.commercialRole !== "purchase" || !this.state.partnerId || !this.state.productId) return;
        const lines = await this.orm.searchRead("purchase.order.line", [
            ["order_id.state", "in", ["purchase", "done"]],
            ["order_id.partner_id.commercial_partner_id", "=", this.state.partnerId],
            ["product_id", "=", this.state.productId], ["product_qty", ">", 0],
        ], ["order_id", "product_qty", "qty_received", "product_uom_id"], { limit: 100 });
        this.state.purchaseLines = lines.map((line) => ({
            ...line, label: `${line.order_id[1]} — ${line.product_qty - line.qty_received} remaining`,
        }));
    },

    ticketValues() {
        const values = super.ticketValues(...arguments);
        if (this.state.commercialRole === "purchase" && this.state.purchaseLineId) values.purchase_line_id = this.state.purchaseLineId;
        return values;
    },
});
