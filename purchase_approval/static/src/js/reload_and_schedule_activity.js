/** @odoo-module **/

import { registry } from "@web/core/registry";

async function reloadAndScheduleActivity(env, action) {
    const controller = env.services.action.currentController;
    if (controller) {
        await env.services.action.restore(controller.jsId);
    }
    return action.params?.next;
}

registry
    .category("actions")
    .add("purchase_approval_reload_and_schedule_activity", reloadAndScheduleActivity);
