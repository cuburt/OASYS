from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
import odoo.addons.decimal_precision as dp
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT



#THE ITEMS IN THE JOURNAL, LEDGER, ETC.


class AccountMove(models.Model):
    _name = 'OASYS.account.move'
    _description = 'Account Entry'
    _order = 'date desc, id desc'

    @api.multi
    @api.depends('name', 'state')
    def name_get(self):
        result = []
        for move in self:
            if move.state == 'draft':
                name = '* ' + str(move.id)
            else:
                name = move.name
            result.append((move.id, name))
        return result

    @api.multi
    @api.depends('line_ids.debit', 'line_ids.credit')
    def _amount_compute(self):
        for move in self:
            total = 0.0
            for line in move.line_ids:
                total += line.debit
            move.amount = total

    @api.one
    @api.depends('company_id')
    def _compute_currency(self):
        self.currency_id = self.company_id.currency_id or self.env.user.company_id.currency_id

    @api.multi
    def _get_default_journal(self):
        if self.env.context.get('default_journal_type'):
            return self.env['OASYS.journal'].search(['&',('type', '=', self.env.context['default_journal_type']),('code','=','MISC'),('company_id','=',self.env.user.company_id.id)],
                                                      limit=1).id

    @api.multi
    @api.depends('line_ids.partner_id')
    def _compute_partner_id(self):
        for move in self:
            partner = move.line_ids.mapped('partner_id')
            move.partner_id = partner.id if len(partner) == 1 else False

    name = fields.Char(string='Number', required=True, copy=False,default='/')
    reference = fields.Char(string='Reference', copy=False)
    date = fields.Date(required=True, states={'posted': [('readonly', True)]}, index=True, default=fields.Date.context_today)
    journal_id = fields.Many2one('OASYS.journal', string='Journal', required=True, states={'posted': [('readonly', True)]}, default=_get_default_journal)
    currency_id = fields.Many2one('res.currency', compute='_compute_currency', store=True, string="Currency")
    state = fields.Selection([('draft', 'Unposted'), ('posted', 'Posted')], string='Status',
                             required=True, readonly=True, copy=False, default='draft',
                             help='All manually created new journal entries are usually in the status \'Unposted\', '
                                  'but you can set the option to skip that status on the related journal. '
                                  'In that case, they will behave as journal entries automatically created by the '
                                  'system on document validation (invoices, bank statements...) and will be created '
                                  'in \'Posted\' status.')
    line_ids = fields.One2many('OASYS.account.move.line', 'move_id', string='Journal Items',
                               states={'posted': [('readonly', True)]}, copy=True)
    partner_id = fields.Many2one('res.partner', compute='_compute_partner_id', string="Partner", store=True, readonly=True)
    company_id = fields.Many2one('res.company', related='journal_id.company_id', string='Company', store=True,
                                 readonly=True)
    amount = fields.Monetary(compute='_amount_compute', store=True)
    narration = fields.Text(string='Internal Note')

    #matched_percentage = fields.Float('Percentage Matched', compute='_compute_matched_percentage', digits=0, store=True, readonly=True, help="Technical field used in cash basis method")
    #connected bank
    #statement_line_id = fields.Many2one('account.bank.statement.line', index=True, string='Bank statement line reconciled with this entry', copy=False, readonly=True)
    #for search purposes
    dummy_account_id = fields.Many2one('OASYS.account', related='line_ids.account_id', string='Account', store=False, readonly=True)

    @api.multi
    def post(self):
        # invoice = self._context.get('invoice', False)
        self._post_validate()
        for move in self:
            #move.line_ids.create_analytic_lines()
            if move.name == '/':
                date = datetime.strptime(move.date, DEFAULT_SERVER_DATE_FORMAT)
                year = date.strftime('%Y')
                journal = move.journal_id
                rjust = 5 - len(str(move.id))
                move.name = '%s/%s/%s' % (journal.code,year,str(move.id).rjust(rjust,'0'))
                # if invoice and invoice.move_name and invoice.move_name != '/':
                #     new_name = invoice.move_name
                # else:
                #     # if journal.sequence_id:
                #     #     # If invoice is actually refund and journal has a refund_sequence then use that one or use the regular one
                #     #     sequence = journal.sequence_id
                #     #     if invoice and invoice.type in ['out_refund', 'in_refund'] and journal.refund_sequence:
                #     #         if not journal.refund_sequence_id:
                #     #             raise UserError(_('Please define a sequence for the refunds'))
                #     #         sequence = journal.refund_sequence_id
                #     #
                #     #     new_name = sequence.with_context(ir_sequence_date=move.date).next_by_id()
                #     # else:
                #     #     raise UserError(_('Please define a sequence on the journal.'))
                #     pass
            else: pass

        return self.write({'state': 'posted'})

    @api.multi
    def button_cancel(self):
        for move in self:
            if not move.journal_id.update_posted:
                raise UserError(_('You cannot modify a posted entry of this journal.\nFirst you should set the journal to allow cancelling entries.'))
        if self.ids:
            self.check_access_rights('write')
            self.check_access_rule('write')
            self._check_lock_date()
            self._cr.execute('UPDATE oasys_account_move '\
                       'SET state=%s '\
                       'WHERE id IN %s', ('draft', tuple(self.ids),))
            self.invalidate_cache()
        self._check_lock_date()
        return True

    @api.multi
    def _check_lock_date(self):
        for move in self:
            lock_date = max(move.company_id.period_lock_date, move.company_id.fiscalyear_lock_date)
            if self.user_has_groups('OASYS.group_oasys_adviser'):
                lock_date = move.company_id.fiscalyear_lock_date
            if move.date <= lock_date:
                if self.user_has_groups('OASYS.group_oasys_adviser'):
                    message = _("You cannot add/modify entries prior to and inclusive of the lock date %s") % (lock_date)
                else:
                    message = _("You cannot add/modify entries prior to and inclusive of the lock date %s. Check the company settings or ask someone with the 'Adviser' role") % (lock_date)
                raise UserError(message)
        return True

    @api.multi
    def _post_validate(self):
        for move in self:
            if move.line_ids:
                if not all([x.company_id.id == move.company_id.id for x in move.line_ids]):
                    raise UserError(_("Cannot create moves for different companies."))
        self.assert_balanced()
        return self._check_lock_date()#double entry items. Initial items. The actual bloody items.

    @api.multi
    def assert_balanced(self):
        if not self.ids:
            return True
        prec = self.env['decimal.precision'].precision_get('Account')

        self._cr.execute("""\
            SELECT      move_id
            FROM        oasys_account_move_line
            WHERE       move_id in %s
            GROUP BY    move_id
            HAVING      abs(sum(debit) - sum(credit)) > %s
            """, (tuple(self.ids), 10 ** (-max(5, prec))))
        if len(self._cr.fetchall()) != 0:
            raise UserError(_("Cannot create unbalanced journal entry."))
        return True

class AccountMoveLine(models.Model):
    _name = "OASYS.account.move.line"
    _description = "Journal Item"
    _order = "date desc, id desc"

    @api.depends('debit', 'credit')
    def _store_balance(self):
        for line in self:
            line.balance = line.debit - line.credit

    @api.model
    def _get_currency(self):
        currency = False
        context = self._context or {}
        if context.get('default_journal_id', False):
            currency = self.env['account.journal'].browse(context['default_journal_id']).currency_id
        return currency

    @api.one
    @api.depends('move_id.line_ids')
    def _get_counterpart(self):
        counterpart = set()
        for line in self.move_id.line_ids:
            if (line.account_id.code != self.account_id.code):
                counterpart.add(line.account_id.code)
        if len(counterpart) > 2:
            counterpart = list(counterpart)[0:2] + ["..."]
        self.counterpart = ",".join(counterpart)

    name = fields.Char(required=True, string="Label")
    quantity = fields.Float(digits=dp.get_precision('Product Unit of Measure'),
                            help="The optional quantity expressed by this line, eg: number of product sold. The quantity is not a legal requirement but is very useful for some reports.")
    # product_uom_id = fields.Many2one('product.uom', string='Unit of Measure')
    product_id = fields.Many2one('OASYS.product', string='Product')
    debit = fields.Monetary(default=0.0, currency_field='currency_id')
    credit = fields.Monetary(default=0.0, currency_field='currency_id')
    balance = fields.Monetary(compute='_store_balance', store=True, currency_field='currency_id',
                              help="Technical field holding the debit - credit in order to open meaningful graph views from reports")

    currency_id = fields.Many2one('res.currency', string='Currency', default=_get_currency,
                                 help="The optional other currency if it is a multi-currency entry.")
    account_id = fields.Many2one('OASYS.account', string='Account', required=True, index=True,
                                 ondelete="cascade", domain=[('deprecated', '=', False)],
                                 default=lambda self: self._context.get('account_id', False))
    move_id = fields.Many2one('OASYS.account.move', string='Journal Entry', ondelete="cascade",
                                help="The move of this entry line.", index=True, required=True, auto_join=True)
    narration = fields.Text(related='move_id.narration', string='Narration')
    reference = fields.Char(related='move_id.reference', string='Reference', store=True, copy=False, index=True)
    journal_id = fields.Many2one('OASYS.journal', related='move_id.journal_id', string='Journal',
                                 index=True, store=True, copy=False)  # related is required

    date_maturity = fields.Date(string='Due date', index=True, required=True,
                                help="This field is used for payable and receivable journal entries. You can put the limit date for the payment of this line.")
    date = fields.Date(related='move_id.date', string='Date', index=True, store=True, copy=False)  # related is required
    tax_ids = fields.Many2many('OASYS.tax', string='Taxes',
                               domain=['|', ('active', '=', False), ('active', '=', True)])
    company_id = fields.Many2one('res.company', related='account_id.company_id', string='Company', store=True)
    counterpart = fields.Char("Counterpart", compute='_get_counterpart',
                              help="Compute the counter part accounts of this journal item for this journal entry. This can be needed in reports.")

    # # TODO: put the invoice link and partner_id on the account_move
    invoice_id = fields.Many2one('OASYS.invoice', oldname="invoice")
    partner_id = fields.Many2one('res.partner', string='Partner', ondelete='restrict')



