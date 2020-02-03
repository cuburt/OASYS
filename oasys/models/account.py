from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

#account types(ex.accounts receivable, accounts payable, etc)
class Account(models.Model):
    _name = 'OASYS.account'
    _description = "Account"
    _order = "code"

    name = fields.Char(string='Account Name', required=True, index=True)
    currency_id = fields.Many2one('res.currency', string='Account Currency',
                                  help="Forces all moves for this account to have this account currency.")
    code = fields.Char(size=64, index=True, store=True,track_visibility='onchange', readonly=True)
    index = fields.Integer(track_visibility='onchange', store=True)
    deprecated = fields.Boolean(index=True, default=False)
    user_type_id = fields.Many2one('OASYS.account.type', string='Type', required=True, oldname="user_type", store=True,
                                   help="Account Type is used for information purpose, to generate country-specific legal reports, and set the rules to close a fiscal year and generate opening entries.")
    internal_type = fields.Selection(related='user_type_id.type', string="Internal Type", store=True, readonly=True)
    note = fields.Text('Internal Notes')
    company_id = fields.Many2one('res.company', string='Company', required=True, store=True, readonly=True,
        default=lambda self: self.env.user.company_id)



    @api.model
    def create(self, vals):
        record = super(Account, self).create(vals)
        user_type_id = record.user_type_id
        company_id = record.company_id

        rec = self.env['OASYS.account'].search(
            [('company_id', '=', company_id.id), ('user_type_id','=', user_type_id.id), ('index', '!=', False)],
            order='index desc', limit=1).index
        if rec:
            val = rec + 1
        else:
            val = 1
        rjust = 7 - (len(str(val))+len(str(user_type_id.id)))
        record['code'] = '%s%s' % (user_type_id.id, str(val).rjust(rjust, '0'))
        record['index'] = val

        return record
#account groups(ex. current assets, long-term assets, current liabilities, lng-term liabilities, etc.)
class AccountType(models.Model):
    _name = 'OASYS.account.type'
    _description = 'Account Type'

    name = fields.Char(string='Account Type', required=True, translate=True)
    #the ledger type(ex. payable ledger, receivable ledger, general ledger)
    type = fields.Selection([
        ('other', 'General'),
        ('receivable', 'Receivable'),
        ('payable', 'Payable'),
        ('liquidity', 'Liquidity'),
    ], required=True, default='other',
        help="The 'Internal Type' is used for features available on " \
             "different types of accounts: liquidity type is for cash or bank accounts" \
             ", payable/receivable is for vendor/customer accounts.")
    description = fields.Text(string='Description')

#Initial entries of accounts(ex. vendor bills, customer invoices, bank, etc.)
class Journal(models.Model):
    _name = 'OASYS.journal'
    _description = 'Journal'
    _order = 'sequence, type, code'

    @api.model
    def _default_inbound_payment_methods(self):
        return self.env['OASYS.payment.method'].search([('is_default','=',True),('payment_type','=','inbound')]).ids

    @api.model
    def _default_outbound_payment_methods(self):
        return self.env['OASYS.payment.method'].search([('is_default','=',True),('payment_type', '=', 'outbound')]).ids

    name = fields.Char(string='Journal Name', required=True)
    code = fields.Char(string='Short Code', size=5, required=True, help="The journal entries of this journal will be named using this prefix.")
    #journal type(ex. cash receipts journal, cash dibursements journal, sales journal, purchases journal, general journal)
    type = fields.Selection([
        ('sale', 'Sale'),
        ('purchase', 'Purchase'),
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('general', 'Miscellaneous'),
    ], required=True,
        help="Select 'Sale' for customer invoices journals.\n" \
             "Select 'Purchase' for vendor bills journals.\n" \
             "Select 'Cash' or 'Bank' for journals that are used in customer or vendor payments.\n" \
             "Select 'General' for miscellaneous operations journals.")
    type_control_ids = fields.Many2many('OASYS.account.type', 'account_journal_type_rel', 'journal_id', 'type_id', string='Account Types Allowed')
    account_control_ids = fields.Many2many('OASYS.account', 'account_account_type_rel', 'journal_id', 'account_id', string='Accounts Allowed',
        domain=[('deprecated', '=', False)])
    default_credit_account_id = fields.Many2one('OASYS.account', string='Default Credit Account',
                                                domain=[('deprecated', '=', False)],
                                                help="It acts as a default account for credit amount")
    default_debit_account_id = fields.Many2one('OASYS.account', string='Default Debit Account',
                                               domain=[('deprecated', '=', False)],
                                               help="It acts as a default account for debit amount")
    update_posted = fields.Boolean(string='Allow Cancelling Entries',
                                   help="Check this box if you want to allow the cancellation the entries related to this journal or of the invoice related to this journal")

    sequence = fields.Integer(help='Used to order Journals in the dashboard view', default=10)

    currency_id = fields.Many2one('res.currency', help='The currency used to enter statement', string="Currency",
                                  oldname='currency')
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True, readonly=True,
                                 default=lambda self: self.env.user.company_id,
                                 help="Company related to this journal")

    inbound_payment_method_ids = fields.Many2many('OASYS.payment.method','account_journal_inbound_payment_method_rel', 'journal_id', 'inbound_payment_method',
                                                  domain=[('payment_type', '=', 'inbound')], string='Debit Methods',
                                                  default=_default_inbound_payment_methods,
                                                  help="Means of payment for collecting money. Odoo modules offer various payments handling facilities, "
                                                       "but you can always use the 'Manual' payment method in order to manage payments outside of the software.")
    outbound_payment_method_ids = fields.Many2many('OASYS.payment.method', 'account_journal_outbound_payment_method_rel', 'journal_id', 'outbound_payment_method',
                                                   domain=[('payment_type', '=', 'outbound')], string='Payment Methods',
                                                   default=_default_outbound_payment_methods,
                                                   help="Means of payment for sending money. Odoo modules offer various payments handling facilities, "
                                                        "but you can always use the 'Manual' payment method in order to manage payments outside of the software.")
    at_least_one_inbound = fields.Boolean(compute='_methods_compute', store=True)
    at_least_one_outbound = fields.Boolean(compute='_methods_compute', store=True)

    # Bank journals fields
    bank_account_id = fields.Many2one('res.partner.bank', string="Bank Account", ondelete='restrict', copy=False)
    display_on_footer = fields.Boolean("Show in Invoices Footer",
                                       help="Display this bank account on the footer of printed documents like invoices and sales orders.")
    bank_acc_number = fields.Char(related='bank_account_id.acc_number')
    bank_id = fields.Many2one('res.bank', related='bank_account_id.bank_id')

    @api.multi
    def _search_company_journals(self, operator, value):
        if value:
            recs = self.search([('company_id', operator, self.env.user.company_id.id)])
        elif operator == '=':
            recs = self.search([('company_id', '!=', self.env.user.company_id.id)])
        else:
            recs = self.search([('company_id', operator, self.env.user.company_id.id)])
        return [('id', 'in', [x.id for x in recs])]

    @api.multi
    @api.depends('inbound_payment_method_ids', 'outbound_payment_method_ids')
    def _methods_compute(self):
        for journal in self:
            journal.at_least_one_inbound = bool(len(journal.inbound_payment_method_ids))
            journal.at_least_one_outbound = bool(len(journal.outbound_payment_method_ids))


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    journal_id = fields.One2many('OASYS.journal', 'bank_account_id', domain=[('type','=','bank')], string='Account Journal', readonly=True,
                                 help='The accounting journal corresponding to this bank account.')

    @api.one
    @api.constrains('journal_id')
    def _check_journal_id(self):
        if len(self.journal_id) > 1:
            raise ValidationError(_('A bank account can only belong to one journal.'))

