# -*- coding: utf-8 -*-

{
    'name': 'BlazePinPay Payment Acquirer',
    'category': 'Hidden',
    'summary': 'Payment Acquirer: BlazePinPay Implementation',
    'version': '1.2',
    'description': """BlazePinPay Payment Acquirer""",
    'depends': ['payment'],
    'data': [
        'views/payment_views.xml',
        'views/payment_blzpinpay_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'post_init_hook': 'create_missing_journal_for_acquirers',
}
