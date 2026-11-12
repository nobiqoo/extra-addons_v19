/** @odoo-module **/
import { Component, onWillStart, onWillUnmount, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { _t } from '@web/core/l10n/translation';

export class BudgetDashboard extends Component {
    static template = 'sale_budget_arthome.Dashboard';
    static props = ['*'];

    setup() {
        this.orm = useService('orm');
        this.selectWeek = this.selectWeek.bind(this);
        this.selectMetric = this.selectMetric.bind(this);
        this.selectView = this.selectView.bind(this);
        this.clearSalesWeek = this.clearSalesWeek.bind(this);
        this.changeWeek = this.changeWeek.bind(this);
        this.selectDate = this.selectDate.bind(this);
        this.selectDateKey = this.selectDateKey.bind(this);
        const now = new Date();
        this.state = useState({
            month: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
            budgetId: String(this.props.action.params?.budget_id || ''),
            teamId: '', zone: '', categoryId: '', view: 'week', week: 0,
            metric: 'sales', salesWeek: 0, salesTab: 'sales', collectionFilter: 'all', chartView: 'week',
            data: null, loading: true, error: '',
        });
        this.requestNumber = 0;
        onWillStart(async () => {
            if (this.state.budgetId) {
                const [budget] = await this.orm.read('sale.budget.monthly', [Number(this.state.budgetId)], ['date_start']);
                this.state.month = budget.date_start.slice(0, 7);
            }
            await this.load();
            this.timer = setInterval(() => {
                if (!document.hidden) {
                    this.load();
                }
            }, 60000);
        });
        onWillUnmount(() => {
            clearInterval(this.timer);
            this.requestNumber++;
        });
    }

    async load() {
        const request = ++this.requestNumber;
        this.state.loading = true;
        try {
            const data = await this.orm.call('sale.budget.monthly', 'get_dashboard', [], {
                month: `${this.state.month}-01`, budget_id: this.state.budgetId || null,
                team_id: this.state.teamId || null, zone: this.state.zone || null,
                category_id: this.state.categoryId || null,
            });
            if (request === this.requestNumber) {
                this.state.data = data;
                this.state.error = '';
            }
        } catch (error) {
            if (request === this.requestNumber) {
                this.state.error = error.data?.message || _t('No se pudo cargar el tablero.');
            }
        } finally {
            if (request === this.requestNumber) {
                this.state.loading = false;
            }
        }
    }

    async change(event) {
        const field = event.target.name;
        if (field === 'month' && !/^\d{4}-\d{2}$/.test(event.target.value)) {
            return;
        }
        this.state[field] = event.target.value;
        if (field === 'month') {
            this.state.budgetId = '';
            this.state.teamId = '';
            this.state.zone = '';
            this.state.categoryId = '';
            this.state.week = 0;
            this.state.salesWeek = this.state.view === 'week' ? 0 : null;
        }
        await this.load();
    }

    money(value) {
        return new Intl.NumberFormat('es-CO', {
            style: 'currency', currency: this.state.data?.currency || 'COP', maximumFractionDigits: 0,
        }).format(value || 0);
    }

    percent(value) {
        return value === null ? _t('Sin meta') : `${value.toFixed(1)} %`;
    }

    get weeks() {
        const weeks = [];
        for (const day of this.state.data?.days || []) {
            if (!weeks.length || new Date(`${day.date}T12:00:00`).getDay() === 1) {
                weeks.push([]);
            }
            weeks.at(-1).push(day);
        }
        return weeks;
    }

    get visibleDays() {
        if (this.state.view === 'week') {
            return this.weeks[this.state.week] || [];
        }
        return this.state.data?.days || [];
    }

    get weeklyRows() {
        return this.weeks.map((days, i) => {
            const budget = days.reduce((a, d) => a + d.budget, 0);
            const real = days.reduce((a, d) => a + d.real, 0);
            return { name: `${_t('Semana')} ${i + 1}`, range: `${days[0].date} / ${days.at(-1).date}`,
                budget, real, compliance: budget ? 100 * real / budget : null };
        });
    }

    get weeklyMax() {
        return Math.max(1, ...this.weeklyRows.flatMap((row) => [row.budget, row.real]));
    }

    get visibleSales() {
        const sales = this.state.data?.sales || [];
        if (this.state.salesWeek === null) {
            return sales;
        }
        const days = this.weeks[this.state.salesWeek] || [];
        if (!days.length) {
            return [];
        }
        return sales.filter((sale) => sale.date >= days[0].date && sale.date <= days.at(-1).date);
    }

    get salesPeriodLabel() {
        if (this.state.salesWeek === null) {
            return _t('Todo el mes');
        }
        return `${_t('Semana')} ${this.state.salesWeek + 1}`;
    }

    get visibleCollectionInvoices() {
        const invoices = this.state.data?.collection_invoices || [];
        if (this.state.collectionFilter === 'paid') {
            return invoices.filter((invoice) => invoice.paid > 0);
        }
        if (this.state.collectionFilter === 'pending') {
            return invoices.filter((invoice) => invoice.pending > 0);
        }
        if (this.state.collectionFilter === 'overdue') {
            return invoices.filter((invoice) => invoice.overdue);
        }
        return invoices;
    }

    get visualDays() {
        if (this.state.salesWeek === null) {
            return this.state.data?.days || [];
        }
        return this.weeks[this.state.salesWeek] || [];
    }

    get visualPeriodLabel() {
        return this.state.salesWeek === null ? _t('Mes completo') : `${_t('Semana')} ${this.state.salesWeek + 1}`;
    }

    get visualSalesBudget() {
        return this.visualDays.reduce((total, day) => total + day.budget, 0);
    }

    get visualSalesReal() {
        return this.visualDays.reduce((total, day) => total + day.real, 0);
    }

    get visualSalesCompliance() {
        return this.visualSalesBudget ? 100 * this.visualSalesReal / this.visualSalesBudget : null;
    }

    get visualCollectionBudget() {
        const monthDays = this.state.data?.days?.length || 0;
        return monthDays ? (this.state.data.collection_budget || 0) * this.visualDays.length / monthDays : 0;
    }

    get visualCollectionReal() {
        return this.visualDays.reduce((total, day) => total + (day.collection || 0), 0);
    }

    get visualCollectionCompliance() {
        return this.visualCollectionBudget ? 100 * this.visualCollectionReal / this.visualCollectionBudget : null;
    }

    get trendDays() {
        const days = this.state.data?.days || [];
        const now = new Date();
        const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
        if (this.state.month === currentMonth) {
            const today = `${currentMonth}-${String(now.getDate()).padStart(2, '0')}`;
            return days.filter((day) => day.date <= today);
        }
        return days;
    }

    get trendChart() {
        const days = this.trendDays;
        const left = 62;
        const right = 748;
        const top = 18;
        const bottom = 218;
        const maximum = Math.max(1, ...days.flatMap((day) => [day.cumulative_budget, day.cumulative_real]));
        const x = (index) => days.length <= 1 ? left : left + index * (right - left) / (days.length - 1);
        const y = (value) => bottom - Math.max(0, value) * (bottom - top) / maximum;
        const points = days.map((day, index) => ({
            ...day,
            x: x(index),
            salesY: y(day.cumulative_real),
            targetY: y(day.cumulative_budget),
            label: new Date(`${day.date}T12:00:00`).toLocaleDateString('es-CO', { day: 'numeric', month: 'short' }),
        }));
        const path = (field) => points.map((point, index) => `${index ? 'L' : 'M'} ${point.x.toFixed(1)} ${point[field].toFixed(1)}`).join(' ');
        const salesPath = path('salesY');
        const targetPath = path('targetY');
        const areaPath = points.length ? `${salesPath} L ${points.at(-1).x.toFixed(1)} ${bottom} L ${points[0].x.toFixed(1)} ${bottom} Z` : '';
        const labelStep = Math.max(1, Math.ceil(days.length / 7));
        return {
            points,
            salesPath,
            targetPath,
            areaPath,
            ticks: [0, 1, 2, 3, 4].map((index) => ({
                value: maximum * index / 4,
                y: bottom - index * (bottom - top) / 4,
            })),
            labels: points.filter((_point, index) =>
                (index % labelStep === 0 && index <= points.length - 1 - labelStep) || index === points.length - 1),
            bottom,
        };
    }

    get visibleCollectionPayments() {
        const payments = this.state.data?.collection_payments || [];
        if (this.state.salesWeek === null) {
            return payments;
        }
        const days = this.weeks[this.state.salesWeek] || [];
        if (!days.length) {
            return [];
        }
        return payments.filter((payment) => payment.date >= days[0].date && payment.date <= days.at(-1).date);
    }

    dayLabel(date) {
        return new Date(`${date}T12:00:00`).toLocaleDateString('es-CO', { weekday: 'short', day: 'numeric' });
    }

    bar(value) {
        return `width: ${Math.max(0, Math.min(value || 0, 120)) / 1.2}%`;
    }

    donut(value, color) {
        const progress = Math.max(0, Math.min(value || 0, 100));
        return `--ab-progress: ${progress}%; --ab-progress-color: ${color}`;
    }

    weeklyBar(value) {
        return `height: ${Math.max(0, Math.min(100, 100 * (value || 0) / this.weeklyMax))}%`;
    }

    selectWeek(index) {
        this.state.week = index;
        this.state.view = 'week';
        this.state.metric = 'sales';
        this.state.salesWeek = index;
        this.state.salesTab = 'sales';
        requestAnimationFrame(() => {
            document.querySelector('.ab_days')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    selectMetric(metric) {
        this.state.metric = metric;
        if (metric === 'sales') {
            this.state.salesTab = 'sales';
        } else {
            this.state.collectionFilter = 'all';
        }
        requestAnimationFrame(() => {
            document.querySelector('.ab_detail_section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    selectView(view) {
        this.state.view = view;
        this.state.salesWeek = view === 'week' ? this.state.week : null;
    }

    clearSalesWeek() {
        this.state.salesWeek = null;
        this.state.view = 'month';
    }

    changeWeek(event) {
        if (event.target.value === 'all') {
            this.clearSalesWeek();
        } else {
            this.selectWeek(Number(event.target.value));
        }
    }

    selectDate(date) {
        const index = this.weeks.findIndex((days) => days.some((day) => day.date === date));
        if (index >= 0) {
            this.selectWeek(index);
        }
    }

    selectDateKey(event, date) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            this.selectDate(date);
        }
    }

    compactMoney(value) {
        return new Intl.NumberFormat('es-CO', {
            notation: 'compact', maximumFractionDigits: 1,
        }).format(value || 0);
    }

    collectionProgress() {
        const budget = this.state.data?.collection_budget || 0;
        const collected = this.state.data?.collected || 0;
        return `width: ${budget ? Math.max(0, Math.min(100, 100 * collected / budget)) : 0}%`;
    }
}

registry.category('actions').add('sale_budget_arthome.dashboard', BudgetDashboard);
