# -*- coding: utf-8 -*-
import logging
import pprint
import werkzeug
import requests
import json

from odoo import http
from odoo.http import request
from odoo.addons.payment.controllers.portal import PaymentProcessing

_logger = logging.getLogger(__name__)


class BlzPinpayController(http.Controller):

    @http.route(['/payment/blzpinpay/s2s/create_json'], type='json', auth='public')
    def blzpinpay_s2s_create_json(self, **kwargs):
        _logger.info('rtv: at blzpinpay_s2s_create_json()')  # debug
        acquirer_id = int(kwargs.get('acquirer_id'))
        acquirer = request.env['payment.acquirer'].browse(acquirer_id)
        if not kwargs.get('partner_id'):
            kwargs = dict(kwargs, partner_id=request.env.user.partner_id.id)
        return acquirer.s2s_process(kwargs).id

    @http.route(['/payment/blzpinpay/s2s/create'], type='http', auth='public')
    def blzpinpay_s2s_create(self, **post):
        _logger.info('rtv: at blzpinpay_s2s_create()')  # debug
        acquirer_id = int(post.get('acquirer_id'))
        acquirer = request.env['payment.acquirer'].browse(acquirer_id)
        error = None
        try:
            acquirer.s2s_process(post)
        except Exception as e:
            error = str(e)

        return_url = post.get('return_url', '/')
        if error:
            separator = '?' if werkzeug.urls.url_parse(return_url).query == '' else '&'
            return_url += '{}{}'.format(separator, werkzeug.urls.url_encode({'error': error}))

        return werkzeug.utils.redirect(return_url)

    @http.route(['/payment/blzpinpay/s2s/create_json_3ds'], type='json', auth='public', csrf=False)
    def blzpinpay_s2s_create_json_3ds(self, verify_validity=False, **kwargs):
        _logger.info('rtv: at blzpinpay_s2s_create_json_3ds()')  # debug          
        if not kwargs.get('partner_id'):
            kwargs = dict(kwargs, partner_id=request.env.user.partner_id.id)
        token = request.env['payment.acquirer'].browse(int(kwargs.get('acquirer_id'))).s2s_process(kwargs)

        if not token:
            res = {
                'result': False,
            }
            return res

        res = {
            'result': True,
            'id': token.id,
            'short_name': token.short_name,
            '3d_secure': False,
            'verified': False,
        }

        if verify_validity != False:
            token.validate()
            res['verified'] = token.verified

        return res

    @http.route([
        '/payment/blzpinpay/create_charge',
    ], type='http', auth='none', csrf=False)
    def blzpinpay_create_charge(self, **post):
        _logger.info('rtv: at blzpinpay_create_charge()')  # debug          
        _logger.info(post)  # debug

        """Expects the result from the user input from pin.v2.js popup"""
        TX = request.env['payment.transaction']
        tx = None
        if post.get('tx_ref'):
            tx = TX.sudo().search([('reference', '=', post['tx_ref'])])
        if not tx:
            tx_id = (post.get('tx_id') or request.session.get('sale_transaction_id') or
                     request.session.get('website_payment_tx_id'))
            tx = TX.sudo().browse(int(tx_id))
        if not tx:
            raise werkzeug.exceptions.NotFound()
        _logger.info('rtv: tx [%s]', pprint.pformat(tx))  # debug  

        response = None
        _logger.info('rtv: tx.type [%s], tx.partner_id [%s]', tx.type, tx.partner_id)  # debug 
        if tx.type == 'form_save' and tx.partner_id:
             # Creating the card token object using the pin card_token response
            blzpinpay_token = dict()
            blzpinpay_token["email"] = post["email"]
            blzpinpay_token["id"] = post['card_token']
            blzpinpay_token["card_token"] = post['card_token']
            blzpinpay_token["currency"] = post['currency']
            blzpinpay_token['object'] = 'token'
            blzpinpay_token['type'] = 'card'

            payment_token_id = request.env['payment.token'].sudo().create({
                'acquirer_id': tx.acquirer_id.id,
                'partner_id': tx.partner_id.id,
                'blzpinpay_token': blzpinpay_token
            })
            _logger.info('rtv: payment_token_id [%s]', pprint.pformat(payment_token_id))  # debug  
            tx.payment_token_id = payment_token_id
            response = tx._create_blzpinpay_charge(acquirer_ref=payment_token_id.acquirer_ref, email=blzpinpay_token['email'])
        else:
            blzpinpay_token = post['token']
            _logger.info('rtv: tokenid [%s], email [%s]', blzpinpay_token['id'], blzpinpay_token['email'])  # debug  
            response = tx._create_blzpinpay_charge(tokenid=blzpinpay_token['id'], email=blzpinpay_token['email'] )
        
        _logger.info('BlzPinpay: entering form_feedback with post data %s', pprint.pformat(response))
        if response:
            request.env['payment.transaction'].sudo().with_context(lang=None).form_feedback(response, 'blzpinpay')
        # add the payment transaction into the session to let the page /payment/process to handle it
        PaymentProcessing.add_payment_transaction(tx)
        return "/payment/process"
