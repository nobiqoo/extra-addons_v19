/** @odoo-module */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onMounted ,onWillStart} from "@odoo/owl";
import { KeepLast } from "@web/core/utils/concurrency";
import { loadJS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";
import {cookie} from "@web/core/browser/cookie";

export class SchoolDashboard extends Component {
	setup() {
		this.rpc = rpc;
		this.action = useService('action');
		this.keepLast = new KeepLast();
		this.state = useState({})
		var student = []
		var teacher = []
		var is_admin = true;
		var subjects = []

        onWillStart(async () => loadJS("/web/static/lib/Chart/Chart.js"));		

		onMounted(async () => {
			await this.fetch_data();
			this.start();
		});
	}
	async start(){
		this.load_datewise_data();
		this.load_class_assignment();
		this.load_student_assignment();
		this.load_scheduled_classes();
		this.render_enrollment_pie_graph();
		this.render_faculty_pie_graph();
		this.render_student_pie_graph();
		this.render_application_pie_graph();
		
		if (this.is_admin == false ){
			await new Promise(resolve => setTimeout(resolve, 1200));
			await this.load_teacher_profile();
			await this.render_faculty_student_pie_graph();
			const attendance_cards = document.querySelector('.attendance_cards');
			const application_card = document.querySelector('#application_card');
			const enrollment_card = document.querySelector('#enrollment_card');
			const notice_card = document.querySelector('#notice_card');
			if (attendance_cards) attendance_cards.classList.add('d-none');
			if (enrollment_card) enrollment_card.classList.add('d-none');
			if (application_card) application_card.classList.add('d-none');
		}
	}

	async load_datewise_data(){
		setTimeout(() => {
			document.querySelectorAll('.dashboard_onclick').forEach(function(element){
				element.addEventListener('click',function(f){
					window.open(f.currentTarget.getAttribute('href'), '_blank');
				}); 
			});
		}, 2000);
		var selected_date = document.querySelector('#date_selection option:checked');
		if (selected_date != null){
			await rpc("/school_management/datewise_data", {'company_id':cookie.get('cids'),'sort_date':selected_date.value}).then(function(result){
				const notice = document.getElementById('notice_board_table');
				const lesson = document.getElementById('lesson_plan_table');
				if (lesson != null)
					lesson.innerHTML = result['lesson_data'];
				if (notice != null)
					notice.innerHTML = result['notice_data'];
			})
		}
		this.load_class_assignment();
		this.load_student_assignment();
		this.load_scheduled_classes();
		this.render_enrollment_pie_graph();
		this.render_application_pie_graph();
	}

	async load_class_assignment(){
		var selected = document.querySelector('#c_assignment option:checked');
		var selected_date = document.querySelector('#date_selection option:checked');
		if (selected != null){
			await rpc("/school_management/class_assignment", {'company_id':cookie.get('cids'),'sort_by':selected.value,'sort_date':selected_date.value}).then(function(result){
				const assignment = document.getElementById('class_assignment_table');
				if (assignment) {
					assignment.innerHTML = result;
				} 
			})
		}
	}

	async load_student_assignment(){
		var selected_val = document.querySelector('#s_assignment option:checked');
		var selected_date = document.querySelector('#date_selection option:checked');
		if (selected_val != null){
			await rpc("/school_management/student_assignment", {'company_id':cookie.get('cids'),'sort_by':selected_val.value,'sort_date':selected_date.value}).then(function(result){
				const s_assignment = document.getElementById('student_assignment_table');
				if (s_assignment) {
					s_assignment.innerHTML = result;
				}
			})
		}
	}

	async load_scheduled_classes(){
		var selected_val = document.querySelector('#s_classes option:checked');
		var selected_date = document.querySelector('#date_selection option:checked');
		if (selected_val != null){
			await rpc("/school_management/scheduled_classes", {'company_id':cookie.get('cids'),'sort_by':selected_val.value,'sort_date':selected_date.value}).then(function(result){
				const scheduled_classes = document.getElementById('scheduled_classes_table');
				if (scheduled_classes) {
					scheduled_classes.innerHTML = result
				}
			})
		}
	}
		
	async fetch_data() {
		const schoolDashboardData = await this.keepLast.add(
			this.rpc("/school_management/dashboard_data", {'company_id':cookie.get('cids')})
		);
		Object.assign(this.state, schoolDashboardData);
		this.teacher = this.state.teachers;
		this.student = this.state.students;
		this.is_admin = this.state.is_admin;
	}

	async load_teacher_profile(){
		var self = this;
		const profileData = await this.keepLast.add(
			this.rpc("/school_management/profile_data", {'company_id':cookie.get('cids')}).then(function(result){
				const subjects_badge = document.getElementById('subjects_badge');
				if (subjects_badge) {
					subjects_badge.innerHTML = result['subjects'];
				}
				Object.assign(self.state, result);
			})
		);
	}

	applicationOnClick(ev){
		this.action.doAction({
			type: "ir.actions.act_window",
			res_model: 'wk.application.form',
			name: 'Applications',
			views: [[false, 'list'], [false, 'form']],
		});
	}

	enrollmentOnClick(ev){
		this.action.doAction({
			type: "ir.actions.act_window",
			res_model: 'student.enrollment',
			name: 'Enrollments',
			views: [[false, 'list'], [false, 'form']],
		});
	}

	studentOnClick(ev){
		this.action.doAction({
			type: "ir.actions.act_window",
			res_model: 'student.student',
			name: 'Students',
			views: [[false, 'list'], [false, 'form']],
		});
	}

	facultyOnClick(ev){
		this.action.doAction({
			type: "ir.actions.act_window",
			res_model: 'hr.employee',
			name: 'Faculty',
			views: [[false, 'list'], [false, 'form']],
			domain: [['is_teacher', '=', 'true']],
		});
	}

	profileOnClick(ev){
		var employee_id = this.state.employee_id;
		this.action.doAction({
			type: "ir.actions.act_window",
			res_model: 'hr.employee',
			name: 'Total Faculty',
			views: [[false, 'form']],
            res_id: employee_id,
		});
	}

	classesOnClick(ev){
		this.action.doAction({
			type: "ir.actions.act_window",
			res_model: 'wk.class.timetable',
			name: 'Total Scheduled Classes',
			views: [[false, 'list'], [false, 'form']],
		});
	}

	classAssignmentsOnClick(ev){
		this.action.doAction({
			type: "ir.actions.act_window",
			res_model: 'wk.class.assignment',
			name: 'Total Class Assignments',
			views: [[false, 'list'], [false, 'form']],
		});
	}

	studentAssignmentsOnClick(ev){
		this.action.doAction({
			type: "ir.actions.act_window",
			res_model: 'wk.student.assignment',
			name: 'Total Student Assignments',
			views: [[false, 'list'], [false, 'form']],
		});
	}

	serviceHoursOnClick(ev){
		this.action.doAction({
			type: "ir.actions.act_window",
			res_model: 'wk.service.hours',
			name: 'New Service Hours',
			views: [[false, 'list'], [false, 'form']],
			domain: [['state', '=', 'new']],
		});
	}

	render_enrollment_pie_graph() {
		var selected_date = document.querySelector('#date_selection option:checked');
		var self = this;
		if (!selected_date || typeof window.Chart === "undefined") {
			return;
		}
		this.rpc("/school_dashboard/enrollment_data", {'company_id':cookie.get('cids'),'sort_date':selected_date.value}).then((result) => {
			var data = result;
			const enrollmentChartContainer = document.querySelector('#enrollment_card .p-3');
			enrollmentChartContainer.innerHTML = '';
			const isEmpty = !data || data.length === 0 || data.every(val => val === 0);

			if (isEmpty) {
				const img = document.createElement('img');
				img.src = '/wk_school_management/static/description/enrollment.png';
				img.alt = 'No Records Found';
				img.style.display = 'block';
				img.style.margin = '10px auto';
				img.style.maxHeight = '120px';
				img.style.objectFit = 'contain';

				const msg = document.createElement('div');
				msg.textContent = "No enrollments found at the moment!";
				msg.style.textAlign = 'center';
				msg.style.marginTop = '10px';
				msg.style.fontSize = '14px';
				msg.style.fontWeight = '600';

				enrollmentChartContainer.appendChild(img);
				enrollmentChartContainer.appendChild(msg);
				return;
			}

			const canvas = Object.assign(document.createElement('canvas'), {
				id: 'enrolment_pie_chart',
				height: 150
			});
			enrollmentChartContainer.appendChild(canvas);

			enrollmentChartContainer.appendChild(canvas);
			new window.Chart('enrolment_pie_chart', {
				type: 'doughnut',
				data: {
					labels: ['Draft','In Progress','Completed','Cancelled'],
					datasets: [{
						backgroundColor: ["#2563EA","#FCB974","#0890B1","#FBA4A4"],
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
								generateLabels: function(chart) {
									var originalLabels = chart.data.labels;
									
									return originalLabels.map(function(label, index) {
										return {
											text: label + ' (' + data[index] + ')',  
											fillStyle: chart.data.datasets[0].backgroundColor[index],
											draw: function(chartArea) {
												var ctx = chartArea.chart.ctx;
												var x = chartArea.x + chartArea.width / 2;
												var y = chartArea.y + chartArea.height / 2;
												var radius = 5;
												ctx.beginPath();
												ctx.arc(x, y, radius, 0, 2 * Math.PI);
												ctx.fillStyle = this.fillStyle;
												ctx.fill();
											}
										};
									});
								}
							},
							onHover: function() {
								document.body.style.cursor = 'pointer';
							},
							onLeave: function() {
								document.body.style.cursor = 'default';
							},
							onClick: (unusedEvent, legendItem) => {
								var label = legendItem.text.split(' ')[0];
								if (label === "Draft") {
									this.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'student.enrollment',
										name: 'New Enrollments',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_draft: 1},
									});
								} 
								else if (label === "In") {
									this.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'student.enrollment',
										name: 'In Progress Enrollments',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_progress: 1},
									});
								}
								else if (label === "Completed") {
									this.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'student.enrollment',
										name: 'Completed Enrollments',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_complete: 1},
									});
								}
								else if (label === "Cancelled") {
									this.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'student.enrollment',
										name: 'Cancelled Enrollments',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_cancel: 1},
									});
								}
							}
						},
					},
				},
			});
		});
	}

	render_application_pie_graph() {
		var selected_date = document.querySelector('#date_selection option:checked');
		var self = this;
		if (!selected_date) {
			return;
		}
		this.rpc("/school_dashboard/application_data", {'company_id':cookie.get('cids'),'sort_date':selected_date.value}).then(function(result){
			var data = result;
			const applicationPieChartContainer = document.querySelector('#application_card .p-3');
			applicationPieChartContainer.innerHTML = '';
			const isEmpty = !data || data.length === 0 || data.every(val => val === 0);

			if (isEmpty) {
				const img = document.createElement('img');
				img.src = '/wk_school_management/static/description/application.png';
				img.alt = 'No Records Found';
				img.style.display = 'block';
				img.style.margin = '10px auto';
				img.style.maxHeight = '120px';
				img.style.objectFit = 'contain';

				const msg = document.createElement('div');
				msg.textContent = "No applications found at the moment!";
				msg.style.textAlign = 'center';
				msg.style.marginTop = '10px';
				msg.style.fontSize = '14px';
				msg.style.fontWeight = '600';

				applicationPieChartContainer.appendChild(img);
				applicationPieChartContainer.appendChild(msg);
				return;
			}

			const canvas = Object.assign(document.createElement('canvas'), {
				id: 'application_pie_chart',
				height: 150
			});
			applicationPieChartContainer.appendChild(canvas);

			new window.Chart(canvas, {
				type: 'doughnut',
				data: {
					labels: ['New','Confirmed','Enrolled','Cancelled'],
					datasets: [{
						backgroundColor: ["#2563EA","#FCB974","#0890B1","#FBA4A4"],
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
								generateLabels: function(chart) {
									var originalLabels = chart.data.labels;
									
									return originalLabels.map(function(label, index) {
										return {
											text: label + ' (' + data[index] + ')',  
											fillStyle: chart.data.datasets[0].backgroundColor[index],
											draw: function(chartArea) {
												var ctx = chartArea.chart.ctx;
												var x = chartArea.x + chartArea.width / 2;
												var y = chartArea.y + chartArea.height / 2;
												var radius = 5;
												ctx.beginPath();
												ctx.arc(x, y, radius, 0, 2 * Math.PI);
												ctx.fillStyle = this.fillStyle;
												ctx.fill();
											}
										};
									});
								}
							},
							onHover: function() {
								document.body.style.cursor = 'pointer';
							},
							onLeave: function() {
								document.body.style.cursor = 'default';
							},
							onClick: function(_, legendItem) {
								var label = legendItem.text.split(' ')[0];
								if (label === "New") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'wk.application.form',
										name: 'New Applications',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_new: 1},
									});
								} 
								else if (label === "Confirmed") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'wk.application.form',
										name: 'Confirmed Applications',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_confirm: 1},
									});
								}
								else if (label === "Enrolled") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'wk.application.form',
										name: 'Enrolled Applications',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_enroll: 1},
									});
								}
								else if (label === "Cancelled") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'wk.application.form',
										name: 'Cancelled Applications',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_cancel: 1},
									});
								}
							}
						},
					},
				},
			});
		});
	}

	render_faculty_pie_graph() {
		var facultyPieChartElement = document.getElementById('faculty_pie_chart');
		if (facultyPieChartElement) {
			document.getElementById('faculty_pie_chart').replaceWith(Object.assign(document.createElement('canvas'), { id: 'faculty_pie_chart', height: 220 }));
			var self = this;
			var chart2 = new Chart('faculty_pie_chart', {
				type: 'doughnut',
				data: {
					labels: ['Present', 'Absent'],
					datasets: [{
						backgroundColor: ["#2563EA", "#F77171"],
						data: this.teacher,
					}],
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					cutout: "75%",
					plugins: {
						legend: {
							position: 'right',
							labels: {
								boxWidth: 15,
								generateLabels: function(chart) {
									var originalLabels = chart.data.labels;
									var data = chart.data.datasets[0].data;
									return originalLabels.map(function(label, index) {
										return {
											text: label + ' (' + data[index] + ')',
											fillStyle: chart.data.datasets[0].backgroundColor[index],
											draw: function(chartArea) {
												var ctx = chartArea.chart.ctx;
												var x = chartArea.x + chartArea.width / 2;
												var y = chartArea.y + chartArea.height / 2;
												var radius = 5;
												ctx.beginPath();
												ctx.arc(x, y, radius, 0, 2 * Math.PI);
												ctx.fillStyle = this.fillStyle;
												ctx.fill();
											}
										};
									});
								}
							},
							onHover: function(event, legendItem, legend) {
								document.body.style.cursor = 'pointer';
							},
							onLeave: function(event, legendItem, legend) {
								document.body.style.cursor = 'default';
							},
							onClick: function(event, legendItem, legend) {
								var label = legendItem.text.split(' ')[0];
		
								var today = new Date();
								today.setUTCHours(0, 0, 0, 0);
								var formattedDate = today.toISOString().split('T')[0] + ' 00:00:00';

								if (label === "Present") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'hr.employee',
										name: 'Present Faculty',
										views: [[false, 'list'],[false, 'form']],
										domain:[
											['is_teacher','=',true],
											['attendance_ids.check_in' ,'>=',formattedDate]
										],
									});
								} 
								else if (label === "Absent") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'hr.employee',
										name: 'Absent Faculty',
										views: [[false, 'list'],[false, 'form']],
										domain: [
											['is_teacher', '=', true],
											'|',
											['last_check_in','=',false],
											['last_check_in', '<', formattedDate],
										],
									});
								}							
							}
						},
					},
				},
				plugins: [{
					id: 'faculty_pie_chart',
					beforeDraw: function(chart) {
						if (chart.canvas.id === 'faculty_pie_chart') {
							var ctx = chart.ctx,
								cw = chart.width,
								ch = chart.height;
		
							var vals = chart.data.datasets[0].data;
							var total = vals.reduce((sum, value) => sum + value, 0);
		
							ctx.restore();
							ctx.clearRect(0, 0, cw, ch);
							
							ctx.textBaseline = "middle";
							var fontFamily = 'Inter';
							ctx.font = '400 20px ' + fontFamily;
							ctx.textAlign = 'center'; 
							ctx.fillStyle = '#000000';
							var verticalShift = -15;
							var offset = -50; 
							ctx.fillText('Total Faculty', cw / 2 + offset, ch / 2  + verticalShift);

							ctx.font = '700 40px ' + fontFamily;
							ctx.fillStyle = '#000000';
							ctx.fillText(total, cw / 2 + offset, ch / 2+ 30 +verticalShift);
							ctx.save();
						}
					}
				}]
			});
		}
	}

	render_student_pie_graph() {
		var studentPieChartElement = document.getElementById('student_pie_chart');
		if (studentPieChartElement) {
			studentPieChartElement.replaceWith(Object.assign(document.createElement('canvas'), { id: 'student_pie_chart', height: 220 }));
			var self = this;
			var chart2 = new Chart('student_pie_chart', {
				type: 'doughnut',
				data: {
					labels: ['Present', 'Absent'],
					datasets: [{
						backgroundColor: ["#2563EA", "#F77171"],
						data: this.student,
					}],
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					cutout: "75%",
					plugins: {
						legend: {
							position: 'right',
							labels: {
								boxWidth: 15,
								generateLabels: function(chart) {
									var originalLabels = chart.data.labels;
									var data = chart.data.datasets[0].data;
			
									return originalLabels.map(function(label, index) {
										return {
											text: label + ' (' + data[index] + ')',
											fillStyle: chart.data.datasets[0].backgroundColor[index],
											draw: function(chartArea) {
												var ctx = chartArea.chart.ctx;
												var x = chartArea.x + chartArea.width / 2;
												var y = chartArea.y + chartArea.height / 2;
												var radius = 8;
												
												ctx.beginPath();
												ctx.arc(x, y, radius, 0, 2 * Math.PI);
												ctx.fillStyle = this.fillStyle;
												ctx.fill();
											}
										};
									});
								}
							},
							onHover: function(event, legendItem, legend) {
								document.body.style.cursor = 'pointer';
							},
							onLeave: function(event, legendItem, legend) {
								document.body.style.cursor = 'default';
							},
							onClick: function(event, legendItem, legend) {
								var label = legendItem.text.split(' ')[0];
								if (label === "Present") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'wk.student.attendance',
										name: 'Present Students',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_present: 1,search_default_group_by_today:1},
									});
								} 
								else if (label === "Absent") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'wk.student.attendance',
										name: 'Absent Students',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_absent: 1,search_default_group_by_today:1},
									});
								}
							}
						},
					},
				},
				plugins: [{
					id: 'student_pie_chart',
					beforeDraw: function(chart) {
						if (chart.canvas.id === 'student_pie_chart') {
							var ctx = chart.ctx,
								cw = chart.width,
								ch = chart.height;
			
							var vals = chart.data.datasets[0].data;
							var total = vals.reduce((sum, value) => sum + value, 0);
			
							ctx.restore();
							ctx.clearRect(0, 0, cw, ch);
							
							ctx.textBaseline = "middle";
							var fontFamily = 'Inter';
							ctx.font = '400 20px ' + fontFamily;
							ctx.textAlign = 'center'; 
							ctx.fillStyle = '#000000';
							var verticalShift = -15;
							var offset = -50; 
							ctx.fillText('Total Students', cw / 2 + offset, ch / 2  + verticalShift);
			
							ctx.font = '700 40px ' + fontFamily;
							ctx.fillStyle = '#000000';
							ctx.fillText(total, cw / 2 + offset, ch / 2 + 30 + verticalShift);
							ctx.save();
						}
					}
				}]
			});
		}
	}

	render_faculty_student_pie_graph(){
		var PieChartElement = document.getElementById('faculty_student_pie_chart');
		if (PieChartElement) {
			PieChartElement.replaceWith(Object.assign(document.createElement('canvas'), { id: 'faculty_student_pie_chart', height: 210 }));
			var self = this;
			var chart2 = new Chart('faculty_student_pie_chart', {
				type: 'doughnut',
				data: {
					labels: ['Present', 'Absent'],
					datasets: [{
						backgroundColor: ["#2563EA", "#F77171"],
						data: this.student,
					}],
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					cutout: "75%",
					plugins: {
						legend: {
							position: 'right',
							labels: {
								boxWidth: 15,
								generateLabels: function(chart) {
									var originalLabels = chart.data.labels;
									var data = chart.data.datasets[0].data;
			
									return originalLabels.map(function(label, index) {
										return {
											text: label + ' (' + data[index] + ')',
											fillStyle: chart.data.datasets[0].backgroundColor[index],
											draw: function(chartArea) {
												var ctx = chartArea.chart.ctx;
												var x = chartArea.x + chartArea.width / 2;
												var y = chartArea.y + chartArea.height / 2;
												var radius = 8;
												
												ctx.beginPath();
												ctx.arc(x, y, radius, 0, 2 * Math.PI);
												ctx.fillStyle = this.fillStyle;
												ctx.fill();
											}
										};
									});
								}
							},
							onHover: function(event, legendItem, legend) {
								document.body.style.cursor = 'pointer';
							},
							onLeave: function(event, legendItem, legend) {
								document.body.style.cursor = 'default';
							},
							onClick: function(event, legendItem, legend) {
								var label = legendItem.text.split(' ')[0];
								if (label === "Present") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'wk.student.attendance',
										name: 'Present Students',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_present: 1,search_default_group_by_today:1},
									});
								} 
								else if (label === "Absent") {
									self.action.doAction({
										type: "ir.actions.act_window",
										res_model: 'wk.student.attendance',
										name: 'Absent Students',
										views: [[false, 'list'],[false, 'form']],
										context:{ search_default_absent: 1,search_default_group_by_today:1},
									});
								}
							}
						},
					},
				},
				plugins: [{
					id: 'faculty_student_pie_chart',
					beforeDraw: function(chart) {
						if (chart.canvas.id === 'faculty_student_pie_chart') {
							var ctx = chart.ctx,
								cw = chart.width,
								ch = chart.height;
			
							var vals = chart.data.datasets[0].data;
							var total = vals.reduce((sum, value) => sum + value, 0);
			
							ctx.restore();
							ctx.clearRect(0, 0, cw, ch);
							
							ctx.textBaseline = "middle";
							var fontFamily = 'Inter';
							ctx.font = '400 20px ' + fontFamily;
							ctx.textAlign = 'center'; 
							ctx.fillStyle = '#000000';
							var verticalShift = -15;
							var offset = -50; 
							ctx.fillText('Students', cw / 2 + offset, ch / 2  + verticalShift);
			
							ctx.font = '700 40px ' + fontFamily;
							ctx.fillStyle = '#000000';
							ctx.fillText(total, cw / 2 + offset, ch / 2 + 30 + verticalShift);
							ctx.save();
						}
					}
				}]
			});
		}
	}
	
	
}

SchoolDashboard.template = 'SchoolDashboard'
registry.category("actions").add('action_school_dashboard', SchoolDashboard)
