odoo.define('payment_blzpinpay.blzpinpay', function(require) {
    "use strict";

    var ajax = require('web.ajax');
    var core = require('web.core');
    var _t = core._t;
    var qweb = core.qweb;
    ajax.loadXML('/payment_blzpinpay/static/src/xml/blzpinpay_templates.xml', qweb);

    // The following currencies are integer only, see
    // https://stripe.com/docs/currencies#zero-decimal
    var int_currencies = [
        'BIF', 'XAF', 'XPF', 'CLP', 'KMF', 'DJF', 'GNF', 'JPY', 'MGA', 'PYG',
        'RWF', 'KRW', 'VUV', 'VND', 'XOF'
    ];

    if ($.blockUI) {
        // our message needs to appear above the modal dialog
        $.blockUI.defaults.baseZ = 2147483647; //same z-index as StripeCheckout
        $.blockUI.defaults.css.border = '0';
        $.blockUI.defaults.css["background-color"] = '';
        $.blockUI.defaults.overlayCSS["opacity"] = '0.9';
    }

    require('web.dom_ready');
    if (!$('.o_payment_form').length) {
        return $.Deferred().reject("DOM doesn't contain '.o_payment_form'");
    }

    var observer = new MutationObserver(function(mutations, observer) {
        for(var i=0; i<mutations.length; ++i) {
            for(var j=0; j<mutations[i].addedNodes.length; ++j) {
                if(mutations[i].addedNodes[j].tagName.toLowerCase() === "form" && mutations[i].addedNodes[j].getAttribute('provider') == 'blzpinpay') {
                    display_blzpinpay_form($(mutations[i].addedNodes[j]));
                }
            }
        }
    });


    function display_blzpinpay_form(provider_form) {
        // Open Checkout with further options
        var payment_form = $('.o_payment_form');
        if(!payment_form.find('i').length)
            payment_form.append('<i class="fa fa-spinner fa-spin"/>');
            payment_form.attr('disabled','disabled');

        var payment_tx_url = payment_form.find('input[name="prepare_tx_url"]').val();
        var access_token = $("input[name='access_token']").val() || $("input[name='token']").val() || '';

        var get_input_value = function(name) {
            return provider_form.find('input[name="' + name + '"]').val();
        }

        var acquirer_id = parseInt(provider_form.find('#acquirer_stripe').val());
        var amount = parseFloat(get_input_value("amount") || '0.0');
        var currency = get_input_value("currency");
        var email = get_input_value("email");
        var invoice_num = get_input_value("invoice_num");
        var merchant = get_input_value("merchant");

        ajax.jsonRpc(payment_tx_url, 'call', {
            acquirer_id: acquirer_id,
            access_token: access_token,
        }).then(function(data) {
            var $pay_stripe = $('#pay_stripe').detach();
            try { provider_form[0].innerHTML = data; } catch (e) {}
            // Restore 'Pay Now' button HTML since data might have changed it.
            $(provider_form[0]).find('#pay_stripe').replaceWith($pay_stripe);
        }).done(function () {
            var $_dialog = $('<div style="z-index: 2147483661;display: block;background: rgba(0, 0, 0, 0.5);border: 0px none transparent;overflow: hidden auto;visibility: visible;margin: 0px;padding: 0px;-webkit-tap-highlight-color: transparent;position: fixed;left: 0px;top: 0px;width: 100%;height: 100%;display: flex;justify-content: center;align-items: center;"></div>');
            var $_dialog_container = $(['<div class="inner-content" style="width: 400px;height: 500px;background: #fff;">',
            '</div>'].join(''));
            var $_form = $([
                "<form action='/payment/blzpinpay/create_charge' class='pin' method='post'>",
                    "<fieldset>",
                    "<legend>Payment</legend>",
                    "<label for='cc-number'>Credit Card Number</label>",
                    "<input id='cc-number' type='text'>",
                    "<label for='cc-name'>Name on Card</label>",
                    "<input id='cc-name' type='text'>",
                    "<label for='cc-expiry-month'>Expiry Month</label>",
                    "<input id='cc-expiry-month'>",
                    "<label for='cc-expiry-year'>Expiry Year</label>",
                    "<input id='cc-expiry-year'>",
                    "<label for='cc-cvc'>CVC</label>",
                    "<input id='cc-cvc'>",
                    "</fieldset>",
                    "<input type='submit' value='Pay now'></input>",
                    "</form>"].join(''))
            var submitButton = $_form.find(":submit");
            var pinApi = new Pin.Api($("input[name='blzpinpay_key']").val(), 'test');

            $_form.submit(function(e) {
                e.preventDefault();
            
                // Disable the submit button to prevent multiple clicks
                submitButton.attr({disabled: true});
            
                // Fetch details required for the createToken call to Pin Payments
                var card = {
                    number:           $('#cc-number').val(),
                    name:             $('#cc-name').val(),
                    expiry_month:     $('#cc-expiry-month').val(),
                    expiry_year:      $('#cc-expiry-year').val(),
                    cvc:              $('#cc-cvc').val(),
                    address_line1:    $("input[name='address_line1']").val(),
                    address_line2:    $("input[name='address_line2']").val(),
                    address_city:     $("input[name='address_city']").val(),
                    address_state:    $("input[name='address_state']").val(),
                    address_postcode: $("input[name='address_postcode']").val(),
                    address_country:  $("input[name='address_country']").val()
                };
            
                // Request a token for the card from Pin Payments
                pinApi.createCardToken(card).then(function(card) {
                    $('<input>')
                    .attr({type: 'hidden', name: 'card_token'})
                    .val(card.token)
                    .appendTo($_form);
                    $('<input>')
                    .attr({type: 'hidden', name: 'ip_address'})
                    .val('192.0.2.42')
                    .appendTo($_form);
                    $('<input>')
                    .attr({type: 'hidden', name: 'description'})
                    .val($('input[name="invoice_num"]').val())
                    .appendTo($_form);
                    // $('input[name="csrf_token"]').appendTo($_form);
                    $('input[name="email"]').appendTo($_form);
                    $('input[name="amount"]').appendTo($_form);
                    $('input[name="currency"]').appendTo($_form);

                    console.log(card);
                    console.log($_form.serialize());

                    $_form.get(0).submit();
                }).done();
            });
            $_dialog_container.append($_form)
            $_dialog.append($_dialog_container)
            $_dialog.insertAfter($(provider_form[0]))
        });
    }

	// display_blzpinpay_form($('form[provider="blzpinpay"]'));
	
    $.getScript("https://cdn.pinpayments.com/pin.v2.js", function(data, textStatus, jqxhr) {
       observer.observe(document.body, {childList: true});
       display_blzpinpay_form($('form[provider="blzpinpay"]'));
    });
});
