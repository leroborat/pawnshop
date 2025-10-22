# from odoo import http


# class Pawnshop(http.Controller):
#     @http.route('/pawnshop/pawnshop', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/pawnshop/pawnshop/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('pawnshop.listing', {
#             'root': '/pawnshop/pawnshop',
#             'objects': http.request.env['pawnshop.pawnshop'].search([]),
#         })

#     @http.route('/pawnshop/pawnshop/objects/<model("pawnshop.pawnshop"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('pawnshop.object', {
#             'object': obj
#         })

