# -*- coding: utf-8 -*-
from odoo import http

# class OasysTest(http.Controller):
#     @http.route('/oasys_test/oasys_test/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/oasys_test/oasys_test/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('oasys_test.listing', {
#             'root': '/oasys_test/oasys_test',
#             'objects': http.request.env['oasys_test.oasys_test'].search([]),
#         })

#     @http.route('/oasys_test/oasys_test/objects/<model("oasys_test.oasys_test"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('oasys_test.object', {
#             'object': obj
#         })