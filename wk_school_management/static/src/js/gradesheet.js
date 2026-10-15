import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState} from "@odoo/owl";

export class GradesheetPage extends Component {
	
	setup() {
        this.orm = useService("orm");
        this.state = useState({
            sessions : [],
            grades : [],
            sections: [],
            showSectionDropdown: false,
            populate_class :[],
            errr_message :"",
            assignments : [],
            students : [],
            student_score : [],
            average_score : [],
            col_average: [],
            last_col : "",
            
        });		
        this.getSessionRecord()
	}	

    async getSessionRecord(){
        const session =  await this.orm.searchRead("wk.school.session",[],)
        this.state.sessions = session 
        const grades = await this.orm.searchRead("wk.school.grade",[],)
        this.state.grades = grades 
    }

    async _fetch_populate_class(selected_session,selected_grade,section_option){
        var selected_session_id = parseInt(selected_session)
        var selected_grade_id = parseInt(selected_grade)
        var selected_section = parseInt(section_option)
        const populate_class = await this.orm.call("wk.school.class", "get_populate_class_record", ["", selected_session_id, selected_grade_id,selected_section]);
        this.state.populate_class = populate_class    
    }

    async getSectionsByGrade(gradeId) {
        if (this.state.selected_grade !== gradeId) {
            const sectionDropdown = document.querySelector('#section_selection');
            if (sectionDropdown) {
                sectionDropdown.value = "-1";
            }
            this.state.sections = [];
            this.state.selected_grade = gradeId;
        }

        const sections = await this.orm.searchRead("wk.grade.section", [['grade_id', '=', gradeId]], ['name']);
        this.state.sections = sections;
        this.state.showSectionDropdown = sections.length > 0;
    }

    async onchange_session_grade_data() {
        const selected_option = document.querySelector('#session_selection').value;
        const grades_option = document.querySelector('#grades_selection').value;
        const classDropdown = document.querySelector('#class_selection');

        if (classDropdown) {
            classDropdown.value = "-1";
        }
        this.state.populate_class = [];

        if (selected_option == -1 || grades_option == -1) {
            return;
        }
        await this.getSectionsByGrade(parseInt(grades_option));
        const sectionElement = document.querySelector('#section_selection');
        let sectionId = null;
        if (sectionElement) {
            const value = parseInt(sectionElement.value);
            if (!isNaN(value) && value !== -1) {
                sectionId = value;
            }
        }
        await this._fetch_populate_class(selected_option, grades_option, sectionId);
    }

    async _fetch_gradesheet_record(){
        var populate_class = parseInt(document.querySelector('#class_selection').value);
        var table_header = document.querySelector('.table_header');
        var error_message = document.querySelector('.error_message');
        var table_data = document.querySelector('.table_data');
        if(populate_class == -1){
            const message = "Kindly Fill all the details"
            this.state.error_message = message
            table_header.classList.remove("d-none");
            error_message.classList.remove("d-none");
            table_data.classList.add("d-none");
        }
        else{
        const assignment = await this.orm.call("wk.school.class", "fetch_gradesheet_record", ["", populate_class]);
        this.state.students = assignment[0]
        this.state.assignments = assignment[1]
        this.state.student_score = assignment[2]
        this.state.average_score = assignment[3]
        this.state.col_average = assignment[4]
        this.state.last_col = assignment[5]
        table_data.classList.remove("d-none");
        error_message.classList.add("d-none");
        table_header.classList.remove("d-none");
        }
    }
}
GradesheetPage.template = 'gradesheet_template'
registry.category("actions").add('action_dashboard_gradesheet', GradesheetPage)
