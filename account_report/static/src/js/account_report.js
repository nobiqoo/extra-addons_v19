odoo.define('account_report.account_report',  function (require) {
'use strict';

var core = require('web.core');
var accountReportsWidget = require('account_reports.account_report').accountReportsWidget;
var M2MFilters = require('account_reports.account_report').M2MFilters;

var _t = core._t;

accountReportsWidget.include({

    custom_events: _.extend({}, accountReportsWidget.prototype.custom_events, {
        'seller_filter_changed': function(ev) {
            var self = this;
            self.report_options.seller_ids = ev.data.seller_ids;
            self.report_options.team_ids = ev.data.team_ids;
            return self.reload().then(function () {
                self.$searchview_buttons.find('.account_seller_filter').click();
            });
        },
    }),
    render_searchview_buttons: function() {
        const res = this._super.apply(this, arguments);
        // seller filter
        if (this.report_options.seller) {
            if (!this.seller_m2m_filter) {
                var fields = {};
                if ('seller_ids' in this.report_options) {
                    fields['seller_ids'] = {
                        label: _t('Sellers'),
                        modelName: 'res.users',
                        value: this.report_options.seller_ids.map(Number),
                    };
                }
                if ('team_ids' in this.report_options) {
                    fields['team_ids'] = {
                        label: _t('Sales teams'),
                        modelName: 'crm.team',
                        value: this.report_options.team_ids.map(Number),
                    };
                }
                if (!_.isEmpty(fields)) {
                    this.seller_m2m_filter = new M2MFilters(this, fields, 'seller_filter_changed');
                    this.seller_m2m_filter.appendTo(this.$searchview_buttons.find('.js_account_seller_m2m'));
                }
            } else {
                this.$searchview_buttons.find('.js_account_seller_m2m').append(this.seller_m2m_filter.$el);
            }
        }
        return res;
    },
});
});
