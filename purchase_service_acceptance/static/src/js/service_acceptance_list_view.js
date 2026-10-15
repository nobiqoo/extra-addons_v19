/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ServiceAcceptanceListController } from "./service_acceptance_list_controller";

export const serviceAcceptanceListView = {
    ...listView,
    Controller: ServiceAcceptanceListController,
};

registry.category("views").add("purchase_service_acceptance_list_view", serviceAcceptanceListView);
