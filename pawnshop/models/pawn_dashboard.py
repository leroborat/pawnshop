from odoo import api, fields, models


class PawnDashboard(models.TransientModel):
    _name = "pawn.dashboard"
    _description = "Pawnshop Dashboard"

    name = fields.Char(default="Pawnshop Dashboard")
    branch_id = fields.Many2one("pawn.branch", string="Branch")

    active_tickets = fields.Integer(compute="_compute_metrics", store=False)
    due_today = fields.Integer(compute="_compute_metrics", store=False)
    in_grace = fields.Integer(compute="_compute_metrics", store=False)
    overdue = fields.Integer(compute="_compute_metrics", store=False)
    forfeited = fields.Integer(compute="_compute_metrics", store=False)
    principal_month = fields.Monetary(compute="_compute_metrics", currency_field="currency_id", store=False)
    interest_month = fields.Monetary(compute="_compute_metrics", currency_field="currency_id", store=False)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id.id)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if "branch_id" in fields_list and not vals.get("branch_id"):
            user = self.env.user
            vals["branch_id"] = user.branch_ids[:1].id if hasattr(user, "branch_ids") else False
        return vals

    @api.depends("branch_id")
    def _compute_metrics(self):
        Ticket = self.env["pawn.ticket"].sudo()
        AccountMove = self.env["account.move"].sudo()
        today = fields.Date.context_today(self)
        for rec in self:
            domain_base = []  # for pawn.ticket (has branch_id)
            if rec.branch_id:
                domain_base.append(("branch_id", "=", rec.branch_id.id))

            rec.active_tickets = Ticket.search_count(domain_base + [("state", "in", ["active", "renewed"])])
            rec.due_today = Ticket.search_count(domain_base + [("date_maturity", "=", today), ("state", "in", ["active", "renewed"])])
            rec.in_grace = Ticket.search_count(domain_base + [("state", "=", "active"), ("date_maturity", "<", today)])
            rec.overdue = Ticket.search_count(domain_base + [("state", "=", "forfeited")])
            rec.forfeited = Ticket.search_count(domain_base + [("state", "=", "forfeited")])

            first_day = today.replace(day=1)
            inv_domain = [("move_type", "=", "out_invoice"), ("invoice_date", ">=", first_day)]
            # Filter by branch via the related pawn ticket if available
            if rec.branch_id:
                inv_domain.append(("pawn_ticket_id.branch_id", "=", rec.branch_id.id))
            # Consider posted invoices only for KPI stability
            inv_domain.append(("state", "=", "posted"))
            sums = AccountMove.read_group(inv_domain, ["amount_untaxed:sum", "amount_tax:sum"], [])
            principal = sums[0].get("amount_untaxed_sum", 0.0) if sums else 0.0
            interest = sums[0].get("amount_tax_sum", 0.0) if sums else 0.0
            rec.principal_month = principal
            rec.interest_month = interest

    def action_open_tickets(self):
        self.ensure_one()
        action = self.env.ref("pawnshop.action_pawn_ticket").read()[0]
        domain = [("state", "in", ["active", "renewed"])]
        if self.branch_id:
            domain.append(("branch_id", "=", self.branch_id.id))
        action["domain"] = domain
        return action

    def action_open_due_today(self):
        self.ensure_one()
        action = self.env.ref("pawnshop.action_pawn_ticket").read()[0]
        today = fields.Date.context_today(self)
        domain = [("date_maturity", "=", today), ("state", "in", ["active", "renewed"])]
        if self.branch_id:
            domain.append(("branch_id", "=", self.branch_id.id))
        action["domain"] = domain
        return action

    def action_open_overdue(self):
        self.ensure_one()
        action = self.env.ref("pawnshop.action_pawn_ticket").read()[0]
        today = fields.Date.context_today(self)
        domain = [("date_maturity", "<", today), ("state", "in", ["active", "renewed"])]
        if self.branch_id:
            domain.append(("branch_id", "=", self.branch_id.id))
        action["domain"] = domain
        return action

    @api.model
    def get_metrics(self, branch_id=False):
        Ticket = self.env["pawn.ticket"].sudo()
        LoanBook = self.env["pawn.loan.book.report"].sudo()
        AccountMove = self.env["account.move"].sudo()
        today = fields.Date.context_today(self)
        domain_ticket = []
        if branch_id:
            domain_ticket.append(("branch_id", "=", int(branch_id)))

        # KPIs
        active_tickets = Ticket.search_count(domain_ticket + [("state", "in", ["active", "renewed"])])
        due_today = Ticket.search_count(domain_ticket + [("date_maturity", "=", today), ("state", "in", ["active", "renewed"])])
        in_grace = Ticket.search_count(domain_ticket + [("state", "=", "active"), ("date_maturity", "<", today)])
        overdue = Ticket.search_count(domain_ticket + [("state", "in", ["renewed", "active"]), ("date_maturity", "<", today)])
        forfeited = Ticket.search_count(domain_ticket + [("state", "=", "forfeited")])

        # Monthly sums (posted customer invoices linked to tickets)
        first_day = today.replace(day=1)
        inv_domain = [("move_type", "=", "out_invoice"), ("invoice_date", ">=", first_day), ("state", "=", "posted")]
        if branch_id:
            inv_domain.append(("pawn_ticket_id.branch_id", "=", int(branch_id)))
        moves = AccountMove.search(inv_domain)
        principal_month = sum(m.amount_untaxed for m in moves)
        interest_month = sum(m.amount_tax for m in moves)

        # Aging buckets composition (loan book report has 'aging_bucket')
        buckets = ["current", "due_soon", "grace", "overdue", "matured"]
        domain_lb = []
        if branch_id:
            domain_lb.append(("branch_id", "=", int(branch_id)))
        bucket_counts = {b: LoanBook.search_count(domain_lb + [("aging_bucket", "=", b)]) for b in buckets}

        # 14-day trends (tickets created, redeemed, renewed)
        from datetime import timedelta
        last_n = 14
        label_dates = [today - timedelta(days=i) for i in range(last_n - 1, -1, -1)]
        labels = [fields.Date.to_string(d) for d in label_dates]
        date_to_label = {lbl: idx for idx, lbl in enumerate(labels)}

        def _series(domain_extra, date_field):
            dom = list(domain_ticket) + domain_extra + [(date_field, ">=", labels[0]), (date_field, "<=", labels[-1])]
            groups = Ticket.read_group(dom, [], [f"{date_field}:day"])  # group only, count via __count
            counts = [0] * len(labels)
            for g in groups:
                day = g.get(f"{date_field}:day")
                lbl = day if isinstance(day, str) else fields.Date.to_string(day)
                if lbl in date_to_label:
                    counts[date_to_label[lbl]] = g.get("__count", 0)
            return counts

        created_series = _series([], "date_created")
        redeemed_series = _series([("state", "=", "redeemed")], "date_redeemed")
        renewed_series = _series([("state", "=", "renewed")], "date_maturity")  # proxy if you store renewal date elsewhere

        return {
            "active_tickets": active_tickets,
            "due_today": due_today,
            "in_grace": in_grace,
            "overdue": overdue,
            "forfeited": forfeited,
            "principal_month": principal_month,
            "interest_month": interest_month,
            "loan_book_buckets": bucket_counts,
            "today": fields.Date.to_string(today),
            "trend": {
                "labels": labels,
                "created": created_series,
                "redeemed": redeemed_series,
                "renewed": renewed_series,
            },
        }
