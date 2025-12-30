/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { Component, onWillStart, onMounted, useRef, onWillUpdateProps, useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { Layout } from "@web/search/layout";
import { WithSearch } from "@web/search/with_search/with_search";
import { SearchBar } from "@web/search/search_bar/search_bar";

export class WasteSankeyRenderer extends Component {
    setup() {
        this.orm = useService("orm");
        this.root = useRef("sankey");
        this.companyPartnerId = user.activeCompany.id;

        // Data storage
        this.data = [];

        onWillStart(async () => {
            await loadJS("https://www.gstatic.com/charts/loader.js");
            await this.loadData();
        });

        onMounted(() => {
            this.renderChart();
        });

        onWillUpdateProps(async (nextProps) => {
            // Reload if domain changes
            if (JSON.stringify(nextProps.domain) !== JSON.stringify(this.props.domain)) {
                await this.loadData(nextProps.domain);
                this.renderChart();
            }
        });
    }

    async loadData(domainOverride = null) {
        const domain = domainOverride || this.props.domain || [];
        // Ensure we always require approved state, merged with search domain
        // Actually, the search view might manage state too, but let's enforce approved only if not present?
        // Or better, add 'state=approved' to the base domain in the controller or assume the user filters for it.
        // The original code hardcoded `state=approved`.
        // Let's prepend it or just allow the search view to control it.
        // If I want to FORCE approved, I should combine it.
        // But the search view has a filter for it.
        // I will add it to the request domain AND the props domain.

        // Actually, let's respect the user's search completely. 
        // If they want to see Draft, they can unfilter 'Approved' in search view if available.
        // But original code enforced it.
        // I'll stick to the props domain for now, so the Search View controls everything.
        // But I should make sure the "Approved" filter is default in the Search View XML.

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

        // Clear previous content if empty
        if (!this.data.length) {
            this.root.el.innerHTML = '<div class="alert alert-info">No waste moves found for this selection.</div>';
            return;
        }

        if (typeof google === 'undefined' || !google.charts) {
            // Retry if google charts not ready
            setTimeout(() => this.renderChart(), 100);
            return;
        }

        google.charts.load('current', { 'packages': ['sankey'] });
        google.charts.setOnLoadCallback(() => {
            if (!this.root.el) return;

            // Clear previous chart
            this.root.el.innerHTML = '';

            const container = this.root.el;
            const chart = new google.visualization.Sankey(container);
            const complexRows = [];

            this.data.forEach(d => {
                const amount = d.amount || 0;
                if (amount <= 0) return;

                // Identification Logic
                const originPartnerId = d.origin_partner ? d.origin_partner[0] : -1;
                const recPartnerId = d.recipient_partner ? d.recipient_partner[0] : -1;

                const isOriginInternal = (originPartnerId === this.companyPartnerId);
                const isRecInternal = (recPartnerId === this.companyPartnerId);

                // Naming helper
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
                    originNode += ' (Source)';
                }

                if (isRecInternal) {
                    recipientNode += ` (${wasteName})`;
                } else {
                    recipientNode += ' (Dest)';
                }

                // Prevent self-loops
                if (originNode === recipientNode) return;

                complexRows.push([originNode, recipientNode, amount]);
            });

            if (complexRows.length === 0) {
                this.root.el.innerHTML = '<div class="alert alert-warning">No valid flows to display (possible self-loops only).</div>';
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
WasteSankeyRenderer.components = { Layout, SearchBar };

export class WasteSankey extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({ searchViewId: false });
        onWillStart(async () => {
            try {
                const result = await this.orm.call("ir.model.data", "check_object_reference", ["abfall_bilanz", "waste_move_view_search"]);
                if (result) {
                    this.state.searchViewId = result[1];
                }
            } catch (e) {
                console.error("Could not load search view ID", e);
            }
        });
    }
}
WasteSankey.template = "abfall_bilanz.WasteSankey";
WasteSankey.components = { WithSearch, WasteSankeyRenderer };

registry.category("actions").add("abfall_bilanz.waste_sankey_view", WasteSankey);
