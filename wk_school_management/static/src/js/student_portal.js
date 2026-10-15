import publicWidget from "@web/legacy/js/public/public_widget";
import { renderToElement } from "@web/core/utils/render";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.student_portal = publicWidget.Widget.extend({
    selector: '.student_portal',
    events: {
        'click #portal_transcript_button': 'fetch_transcript_portal',
        'click .service_class' : 'service_hour_create',
        'click .service_hour_create' : 'fetch_default_time',
        'click .search_icon_button' : 'fetch_searched_assignments',
        'click .discipline_search_icon_button' : 'fetch_searched_discipline',
        'click .notice_search_icon_button' : 'fetch_searched_notice',
        'click a.menu' : 'on_click_portal_menu',
        'click .clickable-assignment' : 'on_click_assignment', 
        'click .submit_assignment' : 'submit_student_assignment',
        'click .assignment_status' : 'on_click_assignment_status',
        'click .clickable-attendance' : 'on_click_attendance', 
        'click .timetable-calendar-view' : 'on_click_timetable_calendar',
        'click .timetable-list-view' : 'on_click_timetable_list',
        'click .clickable-timetable': 'on_clickable_timetable',
        'click .clickable-discipline' : 'on_click_discipline',
        'click .clickable-service_hour' : 'on_click_service_hour',
        'click .clickable-fees' : 'on_click_fee_slip',
        'click .clickable-enrollment' : 'on_click_enrollment',
        'click .clickable-notice' : 'on_click_notice',
        'click .clickable-transport' : 'on_click_transport',
        'click #group_by_dropdown li' : 'fetch_library_groups_by',
        'click .clickable-book' : 'on_click_book_list_view', 

    },
    
    init() {
        this._super(...arguments);
        this.rpc = rpc;
        this.orm = this.bindService("orm");

    },
    
    start: function(){
      const loader = document.getElementById('wk_portal_loader');
      if (loader) {
        loader.classList.add('d-none');
        document.body.classList.remove('wk-portal-loading');
      }

      if (sessionStorage.getItem('sidebar') === 'false' ){
          $('#sidebar_buttons').removeClass('col-2');
          $('#sidebar_buttons').addClass('col-1');
          $('#sidebar_content').addClass('col-11');
          $('#sidebar_buttons li a img').css('margin-left','30%')
          $('.user_img').css('margin-left','20%')
          $('.left_icon').addClass('d-none');
          $('.right_icon').removeClass('d-none');
          $('.sidebar-title').addClass('d-none');
      }

      $('#name_search').show()
      $('#state_selection').hide()
    },

    _showPortalLoader: function(){
      const loader = document.getElementById('wk_portal_loader');
      if (loader) {
        loader.classList.remove('d-none');
        document.body.classList.add('wk-portal-loading');
      }
    },

    on_click_portal_menu: function(ev){
      const target = ev.currentTarget;
      if (!target || !target.getAttribute) {
        return;
      }
      if (target.classList.contains('active')) {
        return;
      }
      const href = target.getAttribute('href');
      if (!href) {
        return;
      }
      const nextUrl = new URL(href, window.location.origin);
      if (nextUrl.pathname === window.location.pathname) {
        return;
      }
      this._showPortalLoader();
    },

    async fetch_library_groups_by(ev){
      var target = $(ev.currentTarget);
      $('#new-data-group').empty()
      if (target.val() == 1){
        $('#name_search').show()
        $('#new-data-group').append('All')
      }
      else if (target.val() == 2){
        $('#name_search').hide()
        $('#new-data-group').append('Issued')
      }
      else if (target.val() == 3){
        $('#name_search').hide()
        $('#new-data-group').append('Todays Return')
      }
      else if (target.val() == 4){
        $('#name_search').hide()
        $('#new-data-group').append('Overdues')
      }
      var search = new URL(window.location).searchParams;
      var data = document.getElementById("new-data-group");
      console.log('--data',data)
      console.log('--data',$(data).text())
      search.set('search', $(data).text());
      location.search = search.toString();
    },

    on_click_book_list_view(ev){
      var target = $(ev.currentTarget)
      var selected_row_id = target.data('href');
      console.log('==',selected_row_id)
      if (selected_row_id){
        window.location.href = window.location.origin + selected_row_id;
        console.log('window.location.href ==',window.location.href )
      }
    },

    async fetch_searched_assignments(ev) {
        ev.preventDefault();
        var search = new URL(window.location).searchParams;
        search.set('search', $('#name_search').val());
        location.search = search.toString();
    },

    async fetch_searched_discipline(ev){
      ev.preventDefault();
      var search = new URL(window.location).searchParams;
      search.set('search', $('#name_search').val());
      location.search = search.toString();
    },

    async fetch_searched_notice(ev){
      ev.preventDefault();
      var search = new URL(window.location).searchParams;
      search.set('search', $('#name_search').val());
      location.search = search.toString();
    },
    
    async fetch_transcript_portal(ev) {
      ev.preventDefault();
      ev.stopPropagation();

      const student = document.getElementById("login_student").value;
      const session = document.getElementById("session_selection").value;
      let error_message = "";
      let subject = [[], {}, {}]; 
      if (session != -1) {
          subject = await this.orm.call("student.student", "fetch_transcript_record", ["", session, student, false]);
      } else {
          error_message = "Please select a session to proceed.";
      }

      const message_div = $(
        renderToElement("wk_school_management.transcript_page", {
          student_information: subject[1],
          school_information: subject[2],
          records: subject[0],
          error_message: error_message,
          issue_date: new Date().toLocaleDateString()
        })
      );
      const container = $('.transcript_data_section');
      container.empty().append(message_div);

      const detail_header = container.find('.p_detail_header')[0];
      const table_header = container.find('.p_table_header')[0];
      const error_message_div = container.find('.p_error_message')[0];
      const table_data = container.find('.p_table_data')[0];

      if (session == -1) {
        if (table_header) table_header.classList.remove("d-none");
        if (error_message_div) error_message_div.classList.remove("d-none");
        if (table_data) table_data.classList.add("d-none");
        if (detail_header) detail_header.classList.add("d-none");
      } else {
        if (table_header) table_header.classList.remove("d-none");
        if (table_data) table_data.classList.remove("d-none");
        if (error_message_div) error_message_div.classList.add("d-none");
        if (detail_header) detail_header.classList.remove("d-none");
      }

      const transcript_table = document.getElementById("transcript_table_header");
      const print_button = document.getElementById("print_transcript_button");

      if (transcript_table && transcript_table.innerHTML.trim() === '') {
          $('#print_transcript_button').addClass('d-none');
      } else {
          $('#print_transcript_button').removeClass('d-none');
          if (print_button && student && session != -1) {
            print_button.href = `/my/transcript/download/${student}/${session}`;
          }
      }
    },

    service_hour_create(ev){
        const name = $('#name').val()
        const start_time = $('#start_time').val()
        const total_hours = $('#total_hours').val()
        const supervisor_id = $('#supervisor_id').val()
        const comment = $('#comment').val()
        const student_id = $('#student_id').val()
  
        if ( !name) {
          $('.name-warning-message').show();
            setTimeout(function(){
            $('.name-warning-message').hide();
            },1000);
        }
        else if (!start_time) {
          $('.start_time-warning-message').show();
            setTimeout(function(){
            $('.start_time-warning-message').hide();
            },1000);
        }
        else if ( !total_hours) {
          $('.total_hours-warning-message').show();
            setTimeout(function(){
            $('.total_hours-warning-message').hide();
            },1000);
        }
        else if (total_hours <= 0) {
          $('.total_hours_value-warning-message').show();
            setTimeout(function(){
            $('.total_hours_value-warning-message').hide();
            },1000);
        }
        else if (supervisor_id == -1) {
          $('.supervisor-warning-message').show();
            setTimeout(function(){
            $('.supervisor-warning-message').hide();
            },1000);
        }
        else if (!comment) {
          $('.comment-warning-message').show();
            setTimeout(function(){
            $('.comment-warning-message').hide();
            },1000);
        }
        else{
          this.rpc('/servicehour/submit', {
            'name' : name,
            'start_time' : start_time,
            'total_hours' : total_hours,
            'supervisor_id' : supervisor_id,
            'student_id' : student_id,
            'comment' : comment,
          }).then((result)=> {
            $('#service_hour_create_modal').modal('toggle');
            location.reload();
          })
        }
      },

    async on_change_transcript_session(ev){
      var $target = $(ev.currentTarget);
        var session = $(`#session_selection option:selected`).val();
        var login_student = $(`#login_student`).val();

        var error_message = ""
        $('#enrollment_selection').children().remove()
        if (session == -1) {

          let option = document.createElement("option");
          option.setAttribute('value', -1);
          
            let optionText = document.createTextNode("Enrollment");
            option.appendChild(optionText);
            enrollment_selection.appendChild(option);
  
          }
          const enrollment_ids =  await this.orm.searchRead("student.enrollment",[["student_id", "=", parseInt(login_student)],['session_id','=',parseInt(session)]],)
          for (let enrollment = 0; enrollment < enrollment_ids.length; enrollment++) {
            let option = document.createElement("option");
            option.setAttribute('value', enrollment_ids[enrollment]['id']);
          
            let optionText = document.createTextNode(enrollment_ids[enrollment]['name']);
            option.appendChild(optionText);          
            enrollment_selection.appendChild(option);
          }
    },
    
    _formatDateTimeLocal: function (date) {
      var year = date.getFullYear();
      var month = String(date.getMonth() + 1).padStart(2, '0'); 
      var day = String(date.getDate()).padStart(2, '0');
      var hours = String(date.getHours()).padStart(2, '0');
      var minutes = String(date.getMinutes()).padStart(2, '0');
      return `${year}-${month}-${day}T${hours}:${minutes}`;
    },

    async fetch_default_time(ev){
      var date = new Date();
      var now = new Date();
      var startTime = this._formatDateTimeLocal(now);
      var endTime = this._formatDateTimeLocal(new Date(now.getTime() + 60 * 60 * 1000)); 
      this.$('#start_time').val(startTime);
      this.$('#end_time').val(endTime);
    },

    on_click_assignment(ev){
      var target = $(ev.currentTarget)
      var selected_row_id = target.data('href');;
      if (selected_row_id){
        this._showPortalLoader();
        window.location.href = window.location.origin + selected_row_id;
      }
    },

    on_click_attendance(ev){
      var target = $(ev.currentTarget)
      var selected_attendance_id = target.data('href');
      if (selected_attendance_id){
        this._showPortalLoader();
        window.location.href = window.location.origin + selected_attendance_id;
      }
    },

    on_clickable_timetable(ev){
      var target = $(ev.currentTarget)
      var selected_timetable_id = target.data('href');
      if (selected_timetable_id){
        this._showPortalLoader();
        window.location.href = window.location.origin + selected_timetable_id;
      }
    },

    on_click_discipline(ev){
      var target = $(ev.currentTarget)
      var selected_discipline_id = target.data('href');
      if (selected_discipline_id){
        this._showPortalLoader();
        window.location.href =  window.location.origin + selected_discipline_id;
      }
    },

    on_click_service_hour(ev){
      var target = $(ev.currentTarget)
      var selected_service_hour_id = target.data('href');
      if (selected_service_hour_id){
        this._showPortalLoader();
        window.location.href = window.location.origin + selected_service_hour_id;
      }
    },

    on_click_fee_slip(ev){
      var target = $(ev.currentTarget)
      var selected_slip_id = target.data('href');
      if (selected_slip_id){
        this._showPortalLoader();
        window.location.href = window.location.origin + selected_slip_id;
      }
    },

    on_click_enrollment(ev){
      var target = $(ev.currentTarget)
      var selected_enrollment_id = target.data('href');
      if (selected_enrollment_id){
        this._showPortalLoader();
        window.location.href = window.location.origin + selected_enrollment_id;
      }
    },

    on_click_notice(ev){
      var target = $(ev.currentTarget)
      var selected_notice_id = target.data('href');
      if (selected_notice_id){
        this._showPortalLoader();
        window.location.href = window.location.origin + selected_notice_id;
      }
    },
    on_click_transport(ev){
      var target = $(ev.currentTarget)
      var selected_transport_id = target.data('href');
      if (selected_transport_id){
        this._showPortalLoader();
        window.location.href = window.location.origin + selected_transport_id;
      }
    },

    submit_student_assignment(ev){
      ev.preventDefault(); 
      const description = $('#description').val();
      const attachement = $('#attachement').val();
      const student_id = $('#student_id').val();
      const assignment_id = $('#assignment_id').val();
      const attachment_type_id = $('input[name="attachment_type_id"]:checked').val();
      const warningMessageDiv = document.getElementById('assignment_type-warning-message');
      
      if (description == 0) {
          $('.description-warning-message').show();
          setTimeout(function(){
              $('.description-warning-message').hide();
          }, 1000);
      }
      else if (!attachment_type_id) {
          $('.attachment_type_id-warning-message').show();
          setTimeout(function(){
              $('.attachment_type_id-warning-message').hide();
          }, 1000);
      }
      else if (attachement == 0) {
          $('.attachement-warning-message').show();
          setTimeout(function(){
              $('.attachement-warning-message').hide();
          }, 1000);
      }
      else{
        const fileInput = document.getElementById('attachement');
        const file = fileInput.files[0];
        
        const fileName = file.name;
        var reader = new FileReader();
  
        reader.readAsDataURL(file);
        reader.onload = function (ev) {
            const mimeTypeMapping = {
              'image': 'image/',
              'pdf': 'application/pdf',
              'zip': 'application/zip',
              'doc': 'application/msword'
            };
            
            const mimeType = file.type;
            const expectedMimeType = mimeTypeMapping[attachment_type_id];
            
            if (!mimeType.startsWith(expectedMimeType)) {
              warningMessageDiv.innerHTML = `Invalid file type. Expected a file of type ${attachment_type_id}.`;
              console.log(warningMessageDiv)
              $('#assignment_type-warning-message').show();
                 setTimeout(function(){
                  $('#assignment_type-warning-message').hide();
                 },1500);
            }
            else {
              let dataURL = reader.result;
              rpc('/assignment/submit', {
                'description' : description,
                'attachement' : dataURL,
                'assignment_id' : assignment_id,
                'student_id' : student_id,
                'fileName' : fileName,
                'attachment_type_id' : attachment_type_id
              }).then((result)=> {
                $('#submit_assignment_modal').modal('toggle');
                $('#success_submit_assignment_modal').modal('toggle');
              })
            }
        }
      }
    },

    on_click_assignment_status(ev){
      $('#success_submit_assignment_modal').modal('toggle');
      location.reload();
    },

    on_click_timetable_calendar(ev){
      $('.timetable-calendar-view').removeClass('inactive-timetable').addClass('active-timetable');
      $('.timetable-list-view').addClass('inactive-timetable').removeClass('active-timetable');
    },
    on_click_timetable_list(ev){
      $('.timetable-list-view').addClass('active-timetable').removeClass('inactive-timetable');
      $('.timetable-calendar-view').removeClass('active-timetable').addClass('inactive-timetable');
    }
  
})

publicWidget.registry.student_timesheet = publicWidget.Widget.extend({
  selector: '#student_timesheet',
  events: {
      'click #student_timesheet':'on_click_timesheet_menu',
  },
  
  init() {
      this._super(...arguments);
      this.rpc = rpc;
      this.orm = this.bindService("orm");
  },
  
  start: function(){
    if ($('#calendar').length == 1 ) {
      this.on_click_timesheet_menu();
    }
  },

  async on_click_timesheet_menu(){
      $('div#calendar').children().remove();

      var calendarEl = $('div#calendar')[0];

      let timesheet_details = await this.rpc("/my/timesheet", {});

      if (calendarEl && timesheet_details && timesheet_details['data']) {
        $(calendarEl).css({
          'max-width': '100%',
          'overflow-x': 'auto',
          'min-height': '500px',
        });

        // Use requestAnimationFrame for faster DOM updates and avoid unnecessary popovers
        var calendar = new FullCalendar.Calendar(calendarEl, {
          timeZone: 'local',
          initialView: 'timeGridWeek',
          nowIndicator: true,
          headerToolbar: {
            left: 'prev,next',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
          },
          views: {
            dayGridMonth: { buttonText: "Month" },
            timeGridWeek: { buttonText: "Week" },
            timeGridDay: { buttonText: "Day" },
          },
          slotEventOverlap: false,
          eventClick: function (info) {
            const props = info.event.extendedProps || {};
            const href = "/my/timetables/" + info.event.id;

            $(info.el).popover({
                html: true,
                trigger: 'focus',
                container: 'body',
                title: info.event.title,
                content: `
                    <div class="row">
                        <div class="col-6 fw-bold">Date :</div>
                        <div class="col-6 text-muted">${props.date || ''}</div>
                    </div>

                    <div class="row">
                        <div class="col-6 fw-bold">Start Time :</div>
                        <div class="col-6 text-muted">${props.start_time || ''}</div>
                    </div>

                    <div class="row">
                        <div class="col-6 fw-bold">End Time :</div>
                        <div class="col-6 text-muted">${props.end_time || ''}</div>
                    </div>

                    <div class="row">
                        <div class="col-6 fw-bold">Location :</div>
                        <div class="col-6 text-muted">${props.location || ''}</div>
                    </div>

                    <div class="mt-2">
                        <a href="${href}" style="color:#2563EA;">View Class Details</a>
                    </div>
                `
              });
              $(info.el).popover('show');
          },
          eventLimit: true,
          events: timesheet_details['data'].map(ev => ({
              ...ev,
              start: ev.extendedProps.start_time, 
              end: ev.extendedProps.end_time
          })),

          datesSet: function() {
            window.requestAnimationFrame(function() {
              $('.fc-col-header-cell').each(function() {
                var $cell = $(this);
                var dayName = $cell.find('.fc-col-header-cell-cushion').text();
                var date = $cell.attr('data-date');
                if (dayName && date) {
                  $cell.css({
                    'overflow': 'hidden',
                    'text-overflow': 'ellipsis',
                    'white-space': 'nowrap',
                    'max-width': '90px',
                    'cursor': 'pointer'
                  });
                  $cell.attr('title', dayName + ' ' + date);
                  if (!$cell.data('bs.popover')) {
                    $cell.popover({
                      html: true,
                      trigger: 'hover',
                      container: 'body',
                      placement: 'top',
                      content: `<div><b>${dayName}</b><br>${date}</div>`,
                    });
                  }
                }
              });
            });
          }
        });
        calendar.render();

        // Fixing of FullCalendar toolbar overflow issues
        $('.fc-header-toolbar').css({
          'flex-wrap': 'wrap',
          'overflow-x': 'auto',
          'width': '100%',
          'box-sizing': 'border-box'
        });
        $('.fc-toolbar-chunk').css({
          'min-width': '0'
        });
        $('.fc-toolbar-title').css({
          'white-space': 'normal',
          'overflow': 'hidden',
          'text-overflow': 'ellipsis'
        });
      }
  },

})

