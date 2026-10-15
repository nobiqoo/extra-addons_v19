import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState} from "@odoo/owl";
var D3_COLORS = ["#1f77b4","#ff7f0e","#aec7e8","#ffbb78","#2ca02c","#98df8a","#d62728", "#ff9896","#9467bd","#c5b0d5","#8c564b","#c49c94","#e377c2","#f7b6d2", "#7f7f7f","#c7c7c7","#bcbd22","#dbdb8d","#17becf","#9edae5"];

export class TranscriptPage extends Component {
	setup() {
        this.orm = useService("orm");
        this.state = useState({
            sessions : [],
            enrollment_ids :[],
            records :[],
            student_subjects :{},
            grade_symbol :[],
            error_message : "",
            student_information : {},
            school_information : {},
            record_data : {},

            students: [],
            enrollments: [],
            subjects:[],

            session: "",
            student: "",
            issue_date: "",
            
        });
        this.getStudentRecord()
        this.getSessionRecord()
        var action_manager = document.querySelector('.o_action_manager');
        action_manager.classList.add("transcript_page");
        action_manager.style.overflow = "auto";
		
	}	

    async _fetchenrollment_session(selected_session){
        var selected_session_id = parseInt(selected_session)
        const enrollment = await this.orm.call("student.enrollment", "get_student_record", ["", selected_session_id]);
        this.state.enrollment_ids = enrollment      
    }

    change_enrollment_session_data(){
        var self = this
		var selected_option = document.querySelector('#session_selection').value
        const res =  this._fetchenrollment_session(selected_option)
        return res
    }

    async getSessionRecord(){
        const session = await this.orm.searchRead("wk.school.session", [["state", "=", "progress"]]);
        this.state.sessions = session;
    }

    async _fetch_transcript_record() {
        var session = parseInt(document.querySelector('#session_selection').value);
        var student = parseInt(document.querySelector('#enrollment_ids_selection').value);

        var table_header = document.querySelector('.table_header');
        var error_message = document.querySelector('.error_message');
        var table_data = document.querySelector('.table_data');
        var detail_header = document.querySelector('.detail_header');

        let message = "";

        const sessionMissing = session === -1;
        const studentMissing = student === -1;

        if (sessionMissing && studentMissing) {
            message = "Please select both session and student to proceed.";
        } else if (studentMissing) {
            message = "Please select a student to proceed.";
        }

        if (message) {
            this.state.error_message = message;
            table_header.classList.remove("d-none");
            error_message.classList.remove("d-none");
            table_data.classList.add("d-none");
            detail_header.classList.add("d-none");
            return;
        }
        const subject = await this.orm.call("student.student", "fetch_transcript_record", ["", session, student]);

        const now = new Date();
        this.state.issue_date = now.toISOString().slice(0, 10);
        this.state.records = subject[0];
        this.state.student_information = subject[1];
        this.state.school_information = subject[2];
        this.state.session = session;
        this.state.student = student;
        this.state.grade_symbol = subject[0]['grade_symbol'];
        table_data.classList.remove("d-none");
        error_message.classList.add("d-none");
        table_header.classList.remove("d-none");
        detail_header.classList.remove("d-none");
    }

    async getStudentRecord(){
        const res =  await this.orm.searchRead("student.student",[],)
        this.state.students = res 
    }
    
    async _fetchenrollment(selected_student){
        var selected_student_id = parseInt(selected_student)
        const enrollment =  await this.orm.searchRead("student.enrollment",[["student_id", "=", selected_student_id]],)
        this.state.enrollments = enrollment    
    }

}
TranscriptPage.template = 'transcript_template'
registry.category("actions").add('action_dashboard_transcript', TranscriptPage)
