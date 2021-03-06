# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012-Today OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

from datetime import datetime
import base64
import cStringIO

import xlwt

from openerp import tools
from openerp.osv import osv
from openerp.osv import fields
from openerp.tools.translate import _

from requests import exceptions
import ebaysdk
from ebaysdk.utils import getNodeText
from ebaysdk.exception import ConnectionError, ConnectionResponseError

class ebay_sale_order_confirm(osv.TransientModel):
    _name = 'ebay.sale.order.confirm'
    _description = 'ebay sale order confirm'
    
    _columns = {
        'count': fields.integer('Item Record Count', readonly=True),
    }
    
    def _get_count(self, cr, uid, context=None):
        if context is None:
            context = {}
        record_ids = context and context.get('active_ids', False)
        return len(record_ids)
    
    _defaults = {
        'count': _get_count,
    }
    
    def action_confirm(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        record_ids = context and context.get('active_ids', False)
        self.pool.get('ebay.sale.order').action_confirm(cr, uid, record_ids, context=None)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Orders',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'ebay.sale.order',
            'context': "{'search_default_state': 'confirmed'}",
        }
    
ebay_sale_order_confirm()

class ebay_sale_order_assign(osv.TransientModel):
    _name = 'ebay.sale.order.assign'
    _description = 'ebay sale order assign'
    
    _columns = {
        'count': fields.integer('Item Record Count', readonly=True),
    }
    
    def _get_count(self, cr, uid, context=None):
        if context is None:
            context = {}
        record_ids = context and context.get('active_ids', False)
        return len(record_ids)
    
    _defaults = {
        'count': _get_count,
    }
    
    def action_assign(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        record_ids = context and context.get('active_ids', False)
        self.pool.get('ebay.sale.order').action_assign(cr, uid, record_ids, context=None)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Orders',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'ebay.sale.order',
            'context': "{'search_default_state': 'assigned'}",
        }
    
ebay_sale_order_assign()

class ebay_sale_order_print(osv.TransientModel):
    _name = 'ebay.sale.order.print'
    _description = 'ebay sale order print'
    
    _columns = {
        'count': fields.integer('Item Record Count', readonly=True),
        'automerge': fields.boolean('Automerge Orders'),
        'automerge_count': fields.integer('Automerge Order Count', readonly=True),
        'carrier': fields.selection([
            ('carrier-4px', '4px'),
            ('carrier-sfc', 'sfc'),
        ], 'Logistics Carrier'),
        'name': fields.char('Filename', readonly=True),
        'data': fields.binary('File', readonly=True),
        'state': fields.selection([
            ('option', 'option'),
            ('download', 'download'),
        ], 'State'),
    }
    
    def _get_count(self, cr, uid, context=None):
        if context is None:
            context = {}
        record_ids = context and context.get('active_ids', False)
        return len(record_ids)
    
    _defaults = {
        'count': _get_count,
        'automerge': True,
        'carrier': 'carrier-4px',
        'state': 'option'
    }
    
    def prepare_4px_slip(self, cr, uid, slip, context=None):
        order_lines = slip['order_lines']
        partner = slip['partner']
        shipping_service_map = {
            'cnam': 'F3',
            'cnram': 'F4',
            'hkam': 'B4',
            'hkram': 'B3',
            'sgam': 'B2',
            'sgram': 'B1',
        }
        weight = 0.0
        for line in order_lines:
            weight += line.product_id.weight * line.product_uom_qty
        weight = weight if weight > 0.01 else 0.01
        slip_line = {
            u'客户单号': slip['ref'],
            u'服务商单号': '',
            u'运输方式': shipping_service_map.get(slip['shipping_service'], ''),
            u'目的国家': partner.country_id.code,
            u'收件人姓名': partner.name,
            u'州 \ 省': partner.state_id.name if partner.state_id else '',
            u'城市': partner.city,
            u'联系地址': '%s %s' % (partner.street, partner.street2 if partner.street2 else ''),
            u'收件人电话': partner.phone if partner.phone else '',
            u'收件人邮箱': partner.email,
            u'收件人邮编': partner.zip,
            u'买家ID': slip['buyer_user_id'],
            u'重量': weight,
            u'是否退件': 'Y',
            u'包裹种类': '1',
        }
        for i, line in enumerate(order_lines):
            price_unit = line.price_unit * line.product_uom_qty
            price_unit = price_unit if price_unit > 8 else 8
            declared_value = price_unit / line.product_uom_qty
            order_line = {
                u'海关报关品名%s' % str(i+1): '%s (%d' % (line.product_id.name, line.product_uom_qty),
                u'配货信息%s' % str(i+1): line.product_id.name,
                u'申报价值%s' % str(i+1): declared_value,
                u'申报品数量%s' % str(i+1): line.product_uom_qty,
                u'配货备注%s' % str(i+1): line.name,
            }
            slip_line.update(order_line)
            if i+1 == 5:
                break
            
        return slip_line
    
    def carrier_4px_format(self, cr, uid, slips, context=None):
        headers = [
            u'客户单号',
            u'服务商单号',
            u'运输方式',
            u'目的国家',
            u'寄件人公司名',
            u'寄件人姓名',
            u'寄件人省',
            u'寄件人城市',
            u'寄件人地址',
            u'寄件人电话',
            u'寄件人邮编',
            u'寄件人传真',
            u'收件人公司名',
            u'收件人姓名',
            u'州 \ 省',
            u'城市',
            u'联系地址',
            u'收件人护照号码',
            u'收件人电话',
            u'收件人邮箱',
            u'收件人邮编',
            u'收件人传真',
            u'买家ID',
            u'交易ID',
            u'保险类型',
            u'保险价值',
            u'订单备注',
            u'重量',
            u'是否退件',
            u'包裹种类',
            u'EORI号码',
            u'海关报关品名1', u'海关申报品名（中）1', u'配货信息1', u'申报价值1', u'申报品URL1', u'海关货物编号1', u'申报品数量1', u'配货备注1',
            u'海关报关品名2', u'海关申报品名（中）2', u'配货信息2', u'申报价值2', u'申报品URL2', u'海关货物编号2', u'申报品数量2', u'配货备注2',
            u'海关报关品名3', u'海关申报品名（中）3', u'配货信息3', u'申报价值3', u'申报品URL3', u'海关货物编号3', u'申报品数量3', u'配货备注3',
            u'海关报关品名4', u'海关申报品名（中）4', u'配货信息4', u'申报价值4', u'申报品URL4', u'海关货物编号4', u'申报品数量4', u'配货备注4',
            u'海关报关品名5', u'海关申报品名（中）5', u'配货信息5', u'申报价值5', u'申报品URL5', u'海关货物编号5', u'申报品数量5', u'配货备注5',
        ]
        
        header_width = {
            u'收件人姓名': (1 + 32) * 256,
            u'州 \ 省': (1 + 32) * 256,
            u'城市': (1 + 32) * 256,
            u'联系地址': (1 + 64) * 256,
            u'订单备注': (1 + 64) * 256,
            u'海关报关品名1': (1 + 64) * 256, u'配货信息1': (1 + 64) * 256, u'配货备注1': (1 + 64) * 256,
            u'海关报关品名2': (1 + 64) * 256, u'配货信息2': (1 + 64) * 256, u'配货备注2': (1 + 64) * 256,
            u'海关报关品名3': (1 + 64) * 256, u'配货信息3': (1 + 64) * 256, u'配货备注3': (1 + 64) * 256,
            u'海关报关品名4': (1 + 64) * 256, u'配货信息4': (1 + 64) * 256, u'配货备注4': (1 + 64) * 256,
            u'海关报关品名5': (1 + 64) * 256, u'配货信息5': (1 + 64) * 256, u'配货备注5': (1 + 64) * 256,
        }
        
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('4px Delivery Slip')
        
        for i, name in enumerate(headers):
            worksheet.write(0, i, name)
            width = header_width.get(name, 0)
            width = width if width else (1 + 16) * 256
            worksheet.col(i).width = width
            
        for i, slip in enumerate(slips):
            row = i + 1
            for key, value in self.prepare_4px_slip(cr, uid, slip, context=context).items():
                col = headers.index(key)
                if row % 2:
                    worksheet.write(row, col, value, xlwt.easyxf('pattern: pattern solid, fore_color light_green;'))
                else:
                    worksheet.write(row, col, value)
        
        return workbook
    
    def _prepare_slip(self, cr, uid, ebay_sale_order, context=None):
        sale_order = ebay_sale_order.sale_order_ids[0]
        order_lines = sale_order.order_line
        partner = sale_order.partner_shipping_id
        return partner.address_id, dict(
            ref=ebay_sale_order.name.replace('/', ''),
            partner=partner,
            buyer_user_id=ebay_sale_order.buyer_user_id,
            shipping_service=ebay_sale_order.shipping_service,
            order_lines=order_lines,
            ebay_sale_order=ebay_sale_order,
        )
    
    def prepare_delivery_order(self, cr, uid, worksheet, slips, context=None):
        headers = [
            'Order Number',
            'Product',
            'Description',
            'Message',
        ]
        
        header_width = {
            'Order Number': (1 + 16) * 256,
            'Product': (1 + 56) * 256,
            'Description': (1 + 80) * 256,
            'Message': (1 + 56) * 256,
        }
        
        easyxf = [
            xlwt.easyxf('pattern: pattern solid, fore_color light_blue;'),
            xlwt.easyxf('pattern: pattern solid, fore_color light_green;'),
            xlwt.easyxf('pattern: pattern solid, fore_color gray40;'),
            xlwt.easyxf('pattern: pattern solid, fore_color light_yellow;'),
            xlwt.easyxf('pattern: pattern solid, fore_color light_orange;'),
            xlwt.easyxf('pattern: pattern solid, fore_color light_turquoise;'),
        ]
        
        for i, name in enumerate(headers):
            worksheet.write(0, i, name)
            width = header_width.get(name, 0)
            width = width if width else (1 + 16) * 256
            worksheet.col(i).width = width
            
        for i, slip in enumerate(slips):
            row = i + 1
            def _prepare_order(slip):
                product = ''
                description = ''
                order_lines = slip['order_lines']
                for line in order_lines:
                    if product:
                        product += '\n'
                        description += '\n'
                    product += '%s ( x%d )' % (line.product_id.name, line.product_uom_qty)
                    description += line.name
                message = slip['ebay_sale_order'].buyer_checkout_message
                message = message if message else ''
                order = {
                    'Order Number': slip['ref'],
                    'Product': product,
                    'Message': message,
                    'Description': description,
                }
                return order
                
            order = _prepare_order(slip)
            for key, value in order.items():
                col = headers.index(key)
                worksheet.write(row, col, value, easyxf[row % 6])
    
    def action_print(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        this = self.browse(cr, uid, ids)[0]
        
        record_ids = context and context.get('active_ids', False)
        delivery_slips = dict()
        sequence = 0
        automerge_count = 0
        for ebay_sale_order in self.pool.get('ebay.sale.order').browse(cr, uid, record_ids, context=context):
            if ebay_sale_order.sale_order_ids:
                address_id, slip = self._prepare_slip(cr, uid, ebay_sale_order, context=context)
                address_id = address_id if this.automerge else sequence
                sequence += 1
                if address_id in delivery_slips:
                    automerge_count += 1
                    delivery_slips[address_id]['order_lines'].extend(slip['order_lines'])
                else:
                    delivery_slips[address_id] = slip
        delivery_slips = delivery_slips.values()
        delivery_slips.sort(key=lambda x:x['ref'],reverse=True)
        
        workbook = self.carrier_4px_format(cr, uid, delivery_slips, context=context)
        
        worksheet = workbook.add_sheet('Delivery Order')
        self.prepare_delivery_order(cr, uid, worksheet, delivery_slips, context=context)
        
        fp = cStringIO.StringIO()
        workbook.save(fp)
        out = base64.encodestring(fp.getvalue())
        fp.close()
        
        this.name = "%s-%s.xls" % (this.carrier, datetime.now().strftime('%Y%m%d-%H%M%S'))
        
        self.write(cr, uid, ids, {'state': 'download',
                                  'automerge_count': automerge_count,
                                  'data': out,
                                  'name': this.name}, context=context)
        return {
            'name': "Print Delivery Slip",
            'type': 'ir.actions.act_window',
            'res_model': 'ebay.sale.order.print',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': this.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

ebay_sale_order_print()

class ebay_sale_order_send(osv.TransientModel):
    _name = 'ebay.sale.order.send'
    _description = 'ebay sale order send'
    
    _columns = {
        'count': fields.integer('Item Record Count', readonly=True),
        'exception': fields.text('Exception', readonly=True),
        'state': fields.selection([
            ('confirm', 'confirm'),
            ('exception', 'exception')]),
    }
    
    def _get_count(self, cr, uid, context=None):
        if context is None:
            context = {}
        record_ids = context and context.get('active_ids', False)
        return len(record_ids)
    
    _defaults = {
        'count': _get_count,
        'exception': '',
        'state': 'confirm',
    }
    
    def action_send(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        this = self.browse(cr, uid, ids)[0]
        record_ids = context and context.get('active_ids', False)
        
        sale_order_obj = self.pool.get('sale.order')
        stock_move_obj = self.pool.get('stock.move')
        ebay_ebay_obj = self.pool.get('ebay.ebay')
        send_ids = list()
        for order in self.pool.get('ebay.sale.order').browse(cr, uid, record_ids, context=context):
            user = order.ebay_user_id
            if order.state == 'assigned':
                for sale_order in order.sale_order_ids:
                    for picking in sale_order.picking_ids:
                        move_line_ids = [move_line.id for move_line in picking.move_lines if move_line.state not in ['done','cancel']]
                        stock_move_obj.action_done(cr, uid, move_line_ids, context=context)
                # complete sale
                call_data=dict(
                    FeedbackInfo=dict(
                        CommentText='Quick response and fast payment. Perfect! THANKS!!',
                        CommentType='Positive',
                        TargetUser=order.buyer_user_id,
                    ),
                    OrderID=order.order_id,
                    Shipped="true",
                )
                call_name = 'CompleteSale'
                api = ebay_ebay_obj.trading(cr, uid, user, call_name, context=context)
                try:
                    api.execute(call_name, call_data)
                except ConnectionError as e:
                    res = str(e)
                except ConnectionResponseError as e:
                    res = str(e)
                except exceptions.RequestException as e:
                    res = str(e)
                except exceptions.ConnectionError as e:
                    res = str(e)
                except exceptions.HTTPError as e:
                    res = str(e)
                except exceptions.URLRequired as e:
                    res = str(e)
                except exceptions.TooManyRedirects as e:
                    res = str(e)
                else:
                    res = order.write({'state': 'sent'})
                if res != True:
                    break
            
        if res != True:
            self.write(cr, uid, [this.id], {
                                  'exception': res,
                                  'state': 'exception'}, context=context)
            return  {
                'name': "Delivery",
                'type': 'ir.actions.act_window',
                'res_model': 'ebay.sale.order.send',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': this.id,
                'views': [(False, 'form')],
                'target': 'new',
            }
        else:
            return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Orders',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'ebay.sale.order',
        }
    
ebay_sale_order_send()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: