# Abfall Weighbridge Core

Odoo 19 core for authenticated SysTec IT3 capture. The certified IT3/ASM archive
is authoritative; this addon stores immutable signed evidence and manages the
two-stage weighing lifecycle.

The core deliberately has no dependency on Stock, Sales, Purchase, or
Accounting. Install optional addons as needed:

- `abfall_weighbridge_stock` for physical stock processing and no-charge moves;
- `abfall_weighbridge_sale` for sales lines, spot sales, and deliveries;
- `abfall_weighbridge_purchase` for purchase lines, spot purchases, and receipts;
- `abfall_weighbridge_billing` for invoices, bills, and scheduled billing;
- `abfall_weighbridge_full` as a convenience installer for the complete stack.

Downstream processing uses independent retryable states. Its failure cannot roll
back a successfully verified terminal capture.

The station-side service is deployed independently from
`services/abfall_weighbridge_edge`.

This source targets Odoo 19. Odoo 18 and 17 ports belong on dedicated branches.
