/* @odoo-module */

import { ListController } from '@web/views/list/list_controller';
import { FormController } from '@web/views/form/form_controller';
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';
import { _t } from '@web/core/l10n/translation';

const origDesc = Object.getOwnPropertyDescriptor(ListController.prototype, 'archiveDialogProps');
if (origDesc && origDesc.get) {
    async function fetchUserRules(ctx, ids) {
        if (!ids || !ids.length) {
            return [];
        }
        if (ctx && ctx.orm && ctx.orm.call) {
            return await ctx.orm.call('res.users', 'get_user_info_for_archived_rules', [ids]);
        }
    }
    function buildRulesBody(userRules, header) {
        let out = (header || '') + '\n\n';
        if (userRules && userRules.length) {
            for (const u of userRules) {
                out += `${u.display_name}:\n`;
                for (const r of u.rules) {
                    const name = typeof r === 'string' ? r : r.name;
                    out += ` - ${name}\n`;
                }
                out += '\n';
            }
        } else {
            out += _t('No access management rules found for selected user(s).');
        }
        return out;
    }

    // list view
    const origGetStaticList = ListController.prototype.getStaticActionMenuItems;
    ListController.prototype.getStaticActionMenuItems = function () {
        const items = origGetStaticList.call(this);
        const resModel = this.model && this.model.root && this.model.root.resModel;
        if (resModel !== 'res.users') {
            return items;
        }
        if (items.archive) {
            const origCallback = items.archive.callback;
            items.archive.callback = async () => {
                const resIds = await this.model.root.getResIds(true);
                const ids = resIds && resIds.length ? resIds : [];
                const userRules = ids.length ? await fetchUserRules(this, ids) : [];
                const usersWithRules = (userRules || []).filter((u) => u.rules && u.rules.length);
                if (!usersWithRules.length) {
                    return origCallback.call(this);
                }
                const body = buildRulesBody(usersWithRules, _t('The selected user(s) are part of the following access management rules:')) + '\n' + _t('Are you sure you want to archive the selected user(s)?');

                const dialogProps = {
                    title: _t('Archive records'),
                    body: body,
                    confirmLabel: _t('Archive and Remove from rules'),
                    cancelLabel: _t('Cancel'),
                    confirm: async () => {
                        await this.model.root.archive(true);
                    },
                    cancel: () => {},
                };
                this.dialogService.add(ConfirmationDialog, dialogProps);
            };
        }
        return items;
    };

    // form view
    const origGetStaticForm = FormController.prototype.getStaticActionMenuItems;
    FormController.prototype.getStaticActionMenuItems = function () {
        const items = origGetStaticForm.call(this);
        const resModel = this.model && this.model.root && this.model.root.resModel;
        if (resModel !== 'res.users') {
            return items;
        }
        if (items.archive) {
            const origCallback = items.archive.callback;
            items.archive.callback = async () => {
                const id = this.model.root.resId;
                const ids = id ? [id] : [];
                const userRules = ids.length ? await fetchUserRules(this, ids) : [];
                const usersWithRules = (userRules || []).filter((u) => u.rules && u.rules.length);
                if (!usersWithRules.length) {
                    return origCallback.call(this);
                }
                const body = buildRulesBody(usersWithRules, _t('The selected user is part of the following access management rules:')) + '\n' + _t('Are you sure you want to archive this user?');

                const dialogProps = {
                    title: _t('Archive record'),
                    body: body,
                    confirmLabel: _t('Archive and Remove from rules'),
                    cancelLabel: _t('Cancel'),
                    confirm: async () => {
                        await this.model.root.archive(true);
                    },
                    cancel: () => {},
                };
                this.dialogService.add(ConfirmationDialog, dialogProps);
            };
        }
        return items;
    };

}
