from odoo import models, fields, api, _
from odoo.tools import float_is_zero, float_compare
from odoo.exceptions import UserError, ValidationError

class AccountTaxGroup(models.Model):
    _name = 'oasys.tax.group'
    _order = 'sequence asc'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)


class AccountTax(models.Model):
    _name = 'oasys.tax'
    _description = 'Tax'
    _order = 'sequence,id'

    @api.model
    def _default_tax_group(self):
        return self.env['oasys.tax.group'].search([],limit=1)

    # @api.depends(
    #     'state', 'currency_id', 'invoice_line_ids.price_subtotal',
    #     'move_id.line_ids.amount_residual',
    #     'move_id.line_ids.currency_id')
    # def _compute_residual(self):
    #     residual = 0.0
    #     residual_company_signed = 0.0
    #     sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
    #     for line in self.sudo().move_id.line_ids:
    #         if line.account_id.internal_type in ('receivable', 'payable'):
    #             residual_company_signed += line.amount_residual
    #             if line.currency_id == self.currency_id:
    #                 residual += line.amount_residual_currency if line.currency_id else line.amount_residual
    #             else:
    #                 from_currency = (line.currency_id and line.currency_id.with_context(
    #                     date=line.date)) or line.company_id.currency_id.with_context(date=line.date)
    #                 residual += from_currency.compute(line.amount_residual, self.currency_id)
    #     self.residual_company_signed = abs(residual_company_signed) * sign
    #     self.residual_signed = abs(residual) * sign
    #     self.residual = abs(residual)
    #     digits_rounding_precision = self.currency_id.rounding
    #     if float_is_zero(self.residual, precision_rounding=digits_rounding_precision):
    #         self.reconciled = True
    #     else:
    #         self.reconciled = False
    name = fields.Char(string='Tax Name', required=True, translate=True)
    type_tax_use = fields.Selection([('sale', 'Sales'), ('purchase', 'Purchases'), ('none', 'None')],
                                    string='Tax Scope', required=True, default="sale",
                                    help="Determines where the tax is selectable. Note : 'None' means a tax can't be used by itself, however it can still be used in a group.")
    amount_type = fields.Selection(default='percent', string="Tax Computation", required=True, oldname='type',
                                   selection=[('group', 'Group of Taxes'), ('fixed', 'Fixed'),
                                              ('percent', 'Percentage of Price'),
                                              ('division', 'Percentage of Price Tax Included')])
    active = fields.Boolean(default=True, help="Set active to false to hide the tax without removing it.")
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    children_tax_ids = fields.Many2many('oasys.tax', 'account_tax_filiation_rel', 'parent_tax', 'child_tax', string='Children Taxes')
    sequence = fields.Integer(required=True, default=1,
        help="The sequence field is used to define order in which the tax lines are applied.")
    amount = fields.Float(required=True, digits=(16, 4))

    account_id = fields.Many2one('oasys.account', domain=[('deprecated', '=', False),('internal_type','=','liquidity')], string='Tax Account',
                                 ondelete='restrict',
                                 help="Account that will be set on invoice tax lines for invoices. Leave empty to use the expense account.",
                                 oldname='account_collected_id')
    # refund_account_id = fields.Many2one('account.account', domain=[('deprecated', '=', False)],
    #                                     string='Tax Account on Refunds', ondelete='restrict',
    #                                     help="Account that will be set on invoice tax lines for refunds. Leave empty to use the expense account.",
    #                                     oldname='account_paid_id')
    description = fields.Char(string='Label on Invoices', translate=True)
    price_include = fields.Boolean(string='Included in Price', default=False,
                                   help="Check this if the price you use on the product and invoices includes this tax.")
    include_base_amount = fields.Boolean(string='Affect Base of Subsequent Taxes', default=False,
                                         help="If set, taxes which are computed after this one will be computed based on the price tax included.")
    # analytic = fields.Boolean(string="Include in Analytic Cost",
    #                           help="If set, the amount computed by this tax will be assigned to the same analytic account as the invoice line (if any)")
    # tag_ids = fields.Many2many('oasys.account.tag', 'account_tax_account_tag', string='Tags',
    #                            help="Optional tags you may want to assign for custom reporting")
    tax_group_id = fields.Many2one('oasys.tax.group', string="Tax Group", default=_default_tax_group, required=True)
