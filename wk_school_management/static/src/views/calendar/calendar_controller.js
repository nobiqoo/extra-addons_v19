/** @odoo-module **/

import { CalendarController } from "@web/views/calendar/calendar_controller";
import { CalendarModel } from '@web/views/calendar/calendar_model';
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";

function getDateRange(scale) {
    let startDate, endDate;
    const today = new Date();

    switch (scale) {
        case 'day':
            startDate = today;
            endDate = today;
            break;
        case 'week':
            const currentDay = today.getDay();
            const startOfWeek = new Date(today);
            startOfWeek.setDate(today.getDate() - currentDay);
            const endOfWeek = new Date(startOfWeek);
            endOfWeek.setDate(startOfWeek.getDate() + 6);
            startDate = startOfWeek;
            endDate = endOfWeek;
            break;
        case 'month':
            startDate = new Date(today.getFullYear(), today.getMonth(), 1);
            endDate = new Date(today.getFullYear(), today.getMonth() + 1, 0);
            break;
        case 'year':
            startDate = new Date(today.getFullYear(), 0, 1);
            endDate = new Date(today.getFullYear(), 11, 31);
            break;
    }

    return {
        start_date: startDate.toISOString().split('T')[0],
        end_date: endDate.toISOString().split('T')[0]
    };
}

patch(CalendarModel.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        if (
            this.meta.resModel === "wk.class.timetable" ||
            this.meta.resModel === "student.enrollment" ||
            this.meta.resModel === "wk.populate.class"
        ) {
            this.meta.canEdit = false;
        }

    },

    async load(params = {}) {
        const scale = this.meta.scale;
        this.meta.productData = await this.fetchData(scale);
        return super.load(...arguments);
    },

    async fetchData(scale) {
        const dateRange = getDateRange(scale);
        return this.orm.call('wk.class.timetable', 'fetch_data_for_dashboard', [dateRange], {});
    },
});

patch(CalendarController.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.actionService = useService("action");
    },

    async setScale(scale) {
        this.model.meta.scale = scale;
        await this.model.load({scale});
        browser.sessionStorage.setItem("calendar-scale", this.model.scale);
    },

    openViewonClick(ev) {
        let domain = [];
        const scale = this.model.meta.scale;
        const dateRange = getDateRange(scale);
        if (ev.target.classList.contains('completed_classes_dashboard')) {
            let completedClassDomain = [
                ['class_date', '>=', dateRange['start_date']],
                ['class_date', '<=', dateRange['end_date']],
                ['state', '=', 'complete']
            ];
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'wk.class.timetable',
                name: 'Completed Classes',
                views: [[false, 'list'], [false, 'form']],
                domain: completedClassDomain.concat(domain),
                context: {
                    create: true,
                },
            });
        }
        else if (ev.target.classList.contains('upcoming_classes_dashboard')) {
            let upcomingClassDomain = [
                ['class_date', '>=', dateRange.start_date],
                ['class_date', '<=', dateRange.end_date],
                ['state', '=', 'draft']
            ];
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'wk.class.timetable',
                name: 'Upcoming Classes',
                views: [[false, 'list'], [false, 'form']],
                domain: upcomingClassDomain.concat(domain),
                context: {
                    create: true,
                },
            });
        }
        else if (ev.target.classList.contains('toDo_assignment')) {
            let toDoAssignmentDomain = [
                ['state', '=', 'new']
            ];
            
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'wk.student.assignment',
                name: 'To-do Assignments',
                views: [[false, 'list'], [false, 'form']],
                domain: toDoAssignmentDomain.concat(domain),
                context: {
                    create: true,
                },
            });
        }
        else if (ev.target.classList.contains('completed_assignment')) {
            let completedAssignmentDomain = [
                ['state', 'in', ['submit', 'evaluate']]
            ];
            
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'wk.student.assignment',
                name: 'Completed Assignments',
                views: [[false, 'list'], [false, 'form']],
                domain: completedAssignmentDomain.concat(domain),
                context: {
                    create: true,
                },
            });
        }
    },

    bookingModel() {
        return this.props.resModel === 'wk.class.timetable';
    },
});
