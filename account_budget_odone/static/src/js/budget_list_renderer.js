import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";

// Scoped to crossovered.budget.lines' own list view (js_class="account_budget_list")
// so it never touches the stock ListRenderer used everywhere else in Odoo.
export class BudgetListRenderer extends ListRenderer {
    static template = "account_budget_odone.ListRenderer";
}

registry.category("views").add("account_budget_list", {
    ...listView,
    Renderer: BudgetListRenderer,
});
