from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError

class PaymentMethod(models.Model):
    _name = "OASYS.payment.method"
    _description = "Payment Methods"


    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)  # For internal identification
    payment_type = fields.Selection([('inbound', 'Inbound'), ('outbound', 'Outbound')], required=True)
    is_default = fields.Boolean(String='Set as default method of payment')

    @api.model
    def create(self, vals):
        record = super(PaymentMethod, self).create(vals)
        if record.is_default and self.search([('payment_type','=',record.payment_type),('is_default','=',True)],limit=1,offset=1,order='id asc'):
            raise UserError(_('Another method has already been set to default.'))

        return record


    @api.multi
    @api.depends('payment_type')
    def write(self, vals):
        record = super(PaymentMethod, self).write(vals)
        for rec in self:
            if vals['is_default'] and self.env['OASYS.payment.method'].search([('payment_type', '=', rec.payment_type), ('is_default', '=', True)],limit=1,offset=1,order='id asc'):
                raise UserError(_('Another method has already been set to default.'))

        return record
