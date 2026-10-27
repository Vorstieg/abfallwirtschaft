/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WeighbridgeKiosk } from "@abfall_weighbridge/kiosk/kiosk";

patch(WeighbridgeKiosk.prototype, {
    setup() {
        super.setup();
        this.state.saleLines = [];
        this.state.saleLineId = 0;
    },

    async onCommercialContextChanged() {
        await super.onCommercialContextChanged(...arguments);
        this.state.saleLineId = 0;
        this.state.saleLines = [];
        if (this.state.commercialRole !== "sale" || !this.state.partnerId || !this.state.productId) return;
        const lines = await this.orm.searchRead("sale.order.line", [
            ["order_id.state", "=", "sale"],
            ["order_id.partner_id.commercial_partner_id", "=", this.state.partnerId],
            ["product_id", "=", this.state.productId], ["product_uom_qty", ">", 0],
        ], ["order_id", "product_uom_qty", "qty_delivered", "product_uom_id"], { limit: 100 });
        this.state.saleLines = lines.map((line) => ({
            ...line, label: `${line.order_id[1]} — ${line.product_uom_qty - line.qty_delivered} remaining`,
        }));
    },

    ticketValues() {
        const values = super.ticketValues(...arguments);
        if (this.state.commercialRole === "sale" && this.state.saleLineId) values.sale_line_id = this.state.saleLineId;
        return values;
    },
});
