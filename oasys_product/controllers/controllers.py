# -*- coding: utf-8 -*-
from odoo import http

# class OasysProduct(http.Controller):
#     @http.route('/oasys_product/oasys_product/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/oasys_product/oasys_product/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('oasys_product.listing', {
#             'root': '/oasys_product/oasys_product',
#             'objects': http.request.env['oasys_product.oasys_product'].search([]),
#         })

#     @http.route('/oasys_product/oasys_product/objects/<model("oasys_product.oasys_product"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('oasys_product.object', {
#             'object': obj
#         })