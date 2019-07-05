# -*- coding: utf-8 -*-
import logging
import pprint
import werkzeug
import requests

from odoo import http
from odoo.http import request
from odoo.addons.payment.controllers.portal import PaymentProcessing

_logger = logging.getLogger(__name__)


class StripeController(http.Controller):

    @http.route(['/payment/blzpinpay/s2s/create_json'], type='json', auth='public')
    def blzpinpay_s2s_create_json(self, **kwargs):
        acquirer_id = int(kwargs.get('acquirer_id'))
        acquirer = request.env['payment.acquirer'].browse(acquirer_id)
        if not kwargs.get('partner_id'):
            kwargs = dict(kwargs, partner_id=request.env.user.partner_id.id)
        return acquirer.s2s_process(kwargs).id

    @http.route(['/payment/blzpinpay/s2s/create'], type='http', auth='public')
    def blzpinpay_s2s_create(self, **post):
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
    def pinpayments_return(self, **post):
        _logger.info(post)  # debug
        """ Gets the Post data pinpayments after making payment """
        if post['card_token']:
            _logger.info('Card token passed: %s', post['card_token'])  # debug
            acquirer = request.env['payment.acquirer'].search(
                [('provider', '=', 'blzpinpay')]
            )
# Gets the details of charge using card_token from pinpayments for
# further process
            _logger.info('Acquirer environment: %s',acquirer.environment)  # debug
            if acquirer.environment == 'test':
                url = 'https://test-api.pin.net.au'
            else:
                url = 'https://api.pin.net.au'

            if post['currency'] == 'AUD':
                api_key = acquirer.blzpinpay_au_secret_key
            else:
                api_key = acquirer.blzpinpay_us_secret_key
            
            _logger.info('URL: %s', url)  # debug

            post["amount"] = int(float(post["amount"]))
            post['amount'] *= 100

            data = requests.post(url + '/1/charges/', params=post,
                                auth=(api_key, " "))
            if 'false' or 'true' or 'null'in data.text:
                result = data.text.replace(
                    'false', 'False')
                result = result.replace('true', 'True')
                result = result.replace('null', 'False')
                result = eval(result)
            post = result
        _logger.info('Beginning Pin Payments form_feedback with post data %s',
                     pprint.pformat(post))  # debug
        return "/payment/process"

    # @http.route(['/payment/blzpinpay/create_charge'], type='json', auth='public')
    # def blzpinpay_create_charge(self, **post):
    #     """ Create a payment transaction

    #     Expects the result from the user input from checkout.js popup"""
    #     TX = request.env['payment.transaction']
    #     tx = None
    #     if post.get('tx_ref'):
    #         tx = TX.sudo().search([('reference', '=', post['tx_ref'])])
    #     if not tx:
    #         tx_id = (post.get('tx_id') or request.session.get('sale_transaction_id') or
    #                  request.session.get('website_payment_tx_id'))
    #         tx = TX.sudo().browse(int(tx_id))
    #     if not tx:
    #         raise werkzeug.exceptions.NotFound()

    #     stripe_token = post['token']
    #     response = None
    #     if tx.type == 'form_save' and tx.partner_id:
    #         payment_token_id = request.env['payment.token'].sudo().create({
    #             'acquirer_id': tx.acquirer_id.id,
    #             'partner_id': tx.partner_id.id,
    #             'stripe_token': stripe_token
    #         })
    #         tx.payment_token_id = payment_token_id
    #         response = tx._create_blzpinpay_charge(acquirer_ref=payment_token_id.acquirer_ref, email=stripe_token['email'])
    #     else:
    #         response = tx._create_blzpinpay_charge(tokenid=stripe_token['id'], email=stripe_token['email'])
    #     _logger.info('Stripe: entering form_feedback with post data %s', pprint.pformat(response))
    #     if response:
    #         request.env['payment.transaction'].sudo().with_context(lang=None).form_feedback(response, 'stripe')
    #     # add the payment transaction into the session to let the page /payment/process to handle it
    #     PaymentProcessing.add_payment_transaction(tx)
    #     return "/payment/process"
