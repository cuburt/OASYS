# -*- coding: utf-8 -*-
from odoo import http

# class OasysAnalytics(http.Controller):
#     @http.route('/oasys_analytics/oasys_analytics/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/oasys_analytics/oasys_analytics/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('oasys_analytics.listing', {
#             'root': '/oasys_analytics/oasys_analytics',
#             'objects': http.request.env['oasys_analytics.oasys_analytics'].search([]),
#         })

#     @http.route('/oasys_analytics/oasys_analytics/objects/<model("oasys_analytics.oasys_analytics"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('oasys_analytics.object', {
#             'object': obj
#         })