from odoo import models, fields, api



class Product(models.Model):
    _inherit = 'OASYS.product'



    property_account_income_id = fields.Many2one('OASYS.account', string='Income Account', related='category_id.property_account_income_id')
    property_account_expense_id = fields.Many2one('OASYS.account', string='Expense Account', related='category_id.property_account_expense_id')
    tax_ids = fields.Many2many('OASYS.tax',
                               'product_tax_rel', 'product_id', 'tax_id',
                               string='Taxes')
    supplier_tax_ids = fields.Many2many('OASYS.tax',
                                        'product_tax_rel', 'product_id', 'tax_id',
                                        string='Taxes')

class ProductCategory(models.Model):
    _inherit = 'OASYS.product.category'

    property_account_income_id = fields.Many2one('OASYS.account', string='Income Account')
    property_account_expense_id = fields.Many2one('OASYS.account', string='Expense Account')