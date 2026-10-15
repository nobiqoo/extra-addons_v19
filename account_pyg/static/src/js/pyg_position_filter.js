/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useRef, useState } from "@odoo/owl";

class PygListFilterController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    /**
     * Triggered from the renderer when the user clicks "Aplicar"
     * @param {Object} domain  list of domain tuples
     */
    applyPygFilter(domain) {
        this.actionService.doAction({
            name: "PyG por posición",
            type: "ir.actions.act_window",
            res_model: "pyg.position.report",
            views: [[false, "list"], [false, "form"]],
            view_mode: "list",
            target: "main",
            domain: domain,
        });
    }
}

class PygListFilterRenderer extends ListRenderer {
    setup() {
        super.setup();
        this.filterState = useState({
            date_from: "",
            date_to: "",
            account_root_ids: [],
            account_ids: [],
            analytic_account_ids: [],
        });
        onMounted(() => this._syncDomainToFilter());
    }

    /**
     * Sync domain from existing list view domain into filter bar
     */
    _syncDomainToFilter() {
        const domain = this.props.list ? (this.props.list.domain || []) : [];
        domain.forEach((leaf) => {
            if (!Array.isArray(leaf)) return;
            const [field, op, val] = leaf;
            if (field === "document_date") {
                if (op === ">=") this.filterState.date_from = val;
                else this.filterState.date_to = val;
            }
            if (field === "account_root_id") this.filterState.account_root_ids = val;
            if (field === "account_id") this.filterState.account_ids = val;
            if (field === "analytic_account_id") this.filterState.analytic_account_ids = val;
        });
    }

    _onApplyFilter(ev) {
        ev.preventDefault();
        const domain = [];
        if (this.filterState.date_from) {
            domain.push(["document_date", ">=", this.filterState.date_from]);
        }
        if (this.filterState.date_to) {
            domain.push(["document_date", "<=", this.filterState.date_to]);
        }
        if (this.filterState.account_root_ids && this.filterState.account_root_ids.length) {
            domain.push(["account_root_id", "in", this.filterState.account_root_ids]);
        }
        if (this.filterState.account_ids && this.filterState.account_ids.length) {
            domain.push(["account_id", "in", this.filterState.account_ids]);
        }
        if (this.filterState.analytic_account_ids && this.filterState.analytic_account_ids.length) {
            domain.push(["analytic_account_id", "in", this.filterState.analytic_account_ids]);
        }
        this.env.config.applyPygFilter(domain);
    }
}

PygListFilterRenderer.template = "account_pyg.PygListFilterRenderer";

export const pygPositionListFilter = {
    ...listView,
    Controller: PygListFilterController,
    Renderer: PygListFilterRenderer,
};

registry.category("views").add("pyg_position_list_filter", pygPositionListFilter);
