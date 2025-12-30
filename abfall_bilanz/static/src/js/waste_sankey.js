/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { user } from "@web/core/user";

export class WasteSankey extends Component {
    setup() {
        this.orm = useService("orm");
        this.root = useRef("sankey");
        this.wasteTypes = [];
        this.state = useState({
            selectedWasteType: 'all',
        });

        this.data = [];
        this.companyPartnerId = null;

        onWillStart(async () => {
            await loadJS("https://www.gstatic.com/charts/loader.js");

            this.companyPartnerId = user.activeCompany.id;

            // Load Waste Types for Filter
            this.wasteTypes = await this.orm.searchRead(
                "waste.type",
                [], // All waste types
                ['id', 'name', 'key_number', 'dangerous']
            );

            // Initial Data Load
            await this.loadData();
        });

        onMounted(() => {
            this.renderChart();
        });
    }

    async onWasteTypeChanged(ev) {
        this.state.selectedWasteType = ev.target.value;
        await this.loadData();
        this.renderChart();
    }

    async loadData() {
        // Build Domain
        const domain = [['state', '=', 'approved']];
        if (this.state.selectedWasteType !== 'all') {
            domain.push(['abfallart', '=', parseInt(this.state.selectedWasteType)]);
        }

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
            this.root.el.innerHTML = '<div class="alert alert-info">No approved waste moves found for this selection.</div>';
            return;
        }

        if (typeof google === 'undefined' || !google.charts) {
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
                // Internal = Partner ID matches Company Partner ID
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

                // Flow Rules:
                // 1. External -> Internal  (Input):  Ext(Source) -> Int
                // 2. Internal -> External  (Output): Int -> Ext(Dest)
                // 3. Internal -> Internal  (Move):   IntA -> IntB
                // 4. External -> External  (Transit): ExtA(Source) -> ExtB(Dest)

                const wasteName = d.abfallart ? d.abfallart[1] : 'Unknown';

                // REVISED Grouping Logic: 
                // Group INTERNAL nodes by Waste Type (Middle), leave External nodes aggregated (Left/Right).

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

                // Prevent self-loops (e.g. Site A -> Site A)
                if (originNode === recipientNode) return;

                complexRows.push([originNode, recipientNode, amount]);
            });

            // If filtering resulted in visible data but valid loop filtering removed everything
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

WasteSankey.template = "abfall_bilanz.WasteSankey";
registry.category("actions").add("abfall_bilanz.waste_sankey_view", WasteSankey);
