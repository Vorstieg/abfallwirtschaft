# Field Service Task Information Concept

## Goal

Dispatch-generated field service tasks must give the driver the relevant pickup and delivery information without adding a custom task UI:

- which container serial number must be picked up from the customer
- which container serial number must be delivered to the customer
- which product or waste product must be picked up
- a worksheet that can be signed by the customer
- photo documentation through the standard worksheet photo component

The field service task should remain close to the standard Odoo FSM task. The dispatch-specific information is written into the task description.

## Current State

The `abfall_fsm_dispatch` module creates one `project.task` per `stock.picking` when a dispatch list is confirmed or started.

The task currently stores:

- dispatch list
- stock transfer
- customer
- responsible user
- planned date
- text description with dispatch list, transfer, operation type, origin, and dispatch description

The `container_exchange_stock` module already selects the return container and delivery container as `stock.lot` serial numbers and writes them to the related stock picking move lines. Therefore, the linked `stock.picking` remains the source of truth for products, quantities, and serial numbers.

## Functional Design

### 1. Dispatch Information in Task Description

Do not add a new model such as `abfall.fsm.task.line`.

Do not add a custom task form section or task UI extension.

Instead, enrich the generated `project.task.description` in `_prepare_fsm_task_vals()` with a structured text block derived from the linked stock picking.

Recommended description structure:

```text
Dispatch List: DISP/00001
Transfer: WH/IN/00012
Operation Type: Receipts
Origin: SO123 - Container Exchange
Customer: Musterkunde GmbH
Address: Musterstrasse 1, 1010 Wien

Work Instructions
Pickup:
- Product: 10m3 Container
  Container Serial: CONT-00123
  Quantity: 1.00 Units
  From: Customer/Rental
  To: WH/Stock

Delivery:
- Product: 10m3 Container
  Container Serial: CONT-00456
  Quantity: 1.00 Units
  From: WH/Stock
  To: Customer/Rental

Products / Waste to Pick Up:
- Product: Mixed Waste
  Quantity: 800.00 kg
  Container Serial: CONT-00123

Driver Notes:
...
```

The exact labels can be translated later through the existing Odoo translation flow.

### 2. Product and Serial Source

Build the description from the linked `stock.picking`:

- use `stock.move.line.lot_id.name` for serial/lot-specific container information
- fall back to `stock.move.lot_ids`, if relevant in the installed Odoo version
- if no lot/serial exists, still show product, planned quantity, done quantity if available, and UoM
- use `stock.move.product_id`, `product_uom_qty`, `quantity`, and `product_uom`
- use source and destination locations from the move or picking

For serial-tracked container products, each serial number should be explicitly listed in the description.

### 3. Pickup vs Delivery Wording

Use stock movement direction to create driver-friendly sections:

- `Pickup`: movement from customer/rental/customer-facing location back to company stock or disposal flow
- `Delivery`: movement from company stock to customer/rental/customer-facing location
- `Internal Movement`: fallback for route steps that are not customer-facing
- `Unclassified`: fallback if the operation cannot be classified reliably

For container exchanges:

- the return picking description must state the container serial to pick up
- the outgoing/final delivery picking description must state the container serial to deliver

If a single task/picking contains several relevant moves, group them under the matching headings.

### 4. Worksheet

Use the standard Odoo FSM worksheet mechanism for customer confirmation.

The worksheet should include:

- customer name and address
- dispatch list
- stock transfer
- scheduled date
- driver/responsible user
- vehicle, if available from the dispatch list
- task description, including the generated pickup/delivery instructions
- customer signature
- optional driver signature, if supported by the selected worksheet template
- timestamp

The worksheet should not depend on a custom dispatch line model. It can render the task description and standard task fields.

### 5. Photos

Do not add a custom photo model.

Use the default worksheet photo/image component for pickup and delivery photos. The driver captures pictures directly in the worksheet while completing the FSM task.

Recommended worksheet photo prompts:

- pickup photo
- delivery photo
- damage/exception photo
- optional additional photo

If photo requirements become mandatory later, implement that as worksheet validation/configuration where possible instead of adding custom task photo fields.

### 6. Validation Workflow

When the driver validates the FSM task:

1. The driver reviews the task description for product, quantity, and container serial instructions.
2. The driver completes the standard worksheet.
3. The customer signs in the worksheet.
4. The driver adds pickup/delivery photos through the worksheet photo component.
5. The existing `action_fsm_validate()` flow validates the linked stock picking.

The current automatic stock picking validation can remain. If quantity adjustment from the field is required later, that should be designed separately because the simplified concept does not add editable dispatch lines to the task.

## Technical Design

### Model Changes

Keep model changes minimal.

Extend `project.task` only if the worksheet implementation requires standard worksheet-related fields. Do not add:

- `abfall.fsm.task.line`
- `abfall.fsm.task.photo`
- custom one2many task detail fields
- custom photo fields
- custom task detail UI fields

### Description Generation

Extend `abfall.dispatch.list._prepare_fsm_task_vals(picking, fsm_project)`:

- keep the existing base description entries
- append a generated dispatch instruction block
- read products, quantities, UoM, locations, and serial numbers from the picking moves and move lines
- format the result as clear plain text or simple HTML, depending on the field rendering in the target Odoo version

Recommended helper methods:

- `_prepare_fsm_task_description(picking)`
- `_get_fsm_picking_instruction_sections(picking)`
- `_format_fsm_instruction_line(move, move_line=False)`
- `_classify_fsm_move_operation(move, move_line=False)`

### Source of Serial Numbers

Use this priority:

1. `stock.move.line.lot_id`
2. `stock.move.lot_ids`, if available and populated
3. no serial, product-only line

For serial-tracked container products, the expected result is one explicit description entry per serial number.

### Worksheet Dependency

Keep the base dependency on `industry_fsm`.

Add the standard worksheet module dependency used in the installed Odoo version. This must be verified in the target database before implementation because the exact module name depends on the Odoo edition/version and installed FSM worksheet apps.

### Views

No custom field service task UI extension is required for dispatch details.

The existing task view extension may continue to show:

- dispatch list
- stock transfer

The actual product/container instructions live in the task description and worksheet.

## Acceptance Criteria

- When a dispatch list is confirmed, every generated field service task description lists the relevant product, quantity, UoM, source, destination, and serial/container number when available.
- If a transfer contains a serial-tracked container, the task description shows the exact serial number to pick up or deliver.
- Container exchange tasks clearly distinguish pickup container and delivery container in the description.
- No `abfall.fsm.task.line` model is introduced.
- No custom dispatch details tab/list is added to the task UI.
- The customer can sign a standard FSM worksheet.
- The driver can add pickup/delivery photos through the default worksheet photo component.
- Completing the FSM task still validates the linked stock transfer through the existing flow.

## Implementation Phases

### Phase 1: Description Enrichment

- Add helper methods to generate structured pickup/delivery text from stock picking moves and move lines.
- Update `_prepare_fsm_task_vals()` to include the generated instructions.
- Add tests for product-only lines and serial-tracked container lines.

### Phase 2: Worksheet

- Add the correct standard worksheet dependency.
- Configure or add a worksheet template that includes task description, customer signature, and worksheet photo components.
- Verify the worksheet on mobile.

### Phase 3: Validation Hardening

- Keep existing picking validation behavior.
- Optionally add validation around worksheet completion/signature if supported by the standard worksheet module.

## Open Decisions

- Should task descriptions be plain text or HTML in this Odoo version?
- Which installed standard worksheet module/template should be used?
- Should worksheet photos be mandatory, or only recommended?
- Should final worksheet PDFs also be attached to the stock picking or remain only on the FSM task?
