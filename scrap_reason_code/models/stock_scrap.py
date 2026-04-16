# Copyright (C) 2019 IBM Corp.
# Copyright (C) 2019 Open Source Integrators
# Copyright 2023 ForgeFlow S.L. (https://www.forgeflow.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    reason_code_id = fields.Many2one(
        comodel_name="scrap.reason.code",
        domain="[('id', 'in', allowed_reason_code_ids)]",
    )
    allowed_reason_code_ids = fields.Many2many(
        comodel_name="scrap.reason.code",
        compute="_compute_allowed_reason_code_ids",
    )

    scrap_location_id = fields.Many2one(
        'stock.location', 'Scrap Location',
        compute='_compute_scrap_location_id', store=True, required=True, precompute=True,
        domain="[('usage', '=', 'inventory')]", check_company=True, readonly=False)
   
    @api.depends("product_id", "product_id.categ_id")
    def _compute_allowed_reason_code_ids(self):
        for rec in self:
            codes = self.env["scrap.reason.code"]
            if rec.product_id:
                codes = codes.search(
                    [
                        "|",
                        ("product_category_ids", "=", False),
                        ("product_category_ids", "in", rec.product_id.categ_id.id),
                    ]
                )
            rec.allowed_reason_code_ids = codes

    @api.constrains("reason_code_id", "product_id")
    def _check_reason_code_id(self):
        for rec in self:
            if (
                rec.reason_code_id
                and rec.reason_code_id not in rec.allowed_reason_code_ids
            ):
                raise ValidationError(
                    _(
                        "The selected reason code is not allowed for this "
                        "product category."
                    )
                )

    def _prepare_move_values(self):
        res = super()._prepare_move_values()
        res["reason_code_id"] = self.reason_code_id.id
        return res

    @api.depends('reason_code_id')
    def _compute_scrap_location_id(self):
        for scrap in self:
            if scrap.reason_code_id and scrap.reason_code_id.location_id:
                scrap.scrap_location_id = scrap.reason_code_id.location_id
            else:
                super(StockScrap, scrap)._compute_scrap_location_id()
