from odoo import api, models


class PawnNotification(models.AbstractModel):
    _name = "pawn.notification"
    _description = "Pawnshop Notification Routines"

    @api.model
    def _get_candidates(self):
        return self.env["pawn.ticket"]

    @api.model
    def cron_maturity_reminder(self):
        # TODO: implement selection logic (e.g., maturity in 3 days)
        return True

    @api.model
    def cron_grace_warning(self):
        # TODO: implement selection logic for grace period ending
        return True

    @api.model
    def cron_forfeiture_notice(self):
        # TODO: implement selection logic for forfeiture
        return True

    @api.model
    def cron_auction_announcement(self):
        # TODO: implement selection logic for weekly auction announcements
        return True
