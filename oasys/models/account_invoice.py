from odoo import api, fields, models, _
from odoo import *
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import json





# mapping invoice type to journal type
TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale',
    'in_refund': 'purchase',
}

# mapping invoice type to refund type
TYPE2REFUND = {
    'out_invoice': 'out_refund',        # Customer Invoice
    'in_invoice': 'in_refund',          # Vendor Bill
    'out_refund': 'out_invoice',        # Customer Refund
    'in_refund': 'in_invoice',          # Vendor Refund
}

class AccountInvoice(models.Model):
    _name = 'oasys.account.invoice'
    _description =  'Invoice'
    _order = "id desc"

    @api.model
    def _get_reference_type(self):
        return [('none', _('Free Reference'))]

    @api.model
    def _default_journal(self):
        if self._context.get('default_journal_id', False):
            return self.env['oasys.journal'].browse(self._context.get('default_journal_id'))
        inv_type = self._context.get('type', 'in_invoice')
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', filter(None, map(TYPE2JOURNAL.get, inv_types))),
            ('company_id', '=', company_id),
        ]
        return self.env['oasys.journal'].search(domain, limit=1)

    @api.model
    def _default_account(self):
        if self._context.get('default_account_type', False):
            return self.env['oasys.account'].search([('internal_type', '=', self.env.context['default_account_type'])],
                                              limit=1).id

    @api.model
    def _default_currency(self):
        journal = self._default_journal()
        return journal.currency_id or journal.company_id.currency_id or self.env.user.company_id.currency_id

    name = fields.Char(string='Reference/Description', index=True, readonly=True,
                       states={'draft':[('readonly', False)]}, copy=False, help='The name that will be used on account move lines')
    origin = fields.Char(string='Source Document', help="Reference of the document that produced this invoice.",
        readonly=True, states={'draft': [('readonly', False)]})
    type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('in_invoice', 'Vendor Bill'),
        ('out_refund','Customer Refund'),
        ('in_refund','Vendor Refund'),
    ], readonly=True, index=True, change_default=True,
    default=lambda self: self._context.get('type','out_invoice'),
    track_visibility='always')
    number = fields.Char(related='move_id.name', store=True, readonly=True, copy=False)
    move_name = fields.Char(string='Journal Entry Name', readonly=False,
                            default=False, copy=False,
                            help="Technical field holding the number given to the invoice, automatically set when the invoice is validated then stored to set the same number again if the invoice is cancelled, set to draft and re-validated.")
    reference = fields.Char(string='Vendor Reference', copy=False,
                            help="The partner reference of this invoice.", readonly=True,
                            states={'draft': [('readonly', False)]})
    comment = fields.Text('Additional Information', readonly=True, states={'draft': [('readonly', False)]})

    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('cancel', 'Cancelled'),
    ], string='Status', index=True, readonly=True, default='draft',
        track_visibility='onchange', copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed Invoice.\n"
             " * The 'Pro-forma' status is used when the invoice does not have an invoice number.\n"
             " * The 'Open' status is used when user creates invoice, an invoice number is generated. It stays in the open status till the user pays the invoice.\n"
             " * The 'Paid' status is set automatically when the invoice is paid. Its related journal entries may or may not be reconciled.\n"
             " * The 'Cancelled' status is used when user cancel invoice.")
    sent = fields.Boolean(readonly=True, default=False, copy=False,
                          help="It indicates that the invoice has been sent.")
    date_invoice = fields.Date(string='Invoice Date',
                               readonly=True, states={'draft': [('readonly', False)]}, index=True,
                               help="Keep empty to use the current date", copy=False)
    date_due = fields.Date(string='Due Date',
                           readonly=True, states={'draft': [('readonly', False)]}, index=True, copy=False,
                           help="If you use payment terms, the due date will be computed automatically at the generation "
                                "of accounting entries. The payment term may compute several due dates, for example 50% "
                                "now and 50% in one month, but if you want to force a due date, make sure that the payment "
                                "term is not set on the invoice. If you keep the payment term and the due date empty, it "
                                "means direct payment.")
    partner_id = fields.Many2one('res.partner', string='Partner', change_default=True,
                                 required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 track_visibility='always')
    payment_term_id = fields.Many2one('oasys.payment.term', string='Payment Terms', oldname='payment_term',
                                      readonly=True, states={'draft': [('readonly', False)]},
                                      help="If you use payment terms, the due date will be computed automatically at the generation "
                                           "of accounting entries. If you keep the payment term and the due date empty, it means direct payment. "
                                           "The payment term may compute several due dates, for example 50% now, 50% in one month.")
    account_id = fields.Many2one('oasys.account', string='Account',
                                 required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 domain=[('deprecated', '=', False)], help="The partner account used for this invoice.",
                                 default=_default_account)
    invoice_line_ids = fields.One2many('oasys.account.invoice.line', 'invoice_id', string='Invoice Lines',
                                       oldname='invoice_line',
                                       readonly=True, states={'draft': [('readonly', False)]}, copy=True)
    # tax_line_ids = fields.One2many('oasys.invoice.tax', 'invoice_id', string='Tax Lines', oldname='tax_line',
    #                                readonly=True, states={'draft': [('readonly', False)]}, copy=True)
    move_id = fields.Many2one('oasys.account.move', string='Journal Entry',
                              readonly=True, index=True, ondelete='restrict', copy=False,
                              help="Link to the automatically generated Journal Items.")
    amount_untaxed = fields.Monetary(string='Untaxed Amount',
                                     store=True, readonly=True, compute='_compute_amount', track_visibility='always')
    amount_tax = fields.Monetary(string='Tax', store=True, readonly=True, compute='_compute_amount')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_compute_amount')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  required=True, readonly=True, states={'draft': [('readonly', False)]},
                                  default=_default_currency, track_visibility='always')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency",
                                          readonly=True)
    journal_id = fields.Many2one('oasys.journal', string='Journal',
                                 required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 default=_default_journal,
                                 domain="[('type', 'in', {'out_invoice': ['sale'], 'out_refund': ['sale'], 'in_refund': ['purchase'], 'in_invoice': ['purchase']}.get(type, [])), ('company_id', '=', company_id)]")
    company_id = fields.Many2one('res.company', string='Company', change_default=True, related='journal_id.company_id',
                                 required=True, readonly=True, store=True,
                                 default=lambda self: self.env['res.company']._company_default_get('oasys.account.invoice'))
    partner_bank_id = fields.Many2one('res.partner.bank', string='Bank Account',
                                      help='Bank Account Number to which the invoice will be paid. A Company bank account if this is a Customer Invoice or Vendor Refund, otherwise a Partner bank account number.',
                                      readonly=True, states={'draft': [('readonly', False)]})

    residual = fields.Monetary(string='Amount Due',
                               compute='_compute_residual', store=True, help="Remaining amount due.")

    user_id = fields.Many2one('res.users', string='Salesperson', track_visibility='onchange',
                              readonly=True,
                              default=lambda self: self.env.user)

    commercial_partner_id = fields.Many2one('res.partner', string='Commercial Entity', compute_sudo=True,
                                            related='partner_id.commercial_partner_id', store=True, readonly=True,
                                            help="The commercial entity that will be used on Journal Entries for this invoice")


    partner_company = fields.Char(related='partner_id.parent_id.commercial_company_name', string='Partner\'s Compnay', store=True)
    payments_widget = fields.Text(compute='_get_payment_info_JSON')
    receipt_ids = fields.Many2many('oasys.receipt','invoice_receipt_rel','invoice_id',string='Receipts')

    @api.depends('amount_untaxed','amount_tax','amount_total', 'invoice_line_ids')
    def _compute_amount(self):
        tax_per_line = []
        untaxed_amount_per_line = []
        for record in self:
            for line in record.invoice_line_ids:
                for tax in line.invoice_line_tax_ids:
                    tax_per_line.append((line.price_subtotal/100)*tax)
                untaxed_amount_per_line.append(line.price_subtotal)
            record.amount_untaxed = sum(untaxed_amount_per_line)
            record.amount_tax = sum(tax_per_line)
            record.amount_total = record.amount_untaxed - record.amount_tax


    @api.depends('amount_total', 'date_invoice','receipt_ids', 'number')
    def _compute_residual(self):
        for record in self:
            if record.state == 'open':
                record.residual = record.amount_total
                for receipt in self.env['oasys.receipt'].search([('invoice_id','=',record.id),('invoice_no','=',record.number)]):
                    if receipt and receipt.invoice_id == record.id and receipt.date == record.date_invoice:
                        record.residual = record.amount_total - receipt.amount


    @api.one
    @api.depends('receipt_ids.amount')
    def _get_payment_info_JSON(self):
        self.payments_widget = json.dumps(False)
        if self.receipt_ids:
            info = {'title': _('Less Payment'), 'outstanding': False, 'content': []}
            for receipt in self.receipt_ids:
                if self.type in ('out_invoice', 'in_refund'):
                    amount = sum([r.amount for r in receipt])
                    info['content'].append({
                        'name': receipt.name,
                        'journal_name': receipt.invoice_id.journal_id.name,
                        'amount': amount,
                        'currency': receipt.currency_id.symbol,
                        'digits': [69, receipt.currency_id.decimal_places],
                        'position': receipt.currency_id.position,
                        'date': receipt.date,
                        'ref': receipt.invoice_no,
                    })
            self.payments_widget = json.dumps(info)

    #Action to change invoice's state to draft
    @api.multi
    def action_invoice_draft(self):
        if self.filtered(lambda inv: inv.state != 'cancel'):
            raise UserError(_("Invoice must be cancelled in order to reset it to draft."))
        self.write({'state':'draft', 'date': False})

        try:
            report_invoice = self.env['report']._get_report_from_name('oasys.invoice_report')
        except IndexError:
            report_invoice = False
        return True


    @api.multi
    def invoice_line_get(self):
        res = []
        if self.type == 'out_invoice':
            for line in self.invoice_line_ids:
                move_line_dict={
                    'name': line.name.split('\n')[0][:64],
                    'price_unit': line.price_unit,
                    'quantity': line.quantity,
                    'price': line.price_subtotal,
                    'account_id': line.product_id.property_account_income_id.id,
                    'product_id': line.product_id.id,
                    'tax_ids': line.invoice_line_tax_ids,
                    'invoice_id': self.id
                }
                res.append((0,0,move_line_dict))
        elif self.type == 'in_invoice':
            for line in self.invoice_line_ids:
                move_line_dict={
                    'name': line.name.split('\n')[0][:64],
                    'price_unit': line.price_unit,
                    'quantity': line.quantity,
                    'price': line.price_subtotal,
                    'account_id': line.product_id.property_account_expense_id.id,
                    'product_id': line.product_id.id,
                    'tax_ids': line.invoice_line_tax_ids,
                    'invoice_id': self.id
                }
                res.append((0,0,move_line_dict))
        return res

    @api.multi
    def invoice_line_move_line_get(self):
        res = []
        for line in self.invoice_line_ids:

            if self.type == 'out_invoice':
                debit = line.price_subtotal
                credit = 0.00
            else:
                debit = 0.00
                credit = line.price_subtotal
            move_line_dict = {
                'name': line.name.split('\n')[0][:64],
                'quantity': line.quantity,
                'account_id': line.account_id.id,
                'product_id': line.product_id.id,
                'tax_ids': line.invoice_line_tax_ids,
                'invoice_id': line.invoice_id.id,
                'debit': debit,
                'credit': credit,
                'journal_id': self.journal_id.id,
                'date_maturity': self.date_due,
                'date': fields.Date.context_today(self),
                'partner_id': self.partner_id,
            }
            res.append((0, 0, move_line_dict))
        return res


    # def group_lines(self, iml, line):
    #     """Merge account move lines (and hence analytic lines) if invoice line hashcodes are equals"""
    #     if self.journal_id.group_invoice_lines:
    #         line2 = {}
    #         for x, y, l in line:
    #             tmp = self.inv_line_characteristic_hashcode(l)
    #             if tmp in line2:
    #                 am = line2[tmp]['debit'] - line2[tmp]['credit'] + (l['debit'] - l['credit'])
    #                 line2[tmp]['debit'] = (am > 0) and am or 0.0
    #                 line2[tmp]['credit'] = (am < 0) and -am or 0.0
    #                 # line2[tmp]['amount_currency'] += l['amount_currency']
    #                 # line2[tmp]['analytic_line_ids'] += l['analytic_line_ids']
    #                 qty = l.get('quantity')
    #                 if qty:
    #                     line2[tmp]['quantity'] = line2[tmp].get('quantity', 0.0) + qty
    #             else:
    #                 line2[tmp] = l
    #         line = []
    #         for key, val in line2.items():
    #             line.append((0, 0, val))
    #     return line

    #Ledger and journal activity
    @api.multi
    def action_move_create(self):
        for inv in self:
            if not inv.invoice_line_ids:
                raise UserError(_("Please create some invoice lines."))

            iml = inv.invoice_line_move_line_get()

            name = inv.name or '/'
            if inv.type == 'in_invoice':
                debit = 0.00
                credit = self.amount_total
            else:
                debit = self.amount_total
                credit = 0.00

            move_dict = {
                'name': name,
                'account_id': inv.account_id.id,
                'date_maturity': inv.date_due,
                'invoice_id': inv.id,
                'debit': debit,
                'credit': credit,
                'quantity': 1,
                #'tax_ids': [4,[{t.id for t in self.invoice_line_ids.invoice_line_tax_ids}]],
                'journal_id': self.journal_id.id,
                'date': fields.Date.context_today(self),
                'partner_id': self.partner_id,
            }


            move_line = []
            move_line.append((0,0,iml))
            #move_line.append((0, 0, iml2))

            move_vals = {'reference':inv.reference,
                         'journal_id':inv.journal_id.id,
                         'date':fields.Date.context_today(self),
                         'line_ids': [0,0, move_dict],
                         'narration': inv.comment}
            #raise UserError(_(str(move_dict)))
            self.env['oasys.account.move'].create(move_vals)
            #raise UserError(_(str(move_vals)))
            move = self.env['oasys.account.move'].create(move_vals)
            move.post()
            vals = {
                'move_id': int(move.id),
                'move_name': move.name,
            }
            inv.write(vals)
        return True


    @api.multi
    def invoice_print(self):
        self.sent = True
        return self.env['report'].get_action(self, 'oasys.invoice_report')


    # Delete func
    @api.multi
    def action_invoice_cancel(self):
        if self.filtered(lambda inv: inv.state not in ['draft','open']):
            raise UserError(_("Invoice must be in draft or open state in order to be cancelled."))
        return self.action_cancel()

    @api.multi
    def action_cancel(self):
        moves = self.env['oasys.account.move']
        for inv in self:
            if inv.move_id:
                moves += inv.move_id
        self.write({'state':'cancel','move_id':False})
        if moves:
            moves.button_cancel()
            moves.unlink()
        return True

    @api.multi
    def unlink(self):
        for invoice in self:
            if invoice.state not in ('draft', 'cancel'):
                raise UserError(_('You cannot delete an invoice which is not draft or cancelled. You should refund it instead.'))
            elif invoice.move_name:
                raise UserError(_('You cannot delete an invoice after it has been validated (and received a number). You can set it back to "Draft" state and modify its content, then re-confirm it.'))
        return super(AccountInvoice, self).unlink()

    #Action to change invoice's state to open
    @api.multi
    def action_invoice_open(self):
        to_open_invoices = self.filtered(lambda inv: inv.state != 'open')
        if to_open_invoices.filtered(lambda inv: inv.state != 'draft'):
            raise UserError(_("Invoice must be in draft state in order to validate it."))
        to_open_invoices.action_date_assign()
        #to_open_invoices.action_move_create()
        return to_open_invoices.invoice_validate()

    @api.multi
    def action_date_assign(self):
        for inv in self:
            inv._onchange_payment_term_date_invoice()
        return True

    #TODO UNDERSTAND THIS SHIT
    #Defines due date based on payment term and date of invoice's issuance
    @api.onchange('payment_term_id', 'date_invoice')
    def _onchange_payment_term_date_invoice(self):
        date_invoice = self.date_invoice
        if not date_invoice:
            date_invoice = fields.Date.context_today(self)
            if not self.payment_term_id:
                # When no payment term defined. Automatically set to immediate payent
                self.date_due = self.date_due or date_invoice
            else:
                pterm = self.payment_term_id
                pterm_list = \
                pterm.with_context(currency_id=self.company_id.currency_id.id).compute(value=1, date_ref=date_invoice)[
                    0]
                self.date_due = max(line[0] for line in pterm_list)

    #creates new record with similar values that can be viewed by partner company as a bill.
    @api.multi
    def action_bill_partner(self):
        for inv in self:
            user_id = self.env['res.users'].search([('name','=',inv.partner_id.name)],order='id desc',limit=1).id
            company_id = inv.partner_id.parent_id.company_id.id
            journal_id = self.env['oasys.journal'].search([('type','=','purchase'),('company_id','=',company_id)], limit=1).id
            account_id = self.env['oasys.account'].search([('internal_type','=','payable'),('company_id','=',company_id)],limit=1).id
            self.env['oasys.account.invoice'].create({
                                                      'invoice_line_ids':inv.invoice_line_get(),
                                                      'sent':True,
                                                      'state':'open',
                                                      'type':'in_invoice',
                                                      'partner_id':inv.user_id.partner_id.id,
                                                      'user_id':user_id,
                                                      'journal_id': journal_id,
                                                      'account_id':account_id,
                                                      'company_id':company_id,
                                                      'date_invoice': fields.Date.context_today(self),
                                                      'date_due': inv.date_due,
                                                      'partner_company': inv.company_id.name,
                                                      'origin':str(inv.id),
                                                      'amount_untaxed': inv.amount_untaxed,
                                                      'amount_tax': inv.amount_tax,
                                                      'residual': inv.residual,
                                                      'amount_total':inv.amount_total
                                                      })
            partner_invoice = self.env['oasys.account.invoice'].search([('origin','=',str(inv.id))],limit=1)
            #partner_invoice.action_move_create()

        return True

    def _check_invoice_reference(self):
        for invoice in self:
            #refuse to validate a vendor bill/refund if there already exists one with the same reference for the same partner,
            #because it's probably a double encoding of the same bill/refund
            if invoice.type in ('in_invoice', 'in_refund') and invoice.reference:
                if self.search([('type', '=', invoice.type), ('reference', '=', invoice.reference), ('company_id', '=', invoice.company_id.id), ('commercial_partner_id', '=', invoice.commercial_partner_id.id), ('id', '!=', invoice.id)]):
                    raise UserError(_("Duplicated vendor reference detected. You probably encoded twice the same vendor bill/refund."))

    #Changes invoice's state to open
    @api.multi
    def invoice_validate(self):
        self._check_invoice_reference()
        self.action_bill_partner()

        return self.write({'sent':True,'state': 'open', 'date_invoice': fields.Date.context_today(self)})

class AccountInvoiceLine(models.Model):
    _name = 'oasys.account.invoice.line'
    _description = 'Invoice Line'
    _order = " id"

    @api.model
    def _default_account(self):
        if self._context.get('journal_id'):
            journal = self.env['oasys.journal'].browse(self._context.get('journal_id'))
            if self._context.get('type') in ('out_invoice', 'in_refund'):
                return journal.default_credit_account_id.id
            return journal.default_debit_account_id.id

    name = fields.Text(string='Description', required=True, related='product_id.description')
    origin = fields.Char(string='Source Document',
                         help="Reference of the document that produced this invoice.")
    sequence = fields.Integer(default=10,
                              help="Gives the sequence of this line when displaying the invoice.")
    invoice_id = fields.Many2one('oasys.account.invoice', string='Invoice Reference',
                                 ondelete='cascade', index=True)
    product_id = fields.Many2one('oasys.product', string='Product',
                                 ondelete='restrict', index=True)
    account_id = fields.Many2one('oasys.account', string='Account',
                                 required=True, domain=[('deprecated', '=', False)],
                                 default=_default_account,
                                 help="The income or expense account related to the selected product.")
    price_unit = fields.Monetary(string='Unit Price', required=True, digits=dp.get_precision('Product Price'), related='product_id.list_price', currency_field='company_currency_id')
    price_subtotal = fields.Monetary(string='Amount',
                                     store=True, readonly=True, compute='_compute_price')

    quantity = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'),
                            required=True, default=1)
    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Discount'),
                            default=0.0)
    invoice_line_tax_ids = fields.Many2many('oasys.tax',
                                            'account_invoice_line_tax', 'invoice_line_id', 'tax_id',
                                            string='Taxes',
                                            domain=[('type_tax_use', '!=', 'none'), '|', ('active', '=', False),
                                                    ('active', '=', True)], oldname='invoice_line_tax_id')
    company_id = fields.Many2one('res.company', string='Company',
                                 related='invoice_id.company_id', store=True, readonly=True, related_sudo=False)
    partner_id = fields.Many2one('res.partner', string='Partner',
                                 related='invoice_id.partner_id', store=True, readonly=True, related_sudo=False)
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True, related_sudo=False)
    company_currency_id = fields.Many2one('res.currency', related='invoice_id.company_currency_id', readonly=True,
                                          related_sudo=False)

    @api.depends('price_unit', 'quantity','discount')
    def _compute_price(self):
        for record in self:
            initial_price = record.price_unit * record.quantity
            discount = (initial_price/100)*record.discount
            record.price_subtotal = initial_price - discount


class Receipt(models.Model):
    _name = 'oasys.receipt'
    _description = 'Cash Receipt'
    _order = 'date desc'

    @api.multi
    def _default_payment_method(self):
        return self.env['oasys.payment.method'].search([('payment_type','=','inbound'),('is_default','=',True)],limit=1).id

    @api.multi
    def _get_invoice_id(self):
        if self.env.context.get('invoice_id'):
            return self.env.context.get('invoice_id')

    @api.multi
    def _get_partner_id(self):
        if self.env.context.get('invoice_id'):
            return self.env['oasys.account.invoice'].search([('id','=',int(self.env.context.get('invoice_id')))]).partner_id

    @api.multi
    def _get_partner_name(self):
        if self.env.context.get('invoice_id'):
            return self.env['oasys.account.invoice'].search(
                [('id', '=', int(self.env.context.get('invoice_id')))]).partner_id.name

    @api.multi
    def _get_partner_company(self):
        if self.env.context.get('invoice_id'):
            return self.env['oasys.account.invoice'].search(
                [('id', '=', int(self.env.context.get('invoice_id')))]).partner_id.parent_id.company_id

    @api.multi
    def _get_user_id(self):
        if self.env.context.get('invoice_id'):
            return self.env['oasys.account.invoice'].search([('id','=',int(self.env.context.get('invoice_id')))]).user_id

    @api.multi
    def _get_company_id(self):
        if self.env.context.get('invoice_id'):
            return self.env['oasys.account.invoice'].search([('id','=',int(self.env.context.get('invoice_id')))]).company_id
    @api.multi
    def _get_invoice_no(self):
        if self.env.context.get('invoice_no'):
            return self.env.context.get('invoice_no')

    @api.multi
    def _get_invoice_lines(self):
        if self.env.context.get('invoice_line_ids'):
            return self.env.context.get('invoice_line_ids')

    @api.multi
    def _get_residual(self):
        if self.env.context.get('residual'):
            return self.env.context.get('residual')

    name = fields.Char(string='OR Number:', required=False, readonly=True)
    date = fields.Datetime(string="Issued on:", default=fields.Date.context_today, readonly=True)
    type = fields.Many2one('oasys.payment.method',domain=[('payment_type','=','inbound')],string='Type of transaction', default=_default_payment_method)
    invoice_id = fields.Many2one('oasys.account.invoice',required=True, readonly=True, ondelete='cascade', index=True, default=_get_invoice_id)
    partner_id = fields.Many2one('res.partner',related='invoice_id.partner_id',string='Partner', required=True, readonly=True, default = _get_partner_id)
    user_id = fields.Many2one('res.users',related='invoice_id.user_id',string='User', required=True, readonly=True, default = _get_user_id)
    invoice_no = fields.Char(related='invoice_id.number', string='Invoice Reference',store=True,default=_get_invoice_no)
    customer = fields.Char(related='partner_id.name', readonly=True, default = _get_partner_name)
    company_id = fields.Many2one('res.company',related='invoice_id.company_id', readonly=True, default=_get_company_id)
    currency_id = fields.Many2one('res.currency',related='company_id.currency_id')
    partner_company_id = fields.Many2one('res.company', related='partner_id.parent_id.company_id', readonly=True,default = _get_partner_company)
    invoice_line_ids = fields.One2many('oasys.account.invoice.line', 'invoice_id', string='Receipt Lines',
                                       oldname='receipt_line',
                                       readonly=True, copy=True,related = 'invoice_id.invoice_line_ids', default=_get_invoice_lines)
    amount = fields.Monetary(currency_field='currency_id', string='Amount')
    residual = fields.Monetary(currency_field='currency_id', string='Balance', default=_get_residual)



    # OR Number sequencing
    @api.model
    def create(self, vals):
        record = super(Receipt, self).create(vals)
        company_id = record.company_id
        year = datetime.strptime(record.date, DEFAULT_SERVER_DATETIME_FORMAT).strftime('%y')
        rec = self.env['oasys.receipt'].search(
            [('company_id', '=', company_id.id), ('id', '=', record.id)], order='id desc', limit=1).id
        if rec:
            val = rec + 1
        else:
            val = 1
        record['name'] = '%s-%s-%s' % (company_id.id, year, str(val).rjust(9, '0'))
        diff = record.residual - record.amount
        state = 'open'
        if diff == 0.0:
            state = 'paid'

        self.env['oasys.account.invoice'].search([('id','=',record.invoice_id.id),('number','=',record.invoice_no)], limit=1).write({'receipt_ids': (4,[record.id]),'residual':diff,'state': state})

        return record

# class AccountInvoiceTax(models.Model):
#     _name = 'oasys.invoice.tax'
#     _description = 'Invoice Tax'
#     _order = 'sequence'
#
#     invoice_id = fields.Many2one('oasys.account.invoice', string='Invoice', ondelete='cascade', index=True)
#     name = fields.Char(string='Tax Description', required=True, related='tax_id.description')
#     tax_id = fields.Many2one('oasys.tax', string='Tax', ondelete='restrict')
#     account_id = fields.Many2one('oasys.account', string='Tax Account', required=True,
#                                  domain=[('deprecated', '=', False)], related='tax_id.account_id')
#     amount = fields.Monetary()
#     manual = fields.Boolean(default=False)
#     sequence = fields.Integer(help="Gives the sequence order when displaying a list of invoice tax.")
#     company_id = fields.Many2one('res.company', string='Company', related='account_id.company_id', store=True,
#                                  readonly=True)
#     currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True, readonly=True)
#     base = fields.Monetary(string='Base', compute='_compute_base_amount')



class AccountPaymentTerm(models.Model):
    _name = 'oasys.payment.term'
    _description = 'Payment Term'
    _order = 'name'

    def _default_line_ids(self):
        return [(0, 0, {'value': 'balance', 'value_amount': 0.0, 'sequence': 9, 'days': 0,
                        'option': 'day_after_invoice_date'})]

    name = fields.Char(string='Payment Terms', translate=True, required=True)
    active = fields.Boolean(default=True,
                            help="If the active field is set to False, it will allow you to hide the payment term without removing it.")
    note = fields.Text(string='Description on the Invoice', translate=True)
    line_ids = fields.One2many('oasys.payment.term.line', 'payment_id', string='Terms', copy=True,
                               default=_default_line_ids)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)

class AccountPaymentTermLine(models.Model):
    _name = 'oasys.payment.term.line'
    _description = 'Payment term Line'
    _order = 'sequence, id'

    @api.multi
    def _get_default_payment(self):
        if self.env.context.get('default_payment_id'):
            return self.env['oasys.payment.term'].search(
                [('id', '=', self.env.context['default_payment_id'])], limit=1).id

    value = fields.Selection([
        ('balance', 'Balance'),
        ('percent', 'Percent'),
        ('fixed', 'Fixed Amount')
    ], string='Type', required=True, default='balance',
        help="Select here the kind of valuation related to this payment term line.")
    value_amount = fields.Float(string='Value', digits=dp.get_precision('Payment Terms'),
                                help="For percent enter a ratio between 0-100.")
    days = fields.Integer(string='Number of Days', required=True, default=0)
    option = fields.Selection([
        ('day_after_invoice_date', 'Day(s) after the invoice date'),
        ('fix_day_following_month', 'Day(s) after the end of the invoice month (Net EOM)'),
        ('last_day_following_month', 'Last day of following month'),
        ('last_day_current_month', 'Last day of current month'),
    ],
        default='day_after_invoice_date', required=True, string='Options'
    )
    payment_id = fields.Many2one('oasys.payment.term', string='Payment Terms', required=True, index=True,
                                 ondelete='cascade')
    sequence = fields.Integer(default=10, help="Gives the sequence order when displaying a list of payment term lines.")

    @api.one
    @api.constrains('value', 'value_amount')
    def _check_percent(self):
        if self.value == 'percent' and (self.value_amount < 0.0 or self.value_amount > 100.0):
            raise ValidationError(_('Percentages for Payment Terms Line must be between 0 and 100.'))

    @api.onchange('option')
    def _onchange_option(self):
        if self.option in ('last_day_current_month', 'last_day_following_month'):
            self.days = 0

