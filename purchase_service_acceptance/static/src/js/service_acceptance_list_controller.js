/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { ServiceAcceptanceStatsBanner } from "./service_acceptance_stats_banner";

export class ServiceAcceptanceListController extends ListController {
    static template = "purchase_service_acceptance.ServiceAcceptanceListView";
    static components = {
        ...ListController.components,
        ServiceAcceptanceStatsBanner,
    };
}
