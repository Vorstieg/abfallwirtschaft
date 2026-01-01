/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { Component, onWillStart, onMounted, useRef, onWillUpdateProps, useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { Layout } from "@web/search/layout";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { _t } from "@web/core/l10n/translation";
import { SearchModel } from "@web/search/search_model";

// -------------------------------------------------------------------------
// Renderer
// -------------------------------------------------------------------------
export class WasteSankeyRenderer extends Component {
    setup() {
        this.orm = useService("orm");
        this.root = useRef("sankey");
        this.companyPartnerId = user.activeCompany.id;

        this.data = [];

        onWillStart(async () => {
            await loadJS("https://www.gstatic.com/charts/loader.js");
            await this.loadData();
        });

        onMounted(() => {
            this.renderChart();
        });

        onWillUpdateProps(async (nextProps) => {
            if (JSON.stringify(nextProps.domain) !== JSON.stringify(this.props.domain)) {
                await this.loadData(nextProps.domain);
                this.renderChart();
            }
        });
    }

    async loadData(domainOverride = null) {
        const domain = domainOverride || this.props.domain || [];
        this.data = await this.orm.searchRead(
            "waste.move",
            domain,
            ['origin_partner', 'origin_site', 'origin_installation',
                'recipient_partner', 'recipient_site', 'recipient_installation',
                'abfallart', 'amount']
        );
    }

    renderChart() {
        if (!this.root.el) return;

        if (!this.data.length) {
            this.root.el.innerHTML = '<div class="alert alert-info">No waste moves found for this selection.</div>';
            return;
        }

        if (typeof google === 'undefined' || !google.charts) {
            setTimeout(() => this.renderChart(), 100);
            return;
        }

        google.charts.load('current', { 'packages': ['sankey'] });
        google.charts.setOnLoadCallback(() => {
            if (!this.root.el) return;
            this.root.el.innerHTML = '';

            const container = this.root.el;
            const chart = new google.visualization.Sankey(container);
            const complexRows = [];

            this.data.forEach(d => {
                const amount = d.amount || 0;
                if (amount <= 0) return;

                const originPartnerId = d.origin_partner ? d.origin_partner[0] : -1;
                const recPartnerId = d.recipient_partner ? d.recipient_partner[0] : -1;
                const isOriginInternal = (originPartnerId === this.companyPartnerId);
                const isRecInternal = (recPartnerId === this.companyPartnerId);

                const getNodeName = (prefix) => {
                    if (d[prefix + '_installation']) return d[prefix + '_installation'][1];
                    if (d[prefix + '_site']) return d[prefix + '_site'][1];
                    if (d[prefix + '_partner']) return d[prefix + '_partner'][1];
                    return 'Unknown';
                };

                let originNode = getNodeName('origin');
                let recipientNode = getNodeName('recipient');
                const wasteName = d.abfallart ? d.abfallart[1] : 'Unknown';

                if (isOriginInternal) {
                    originNode += ` (${wasteName})`;
                } else {
                    originNode += ' (Quelle)';  // Force left
                }

                if (isRecInternal) {
                    recipientNode += ` (${wasteName})`;
                } else {
                    recipientNode += ' (Ziel)';  // Force right
                }

                if (originNode === recipientNode) return;
                complexRows.push([originNode, recipientNode, amount]);
            });

            if (complexRows.length === 0) {
                this.root.el.innerHTML = '<div class="alert alert-warning">No valid flows to display.</div>';
                return;
            }

            const data = new google.visualization.DataTable();
            data.addColumn('string', 'From');
            data.addColumn('string', 'To');
            data.addColumn('number', 'Weight (kg)');
            data.addRows(complexRows);

            const options = {
                height: 600,
                sankey: {
                    node: {
                        label: { fontName: 'Roboto', fontSize: 12 },
                        width: 20
                    },
                    link: { colorMode: 'gradient' }
                }
            };
            chart.draw(data, options);
        });
    }
}
WasteSankeyRenderer.template = "abfall_bilanz.WasteSankeyRenderer";
WasteSankeyRenderer.components = {};

// -------------------------------------------------------------------------
// Controller
// -------------------------------------------------------------------------
export class WasteSankeyController extends Component {
    setup() {
        // Model prop is passed but we don't strictly need to react to its state here
        // as the Renderer handles data fetching based on domain prop.
    }
}
WasteSankeyController.template = "abfall_bilanz.WasteSankeyView";
WasteSankeyController.components = { Layout, SearchBar, WasteSankeyRenderer };

// -------------------------------------------------------------------------
// View
// -------------------------------------------------------------------------
export const wasteSankeyView = {
    type: "sankey",
    display_name: _t("Sankey"),
    icon: "o_sankey_icon",
    multiRecord: true,
    Controller: WasteSankeyController,
    Renderer: WasteSankeyRenderer,
    SearchModel: SearchModel,

    props: (genericProps, view) => {
        return {
            ...genericProps,
            Model: view.Model,
            Renderer: view.Renderer,
        };
    },
};

registry.category("views").add("sankey", wasteSankeyView);
