/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class ServiceAcceptanceStatsBanner extends Component {
    static template = "purchase_service_acceptance.ServiceAcceptanceStatsBanner";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ stats: null });
        onWillStart(async () => {
            this.state.stats = await this.orm.call(
                "purchase.service.acceptance",
                "get_dashboard_stats",
                [],
            );
        });
    }

    openFiltered(key) {
        const stat = this.state.stats && this.state.stats[key];
        if (!stat) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Service Acceptance"),
            res_model: "purchase.service.acceptance",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: stat.domain,
            target: "current",
        });
    }
}
