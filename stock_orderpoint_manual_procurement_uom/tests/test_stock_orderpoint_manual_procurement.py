# Copyright 2018-20 ForgeFlow S.L. (https://www.forgeflow.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import common


class TestStockWarehouseOrderpoint(common.TransactionCase):
    def setUp(self):
        super(TestStockWarehouseOrderpoint, self).setUp()

        # Refs
        self.group_stock_manager = self.env.ref("stock.group_stock_manager")
        self.group_purchase_manager = self.env.ref("purchase.group_purchase_manager")
        self.vendor = self.env.ref(
            "stock_orderpoint_manual_procurement.product_supplierinfo_product_7"
        )  # noqa
        self.group_change_procure_qty = self.env.ref(
            "stock_orderpoint_manual_procurement." "group_change_orderpoint_procure_qty"
        )
        self.company1 = self.env.ref("base.main_company")

        # Get required Model
        self.reordering_rule_model = self.env["stock.warehouse.orderpoint"]
        self.product_model = self.env["product.product"]
        self.purchase_model = self.env["purchase.order"]
        self.purchase_line_model = self.env["purchase.order.line"]
        self.user_model = self.env["res.users"]
        self.product_ctg_model = self.env["product.category"]
        self.stock_change_model = self.env["stock.change.product.qty"]
        self.make_procurement_orderpoint_model = self.env["make.procurement.orderpoint"]

        # Create users
        self.user = self._create_user(
            "user_1",
            [
                self.group_stock_manager,
                self.group_change_procure_qty,
                self.group_purchase_manager,
            ],
            self.company1,
        )
        # Get required Model data
        self.product_uom = self.env.ref("uom.product_uom_unit")
        self.location = self.env.ref("stock.stock_location_stock")
        self.product = self.env.ref("product.product_product_7")
        self.dozen = self.env.ref("uom.product_uom_dozen")

        # Create Product category and Product
        self.product_ctg = self._create_product_category()
        self.product = self._create_product()

        # Add default quantity
        quantity = 20.00
        self._update_product_qty(self.product, quantity)

        # Create Reordering Rule
        self.reorder = self.create_orderpoint()

    def _create_user(self, login, groups, company):
        """Create a user."""
        group_ids = [group.id for group in groups]
        user = self.user_model.with_context({"no_reset_password": True}).create(
            {
                "name": "Test User",
                "login": login,
                "password": "demo",
                "email": "test@yourcompany.com",
                "company_id": company.id,
                "company_ids": [(4, company.id)],
                "groups_id": [(6, 0, group_ids)],
            }
        )
        return user

    def _create_product_category(self):
        """Create a Product Category."""
        product_ctg = self.product_ctg_model.create({"name": "test_product_ctg"})
        return product_ctg

    def _create_product(self):
        """Create a Product."""
        product = self.product_model.create(
            {
                "name": "Test Product",
                "categ_id": self.product_ctg.id,
                "type": "product",
                "uom_id": self.product_uom.id,
                "variant_seller_ids": [(6, 0, [self.vendor.id])],
            }
        )
        return product

    def _update_product_qty(self, product, quantity):
        """Update Product quantity."""
        change_product_qty = self.stock_change_model.create(
            {
                "product_id": product.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "new_quantity": quantity,
            }
        )
        change_product_qty.change_product_qty()
        return change_product_qty

    def create_orderpoint(self):
        """Create a Reordering Rule"""
        reorder = self.reordering_rule_model.with_user(self.user).create(
            {
                "name": "Order-point",
                "product_id": self.product.id,
                "product_min_qty": 100.0,
                "product_max_qty": 500.0,
                "qty_multiple": 1.0,
                "procure_uom_id": self.dozen.id,
            }
        )
        return reorder

    def create_orderpoint_procurement(self):
        """Make Procurement from Reordering Rule"""
        context = {
            "active_model": "stock.warehouse.orderpoint",
            "active_ids": self.reorder.ids,
            "active_id": self.reorder.id,
        }
        wizard = (
            self.make_procurement_orderpoint_model.with_user(self.user)
            .with_context(context)
            .create({})
        )
        for line in wizard.item_ids:
            line.onchange_uom_id()
        wizard.make_procurement()
        return wizard

    def test_security(self):
        """Test Manual Procurement created from Order-Point"""

        # Create Manual Procurement from order-point procured quantity
        self.create_orderpoint_procurement()

        # As per route configuration, it will create Purchase order
        # Assert that Procurement is created with the desired quantity
        purchase = self.purchase_model.search([("origin", "ilike", self.reorder.name)])
        self.assertEqual(len(purchase), 1)
        purchase_line = self.purchase_line_model.search(
            [("orderpoint_id", "=", self.reorder.id), ("order_id", "=", purchase.id)]
        )
        self.assertEqual(len(purchase_line), 1)
        self.assertEqual(self.reorder.product_id.id, purchase_line.product_id.id)
        # it could be using an existing PO, thus there could be more origins.
        self.assertTrue(self.reorder.name in purchase.origin)
        self.assertNotEqual(
            self.reorder.procure_recommended_qty, purchase_line.product_qty
        )
        if self.reorder.procure_uom_id == self.reorder.product_id.uom_po_id:
            # Our PO unit of measure is also dozens (procure uom)
            self.assertEqual(purchase_line.product_qty, 40)
        else:
            # PO unit of measure is units, not the same as procure uom.
            self.assertEqual(purchase_line.product_qty, 480)
