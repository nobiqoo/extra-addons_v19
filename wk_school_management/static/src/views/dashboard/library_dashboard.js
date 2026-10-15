/** @odoo-module */
import { registry } from "@web/core/registry";
import { Component, useState, onMounted ,onWillStart} from "@odoo/owl";
import { cookie } from "@web/core/browser/cookie";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";

export class LibraryDashboard extends Component {
	setup() {
		this.action = useService("action");
		this.state = useState({
			library_record :{},
		})
		onWillStart(async () => {
			await loadBundle("web.chartjs_lib");
			await this.get_library_data();
		});
		onMounted(async () => {
			this.start();
		});
	}

	async start(){
		// loadJS("/web/static/lib/Chart/Chart.js")
		this.render_bookrequest_pie_graph();
		this.load_library_books();
		this.render_bookcopies_pie_graph();
	}

	async render_bookrequest_pie_graph() {
		var selected_date = document.querySelector('#lib_date_selection option:checked');
		var self = this;
		if (!selected_date) {
			return;
		}
		rpc("/library/bookrequest_data", {'company_id':cookie.get('cids'),'sort_date':selected_date.value}).then(function(result){
			console.log('--resule', result)
			var data = result;
			const requestBookPieChartElement = document.getElementById('book_request_pie_chart');
			if (!requestBookPieChartElement) {
				return;
			}
			requestBookPieChartElement.replaceWith(Object.assign(document.createElement('canvas'), { id: 'book_request_pie_chart', height: 220 }));
			const canvas = document.getElementById('book_request_pie_chart');
			if (!canvas) {
				return;
			}
			var labels = ['Issued', 'Overdue Book List']
			const colorMap = {
				0: '#76b569ff',
				1: '#b05050ff',
			};
			var color = labels.map((_, index) => colorMap[index]);
			console.log('--color',color)
			new window.Chart(canvas, {
				type: 'doughnut',
				data: {
					labels: labels,
					datasets: [{
						backgroundColor: color,
						data: data,
					}],
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					cutout: "65%",
					plugins: {
						legend: {
							position: 'right',
							labels: {
								boxWidth: 15,
							},
							onHover: function() {
								document.body.style.cursor = 'pointer';
							},
							onLeave: function() {
								document.body.style.cursor = 'default';
							},
							onClick: function(_, legendItem) {
								const currentDate = new Date();
								const today = new Date();
								console.log('-today--',today)
								var label = legendItem.text.split(' ')[0];
								console.log('-selected_date--',selected_date.value)
								if (selected_date.value == 'today'){
									const startOfDay = new Date(today.setHours(0, 0, 0, 0));
									const endOfDay = new Date(today.setHours(23, 59, 59, 999));
									if (label === "Issued") {
										self.action.doAction({
											type: "ir.actions.act_window",
											res_model: 'wk.book.history',
											name: 'Issued',
											views: [[false, 'list'],[false, 'form']],
											domain: [["state", "=", 'issued'],['create_date', '>=', startOfDay], ['create_date', '<=', endOfDay]],
										});
									}
									if (label === "Overdue") {
										self.action.doAction({
											type: "ir.actions.act_window",
											res_model: 'wk.book.history',
											name: 'Issued',
											views: [[false, 'list'],[false, 'form']],
											domain: [["state", "=", 'issued'],['expected_return_date', '<', startOfDay]],
										});
									}
								}

								else if (selected_date.value == 'week'){
									const dayOfWeek = currentDate.getDay();
									const diffToMonday = (dayOfWeek + 6) % 7;
									var startDate = new Date(currentDate);
									startDate.setDate(currentDate.getDate() - diffToMonday);
									var endDate = new Date(startDate);
									endDate.setDate(startDate.getDate() + 6);
									if (label === "Issued") {
										self.action.doAction({
											type: "ir.actions.act_window",
											res_model: 'wk.book.history',
											name: 'Issued',
											views: [[false, 'list'],[false, 'form']],
											domain: [["state", "=", 'issued'],['create_date', '>=', startDate], ['create_date', '<=', endDate]],
										});
									}
									if (label === "Overdue") {
										self.action.doAction({
											type: "ir.actions.act_window",
											res_model: 'wk.book.history',
											name: 'Issued',
											views: [[false, 'list'],[false, 'form']],
											domain: [["state", "=", 'issued'],['expected_return_date', '<', startDate]],
										});
									}
								}
								else if (selected_date.value == 'month'){
									var startDate = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    								var endDate = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0);
									if (label === "Issued") {
										self.action.doAction({
											type: "ir.actions.act_window",
											res_model: 'wk.book.history',
											name: 'Issued',
											views: [[false, 'list'],[false, 'form']],
											domain: [["state", "=", 'issued'],['create_date', '>=', startDate], ['create_date', '<=', endDate]],
										});
									}
									if (label === "Overdue") {
										self.action.doAction({
											type: "ir.actions.act_window",
											res_model: 'wk.book.history',
											name: 'Issued',
											views: [[false, 'list'],[false, 'form']],
											domain: [["state", "=", 'issued'],['expected_return_date', '<', startDate]],
										});
									}

								}
							}
						},
					},
				},
				plugins: [{
					id: 'book_request_pie_chart',
					beforeDraw(chart) {
						const { ctx, chartArea } = chart;

						if (!chartArea) return;

						// Calculate total
						const total = chart.data.datasets[0].data
							.reduce((sum, value) => sum + value, 0);

						// Get actual chart (circle) center
						const centerX = (chartArea.left + chartArea.right) / 2;
						const centerY = (chartArea.top + chartArea.bottom) / 2;

						ctx.save();
						ctx.textAlign = 'center';
						ctx.textBaseline = 'middle';

						// Label text
						ctx.font = 'bold 14px sans-serif';
						ctx.fillStyle = '#000';
						ctx.fillText('Total Requests', centerX, centerY - 10);

						// Value text
						ctx.font = 'bold 20px sans-serif';
						ctx.fillStyle = '#000';
						ctx.fillText(total.toString(), centerX, centerY + 12);

						ctx.restore();
					}
				}]
			});
		});
	}

	async render_bookcopies_pie_graph() {
		var selected_date = document.querySelector('#lib_date_selection option:checked');
		var self = this;
		if (!selected_date) {
			return;
		}
		rpc("/library/book_data", {'company_id':cookie.get('cids')}).then(function(result){
			console.log('--resule', result)
			var data = result;
			const requestBookPieChartElement = document.getElementById('book_copies_pie_chart');
			if (!requestBookPieChartElement) {
				return;
			}
			requestBookPieChartElement.replaceWith(Object.assign(document.createElement('canvas'), { id: 'book_copies_pie_chart', height: 220 }));
			const canvas = document.getElementById('book_copies_pie_chart');
			if (!canvas) {
				return;
			}
			var labels = ['Available','Not Available']
			const colorMap = {
				0: '#76b569ff',
				1: '#b05050ff',
			};
			var color = labels.map((_, index) => colorMap[index]);
			console.log('--color',color)
			new window.Chart(canvas, {
				type: 'doughnut',
				data: {
					labels: labels,
					datasets: [{
						backgroundColor: color,
						data: data,
					}],
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					cutout: "65%",
					plugins: {
						legend: {
							position: 'right',
							labels: {
								boxWidth: 15,
							},
							onHover: function() {
								document.body.style.cursor = 'pointer';
							},
							onLeave: function() {
								document.body.style.cursor = 'default';
							},
							onClick: function(_, legendItem) {
								var label = legendItem.text.split(' ')[0];
								if (label === "Available") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'wk.books',
										name: 'Books',
										views: [[false, 'kanban'],[false, 'form']],
										domain: [["state", "=", 'available']],
									});
								} 
								else if (label === "Not") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'wk.books',
										name: 'Books',
										views: [[false, 'kanban'],[false, 'form']],
										domain: [["state", "=", 'not_available']],
									});
								}
							}
						},
					},
				},
				plugins: [{
					id: 'book_copies_pie_chart',
					beforeDraw(chart) {
						const { ctx, chartArea } = chart;

						if (!chartArea) return;

						// Calculate total
						const total = chart.data.datasets[0].data
							.reduce((sum, value) => sum + value, 0);

						// Get actual chart (circle) center
						const centerX = (chartArea.left + chartArea.right) / 2;
						const centerY = (chartArea.top + chartArea.bottom) / 2;

						ctx.save();
						ctx.textAlign = 'center';
						ctx.textBaseline = 'middle';

						// Label text
						ctx.font = 'bold 14px sans-serif';
						ctx.fillStyle = '#000';
						ctx.fillText('Total Books', centerX, centerY - 10);

						// Value text
						ctx.font = 'bold 20px sans-serif';
						ctx.fillStyle = '#000';
						ctx.fillText(total.toString(), centerX, centerY + 12);

						ctx.restore();
					}
				}]
			});
		});
	}

	async load_library_datewise_data(){	
		this.render_bookrequest_pie_graph();
	}

	async issueButtonClick(){
		this.action.doAction("wk_school_management.library_barcode_action_main_view")
	}

	async load_library_books(){
		var selected_val = document.querySelector('#s_books option:checked');
		if (selected_val != null){
			await rpc("/library/books", {'company_id':cookie.get('cids'),'sort_by':selected_val.value}).then(function(result){
				const scheduled_classes = document.getElementById('library_books_table');
				if (scheduled_classes) {
					scheduled_classes.innerHTML = result
				}
			})
		}
	}

	async get_library_data(){
		console.log('cookie', cookie.get('cids'))
        const LibraryDashboardData = await rpc("/library/dashboard_data", {'company_id':cookie.get('cids')});
		console.log('LibraryDashboardData', LibraryDashboardData)
        this.state.library_record = LibraryDashboardData 
    }

	bookOnClick(ev){
		this.action.doAction('wk_school_management.wk_book_action');
	}

	requestOnClick(ev){
		this.action.doAction('wk_school_management.wk_booking_history_action');
	}

	categoryOnClick(ev){
		this.action.doAction('wk_school_management.wk_category_action');
	}

}

LibraryDashboard.template = 'LibraryDashboard'
registry.category("actions").add('action_dashboard_library', LibraryDashboard)
