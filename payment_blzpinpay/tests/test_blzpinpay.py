# -*- coding: utf-8 -*-
import odoo
from odoo import fields
from odoo.addons.payment.tests.common import PaymentAcquirerCommon
from odoo.tools import mute_logger


class BlzPinpayCommon(PaymentAcquirerCommon):

    def setUp(self):
        super(BlzPinpayCommon, self).setUp()
        self.blzpinpay = self.env.ref('payment_acquirer_blzpinpay')


@odoo.tests.tagged('post_install', '-at_install', '-standard', 'external')
class BlzPinpayTest(BlzPinpayCommon):

    def test_10_blzpinpay_s2s(self):
        self.assertEqual(self.blzpinpay.environment, 'test', 'test without test environment')

        # Add BlzPinpay credentials
        self.blzpinpay.write({
            'blzpinpay_au_secret_key': 'd7rOHP9Eiti6vsKT7AzwEQ',
            'blzpinpay_au_publishable_key': 'pk_uKTj8kNaN2DtCn4yEsMCrQ',
        })

        # Create payment meethod for BlzPinpay
        payment_token = self.env['payment.token'].create({
            'acquirer_id': self.blzpinpay.id,
            'partner_id': self.buyer_id,
            'cc_number': '4242424242424242',
            'cc_expiry': '02 / 26',
            'cc_brand': 'visa',
            'cvc': '111',
            'cc_holder_name': 'Johndoe',
        })

        # Create transaction
        tx = self.env['payment.transaction'].create({
            'reference': 'test_ref_%s' % fields.date.today(),
            'currency_id': self.currency_euro.id,
            'acquirer_id': self.blzpinpay.id,
            'partner_id': self.buyer_id,
            'payment_token_id': payment_token.id,
            'type': 'server2server',
            'amount': 115.0
        })
        tx.blzpinpay_s2s_do_transaction()

        # Check state
        self.assertEqual(tx.state, 'done', 'BlzPinpay: Transcation has been discarded.')

    def test_20_blzpinpay_form_render(self):
        self.assertEqual(self.blzpinpay.environment, 'test', 'test without test environment')

        # ----------------------------------------
        # Test: button direct rendering
        # ----------------------------------------

        # render the button
        res = self.blzpinpay.render('SO404', 320.0, self.currency_euro.id, values=self.buyer_values).decode('utf-8')
        # Generated and received
        self.assertIn(self.buyer_values.get('partner_email'), res, 'BlzPinpay: email input not found in rendered template')

    def test_30_blzpinpay_form_management(self):
        self.assertEqual(self.blzpinpay.environment, 'test', 'test without test environment')

        # typical data posted by BlzPinpay after client has successfully paid
        blzpinpay_post_data = {
            u'amount': 4700,
            u'amount_refunded': 0,
            u'application_fee': None,
            u'balance_transaction': u'txn_172xfnGMfVJxozLwssrsQZyT',
            u'captured': True,
            u'created': 1446529775,
            u'currency': u'eur',
            u'customer': None,
            u'description': None,
            u'destination': None,
            u'dispute': None,
            u'failure_code': None,
            u'failure_message': None,
            u'fraud_details': {},
            u'id': u'ch_172xfnGMfVJxozLwEjSfpfxD',
            u'invoice': None,
            u'livemode': False,
            u'metadata': {u'reference': u'SO100-1'},
            u'object': u'charge',
            u'paid': True,
            u'receipt_email': None,
            u'receipt_number': None,
            u'refunded': False,
            u'refunds': {u'data': [],
                         u'has_more': False,
                         u'object': u'list',
                         u'total_count': 0,
                         u'url': u'/v1/charges/ch_172xfnGMfVJxozLwEjSfpfxD/refunds'},
            u'shipping': None,
            u'source': {u'address_city': None,
                        u'address_country': None,
                        u'address_line1': None,
                        u'address_line1_check': None,
                        u'address_line2': None,
                        u'address_state': None,
                        u'address_zip': None,
                        u'address_zip_check': None,
                        u'brand': u'Visa',
                        u'country': u'US',
                        u'customer': None,
                        u'cvc_check': u'pass',
                        u'dynamic_last4': None,
                        u'exp_month': 2,
                        u'exp_year': 2022,
                        u'fingerprint': u'9tJA9bUEuvEb3Ell',
                        u'funding': u'credit',
                        u'id': u'card_172xfjGMfVJxozLw1QO6gYNM',
                        u'last4': u'4242',
                        u'metadata': {},
                        u'name': u'norbert.buyer@example.com',
                        u'object': u'card',
                        u'tokenization_method': None},
            u'statement_descriptor': None,
            u'status': u'succeeded'}

        tx = self.env['payment.transaction'].create({
            'amount': 4700,
            'acquirer_id': self.blzpinpay.id,
            'currency_id': self.currency_euro.id,
            'reference': 'SO100-1',
            'partner_name': 'Norbert Buyer',
            'partner_country_id': self.country_france.id})

        # validate it
        tx.form_feedback(blzpinpay_post_data, 'blzpinpay')
        self.assertEqual(tx.state, 'done', 'BlzPinpay: validation did not put tx into done state')
        self.assertEqual(tx.acquirer_reference, blzpinpay_post_data.get('id'), 'BlzPinpay: validation did not update tx id')
        blzpinpay_post_data['metadata']['reference'] = u'SO100-2'
        # reset tx
        tx = self.env['payment.transaction'].create({
            'amount': 4700,
            'acquirer_id': self.blzpinpay.id,
            'currency_id': self.currency_euro.id,
            'reference': 'SO100-2',
            'partner_name': 'Norbert Buyer',
            'partner_country_id': self.country_france.id})
        # simulate an error
        blzpinpay_post_data['status'] = 'error'
        blzpinpay_post_data.update({u'error': {u'message': u"Your card's expiration year is invalid.", u'code': u'invalid_expiry_year', u'type': u'card_error', u'param': u'exp_year'}})
        with mute_logger('odoo.addons.payment_blzpinpay.models.payment'):
            tx.form_feedback(blzpinpay_post_data, 'blzpinpay')
        # check state
        self.assertEqual(tx.state, 'cancel', 'Stipe: erroneous validation did not put tx into error state')
