/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { browser } from "@web/core/browser/browser";
import { session } from "@web/session";
import { FormController } from "@web/views/form/form_controller";

function currentUserAffected(record, changes) {
    if (record.resModel === "res.users" && "groups_id" in changes) {
        // Settings > Users > [a user] > Permissions: editing your own groups.
        return record.resId === session.uid;
    }
    if (record.resModel === "res.groups" && "users" in changes) {
        // Settings > Users & Companies > Groups > [a group] > Users: adding
        // or removing yourself from the group's member list.
        return record.data.users.currentIds.includes(session.uid);
    }
    return false;
}

patch(FormController.prototype, {
    async onRecordSaved(record, changes) {
        await super.onRecordSaved(record, changes);
        // Group membership changes only take effect for the current session
        // after a full reload — without this, a newly granted button/field
        // stays hidden until the user manually refreshes the page.
        if (currentUserAffected(record, changes)) {
            browser.location.reload();
        }
    },
});
