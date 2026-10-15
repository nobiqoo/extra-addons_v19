/** @odoo-module **/

import { AccountReport } from "@account_reports/components/account_report/account_report";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class SaleWorkFilters extends AccountReportFilters {
    setup() {
        super.setup();
    }
    
    get hasWorkFilter() {
        return 'work_ids' in this.controller.cachedFilterOptions;
    }
    
    get hasAccountFilter() {
        return 'account_ids' in this.controller.cachedFilterOptions;
    }
}

AccountReport.registerCustomComponent(SaleWorkFilters);

