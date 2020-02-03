import re
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
from odoo.osv import expression
from datetime import datetime
import odoo.addons.decimal_precision as dp

class Product(models.Model):
    _name = 'OASYS.product'
    _description = 'Product'

    name = fields.Char(string="Product Name")
    description = fields.Text()
    image_small = fields.Binary()
    image_medium = fields.Binary()
    image_large = fields.Binary()
    is_active = fields.Boolean(string="Active")
    is_sellable = fields.Boolean(string="Can be Sold")
    is_available = fields.Boolean(string="Can be Purchased")
    type = fields.Selection([('consumable','Consumable'),
                             ('service','Service')], string="Product Type", required=True, default='consumable')
    brand = fields.Char(string='Brand')
    default_code = fields.Char(string="Internal Reference", readonly=True)
    barcode = fields.Char(string="Barcode")
    category_id = fields.Many2one('OASYS.product.category', string='Internal Category', required=True)
    list_price = fields.Monetary(string="Sale Price", currency_field="currency_id")
    standard_price = fields.Monetary(string="Cost", currency_field="currency_id")
    company_id = fields.Many2one('res.company', string="Company", related='category_id.company_id')
    currency_id = fields.Many2one('res.currency', string='Currency', related='company_id.currency_id',
                                  required=True, readonly=True,
                                 track_visibility='always')

    rating = fields.Float(digits=(1,1), string="Product Rating")

    #default_code sequencing
    @api.model
    def create(self, vals):
        record = super(Product, self).create(vals)
        company_id = record.company_id
        product_id = record.id
        date = datetime.strptime(fields.Date.context_today(self), DEFAULT_SERVER_DATE_FORMAT)
        year = date.strftime('%y')
        rec = self.env['OASYS.product'].search(
            [('company_id', '=', company_id.id), ('id','=',product_id)],order='id desc', limit=1).id
        if rec:
            val = rec + 1
        else:
            val = 1
        record['default_code'] = '%s-%s-%s' % (company_id.id, year, str(val).rjust(9, '0'))

        return record

class ProductCategory(models.Model):
    _name = 'OASYS.product.category'
    _description = 'Product Category'

    name = fields.Char(string='Category Name', required=True)
    parent_id = fields.Many2one('OASYS.product.category',string="Parent Category")
    company_id = fields.Many2one('res.company', string="Company", default= lambda self: self.env['res.company']._company_default_get('OASYS.product.category'))
    type = fields.Selection([('view','View'),
                             ('normal','Normal')], string='Category Type')

