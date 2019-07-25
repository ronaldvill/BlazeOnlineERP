# coding: utf-8

import logging
import requests
import pprint

from odoo import api, fields, models, _
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)


# The following currencies are integer only (copy from stripe)
INT_CURRENCIES = [
    u'BIF', u'XAF', u'XPF', u'CLP', u'KMF', u'DJF', u'GNF', u'JPY', u'MGA', u'PYG', u'RWF', u'KRW',
    u'VUV', u'VND', u'XOF'
]


class PaymentAcquirerBlzPinpay(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('blzpinpay', 'Blaze PinPay')])
    blzpinpay_au_secret_key = fields.Char(required_if_provider='blzpinpay', 
                                         groups='base.group_user')
    blzpinpay_au_publishable_key = fields.Char(required_if_provider='blzpinpay', 
                                              groups='base.group_user')
    blzpinpay_us_secret_key = fields.Char(required_if_provider='blzpinpay', 
                                         groups='base.group_user')
    blzpinpay_us_publishable_key = fields.Char(required_if_provider='blzpinpay', 
                                              groups='base.group_user')
    
    blzpinpay_image_url = fields.Char(
        "Checkout Image URL", groups='base.group_user',
        help="A relative or absolute URL pointing to a square image of your "
             "brand or product. As defined in your BlzPinpay profile.")

    @api.multi
    def blzpinpay_form_generate_values(self, tx_values):
        _logger.info('rtv: at blzpinpay_form_generate_values()')  # debug
        self.ensure_one()
        blzpinpay_tx_values = dict(tx_values)
        temp_blzpinpay_tx_values = {
            'company': self.company_id.name,
            'amount': tx_values['amount'],  # Mandatory
            'currency': tx_values['currency'].name,  # Mandatory anyway
            'currency_id': tx_values['currency'].id,  # same here
            'address_line1': tx_values.get('partner_address'),  # Any info of the partner is not mandatory
            'address_city': tx_values.get('partner_city'),
            'address_country': tx_values.get('partner_country') and tx_values.get('partner_country').name or '',
            'email': tx_values.get('partner_email'),
            'address_zip': tx_values.get('partner_zip'),
            'name': tx_values.get('partner_name'),
            'phone': tx_values.get('partner_phone'),
        }

        blzpinpay_tx_values.update(temp_blzpinpay_tx_values)
        return blzpinpay_tx_values

    @api.model
    def _get_pinpayment_api_url(self):
        payment_acquirer = self.env['payment.acquirer'].search([('provider', '=', 'blzpinpay')])
        _logger.info('rtv: current environment --> [%s]', payment_acquirer.environment)              
        if payment_acquirer.environment == 'test':
            url = 'test-api.pin.net.au'
        else:
            url = 'api.pin.net.au'
        return url
    
    @api.model
    def blzpinpay_s2s_form_process(self, data):
        _logger.info('rtv: at blzpinpay_s2s_form_process()')  # debug
        payment_token = self.env['payment.token'].sudo().create({
            'cc_number': data['cc_number'],
            'cc_holder_name': data['cc_holder_name'],
            'cc_expiry': data['cc_expiry'],
            'cc_brand': data['cc_brand'],
            'cvc': data['cvc'],
            'acquirer_id': int(data['acquirer_id']),
            'partner_id': int(data['partner_id'])
        })
        return payment_token

    @api.multi
    def blzpinpay_s2s_form_validate(self, data):
        _logger.info('rtv: at blzpinpay_s2s_form_validate()')  # debug
        self.ensure_one()

        # mandatory fields
        for field_name in ["cc_number", "cvc", "cc_holder_name", "cc_expiry", "cc_brand"]:
            if not data.get(field_name):
                return False
        return True

    def _get_feature_support(self):
        _logger.info('rtv: at _get_feature_support()')  # debug
        """Get advanced feature support by provider.

        Each provider should add its technical in the corresponding
        key for the following features:
            * fees: support payment fees computations
            * authorize: support authorizing payment (separates
                         authorization and capture)
            * tokenize: support saving payment data in a payment.tokenize
                        object
        """
        res = super(PaymentAcquirerBlzPinpay, self)._get_feature_support()
        res['tokenize'].append('blzpinpay')
        return res


class PaymentTransactionBlzPinpay(models.Model):
    _inherit = 'payment.transaction'

    def _create_blzpinpay_charge(self, acquirer_ref=None, tokenid=None, email=None):
        _logger.info('rtv: at _create_blzpinpay_charge()')  # debug
        api_url_charge = 'https://%s/1/charges' % (self.acquirer_id._get_pinpayment_api_url())
        charge_params = {
            'amount': int(self.amount if self.currency_id.name in INT_CURRENCIES else float_round(self.amount * 100, 2)),
            'currency': self.currency_id.name,
            'metadata[reference]': self.reference,
            'description': self.reference,
        }

        if acquirer_ref:
            # charge_params['customer'] = acquirer_ref
            charge_params['customer_token'] = acquirer_ref
        if email:
            charge_params['email'] = email.strip()
        if tokenid:
            charge_params['customer_token'] = str(tokenid)
            # post['customer_token'] = customer_object['response']['token'] 

        payment_acquirer = self.env['payment.acquirer'].browse(self.acquirer_id.id)
        if self.currency_id.name == 'AUD':
            api_key = payment_acquirer.blzpinpay_au_secret_key
        else:
            api_key = payment_acquirer.blzpinpay_us_secret_key
        _logger.info('rtv: currency [%s], api_key [%s]', self.currency_id.name,  api_key)  # debug

        _logger.info('_create_blzpinpay_charge: Sending values to URL %s, values:\n%s', api_url_charge, pprint.pformat(charge_params))
        r = requests.post(api_url_charge,
                          auth=(api_key, ''),
                          params=charge_params)
        res = r.json()
        _logger.info('_create_blzpinpay_charge: Values received:\n%s', pprint.pformat(res))
        
        if res.get('error'):
            _logger.error('payment.token._create_blzpinpay_charge: Customer error:\n%s', pprint.pformat(res['error']))
            raise Exception(res['error']['message'])
        
        return res.get('response')

    @api.multi
    def blzpinpay_s2s_do_transaction(self, **kwargs):
        _logger.info('rtv: at blzpinpay_s2s_do_transaction()')  # debug
        self.ensure_one()
        result = self._create_blzpinpay_charge(acquirer_ref=self.payment_token_id.acquirer_ref, email=self.partner_email)
        return self._blzpinpay_s2s_validate_tree(result)


    def _create_blzpinpay_refund(self):
        _logger.info('rtv: at _create_blzpinpay_refund()')  # debug
        api_url_refund = 'https://%s/refunds' % (self.acquirer_id._get_pinpayment_api_url())
        _logger.info('rtv: refund url %s', pprint.pformat(api_url_refund))

        refund_params = {
            'charge': self.acquirer_reference,
            'amount': int(float_round(self.amount * 100, 2)), # by default, blzpinpay refund the full amount (we don't really need to specify the value)
            'metadata[reference]': self.reference,
        }

        _logger.info('_create_blzpinpay_refund: Sending values to URL %s, values:\n%s', api_url_refund, pprint.pformat(refund_params))
        r = requests.post(api_url_refund,
                            auth=(self.acquirer_id.blzpinpay_au_secret_key, ''),
                            params=refund_params)
        res = r.json()
        _logger.info('_create_blzpinpay_refund: Values received:\n%s', pprint.pformat(res))
        return res

    @api.multi
    def blzpinpay_s2s_do_refund(self, **kwargs):
        _logger.info('rtv: at blzpinpay_s2s_do_refund()')  # debug
        self.ensure_one()
        result = self._create_blzpinpay_refund()
        return self._blzpinpay_s2s_validate_tree(result)

    @api.model
    def _blzpinpay_form_get_tx_from_data(self, data):
        _logger.info('rtv: at _blzpinpay_form_get_tx_from_data()')  # debug          
        _logger.info('rtv: data [%s]', pprint.pformat(data))

        """ Given a data dict coming from BlzPinpay, verify it and find the related
        transaction record. """
        reference = data.get('metadata', {}).get('reference')
        _logger.info('rtv: reference [%s]', pprint.pformat(reference))        
        if not reference:
            blzpinpay_error = data.get('error', {}).get('message', '')
            _logger.error('BlzPinpay: invalid reply received from BlzPinpay API, looks like '
                          'the transaction failed. (error: %s)', blzpinpay_error  or 'n/a')
            error_msg = _("We're sorry to report that the transaction has failed.")
            if blzpinpay_error:
                error_msg += " " + (_("BlzPinpay gave us the following info about the problem: '%s'") %
                                    blzpinpay_error)
            error_msg += " " + _("Perhaps the problem can be solved by double-checking your "
                                 "credit card details, or contacting your bank?")
            raise ValidationError(error_msg)

        tx = self.search([('reference', '=', reference)])
        if not tx:
            error_msg = (_('BlzPinpay: no order found for reference %s') % reference)
            _logger.error(error_msg)
            raise ValidationError(error_msg)
        elif len(tx) > 1:
            error_msg = (_('BlzPinpay: %s orders found for reference %s') % (len(tx), reference))
            _logger.error(error_msg)
            raise ValidationError(error_msg)
        return tx[0]

    @api.multi
    def _blzpinpay_s2s_validate_tree(self, tree):
        self.ensure_one()
        if self.state != 'draft':
            _logger.info('BlzPinpay: trying to validate an already validated tx (ref %s)', self.reference)
            return True

        status = tree.get('status_message') or tree.get('status')
        _logger.info('rtv: status [%s]', status)                
        if status == 'Success' or status == 'succeeded':
            self.write({
                'date': fields.datetime.now(),
                'acquirer_reference': tree.get('token'),
            })
            self._set_transaction_done()
            self.execute_callback()
            if self.payment_token_id:
                self.payment_token_id.verified = True
            return True
        else:
            error = tree['error']['message']
            _logger.warn(error)
            self.sudo().write({
                'state_message': error,
                'acquirer_reference': tree.get('token'),
                'date': fields.datetime.now(),
            })
            self._set_transaction_cancel()
            return False

    @api.multi
    def _blzpinpay_form_get_invalid_parameters(self, data):
        invalid_parameters = []
        reference = data['metadata']['reference']
        if reference != self.reference:
            invalid_parameters.append(('Reference', reference, self.reference))
        return invalid_parameters

    @api.multi
    def _blzpinpay_form_validate(self,  data):
        return self._blzpinpay_s2s_validate_tree(data)


class PaymentTokenBlzPinpay(models.Model):
    _inherit = 'payment.token'

    @api.model
    def blzpinpay_create(self, values):
        _logger.info('rtv: at blzpinpay_create()')  # debug             
        token = values.get('blzpinpay_token')
        description = None
        payment_acquirer = self.env['payment.acquirer'].browse(values.get('acquirer_id'))
        # when asking to create a token on BlzPinpay servers, create card_token
        if values.get('cc_number'): 
            url_token = 'https://%s/tokens' % payment_acquirer._get_pinpayment_api_url()
            _logger.info('rtv: token url %s', pprint.pformat(url_token))

            payment_params = {
                'card[number]': values['cc_number'].replace(' ', ''),
                'card[exp_month]': str(values['cc_expiry'][:2]),
                'card[exp_year]': str(values['cc_expiry'][-2:]),
                'card[cvc]': values['cvc'],
                'card[name]': values['cc_holder_name'],
            }
            r = requests.post(url_token,
                              auth=(payment_acquirer.blzpinpay_au_secret_key, ''),
                              params=payment_params)
            token = r.json()
            description = values['cc_holder_name']
        else:
            partner_id = self.env['res.partner'].browse(values['partner_id'])
            description = 'Partner: %s (id: %s)' % (partner_id.name, partner_id.id)

        if not token:
            raise Exception('blzpinpay_create: No token provided!')

        res = self._blzpinpay_create_customer(token, description, payment_acquirer.id)

        # pop credit card info to info sent to create
        for field_name in ["cc_number", "cvc", "cc_holder_name", "cc_expiry", "cc_brand", "blzpinpay_token"]:
            values.pop(field_name, None)
        return res


    def _blzpinpay_create_customer(self, token, description=None, acquirer_id=None):
        _logger.info('rtv: at _blzpinpay_create_customer()')  # debug          
        _logger.info('rtv: token [%s], desc[%s]', pprint.pformat(token), pprint.pformat(description))
        if token.get('error'):
            _logger.error('payment.token.blzpinpay_create_customer: Token error:\n%s', pprint.pformat(token['error']))
            raise Exception(token['error']['message'])

        if token['object'] != 'token':
            _logger.error('payment.token.blzpinpay_create_customer: Cannot create a customer for object type "%s"', token.get('object'))
            raise Exception('We are unable to process your credit card information.')

        if token['type'] != 'card':
            _logger.error('payment.token.blzpinpay_create_customer: Cannot create a customer for token type "%s"', token.get('type'))
            raise Exception('We are unable to process your credit card information.')

        payment_acquirer = self.env['payment.acquirer'].browse(acquirer_id or self.acquirer_id.id)
        url_customer = 'https://%s/1/customers/' % payment_acquirer._get_pinpayment_api_url()
        _logger.info('rtv: customer url %s', pprint.pformat(url_customer))

        customer_params = {
            'email': token['email'],
            'card_token': token['card_token']
        }

        if token['currency'] == 'AUD':
            api_key = payment_acquirer.blzpinpay_au_secret_key
        else:
            api_key = payment_acquirer.blzpinpay_us_secret_key
        _logger.info('rtv: currency [%s], api_key[%s]', token['currency'], api_key)  # debug  
    
        r = requests.post(url_customer,
                        auth=(api_key, ''),
                        params=customer_params)
        customer = r.json()
        _logger.info('rtv: customer_object: %s', pprint.pformat(customer))  # debug  

        if customer.get('error'):
            _logger.error('payment.token.blzpinpay_create_customer: Customer error:\n%s', pprint.pformat(customer['error']))
            raise Exception(customer['error']['message'])

        desc_str = customer['response']['card']['name'] or description
        values = {
            'acquirer_ref': customer['response']['card']['customer_token'],
            'name': '%s - %s' % (customer['response']['card']['display_number'].replace("-",""), desc_str)
        }
        _logger.info('rtv: return values [%s].', pprint.pformat(values))

        return values
