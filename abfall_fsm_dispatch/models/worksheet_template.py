from odoo import api, models


class WorksheetTemplate(models.Model):
    _inherit = 'worksheet.template'

    @api.model
    def _setup_abfall_dispatch_worksheet_template(self):
        template = self.env.ref('abfall_fsm_dispatch.abfall_dispatch_worksheet_template', raise_if_not_found=False)
        if not template or not template.model_id:
            return

        template._create_abfall_dispatch_worksheet_fields()
        form_view = template._create_or_update_abfall_dispatch_worksheet_form_view()
        template._generate_qweb_report_template(form_view.id)
        template._assign_to_existing_abfall_dispatch_tasks()

    def _create_abfall_dispatch_worksheet_fields(self):
        self.ensure_one()
        existing_fields = set(self.model_id.field_id.mapped('name'))
        field_vals = []
        for name, field_description, ttype in [
            ('x_driver_notes', 'Driver Notes', 'html'),
            ('x_pickup_photo', 'Pickup Photo', 'binary'),
            ('x_delivery_photo', 'Delivery Photo', 'binary'),
            ('x_exception_photo', 'Damage / Exception Photo', 'binary'),
        ]:
            if name in existing_fields:
                continue
            field_vals.append({
                'name': name,
                'field_description': field_description,
                'ttype': ttype,
                'model_id': self.model_id.id,
            })
        if field_vals:
            self.env['ir.model.fields'].create(field_vals)

    def _create_or_update_abfall_dispatch_worksheet_form_view(self):
        self.ensure_one()
        View = self.env['ir.ui.view']
        arch = """
            <form create="false" duplicate="false">
                <sheet>
                    <group invisible="context.get('studio') or context.get('default_x_project_task_id')">
                        <div class="oe_title text-break" colspan="2">
                            <h1>
                                <field name="x_project_task_id" domain="[('is_fsm', '=', True)]" readonly="1"/>
                            </h1>
                        </div>
                    </group>
                    <group class="o_fsm_worksheet_form">
                        <field name="x_comments" placeholder="Additional worksheet comments..."/>
                        <field name="x_driver_notes"/>
                        <field name="x_pickup_photo" widget="image"/>
                        <field name="x_delivery_photo" widget="image"/>
                        <field name="x_exception_photo" widget="image"/>
                    </group>
                </sheet>
            </form>
        """
        vals = {
            'name': 'abfall.dispatch.worksheet.form',
            'type': 'form',
            'model': self.model_id.model,
            'arch': arch,
        }
        view = View.search([
            ('name', '=', vals['name']),
            ('model', '=', vals['model']),
            ('type', '=', 'form'),
        ], limit=1)
        if view:
            view.write(vals)
        else:
            view = View.create(vals)
        return view

    def _assign_to_existing_abfall_dispatch_tasks(self):
        self.ensure_one()
        Task = self.env['project.task']
        if 'worksheet_template_id' not in Task._fields:
            return
        tasks = Task.search([('dispatch_list_id', '!=', False)])
        if not tasks:
            return
        projects = tasks.project_id
        if 'allow_worksheets' in projects._fields:
            projects.filtered(lambda project: not project.allow_worksheets).write({'allow_worksheets': True})
        tasks.write({'worksheet_template_id': self.id})
