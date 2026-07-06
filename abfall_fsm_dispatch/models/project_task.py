from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    stock_picking_batch_id = fields.Many2one(
        'stock.picking.batch',
        string='Stock Batch',
        index=True,
        copy=False,
        ondelete='set null',
    )
    stock_picking_id = fields.Many2one(
        'stock.picking',
        string='Stock Transfer',
        index=True,
        copy=False,
        ondelete='set null',
    )

    _sql_constraints = [
        (
            'project_task_stock_picking_unique',
            'unique(stock_picking_id)',
            'A stock transfer can only be linked to one field service task.',
        ),
    ]
