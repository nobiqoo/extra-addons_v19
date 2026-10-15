import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.student_portal_attendance = publicWidget.Widget.extend({
    selector: '.attendance-view-buttons',
    events: {
        'click .attendance-list-view'     : 'on_click_attendance_list_view',
    },
    
    init() {
        this._super(...arguments);
        this.rpc = rpc;
        this.orm = this.bindService("orm");

    },
    
    on_click_attendance_list_view(ev){
        $('.attendance-list-view').addClass('btn-active').removeClass('btn-inactive');
        $('.attendance-calendar-view').removeClass('btn-active').addClass('btn-inactive');
    },
})

publicWidget.registry.student_attendance_calendar = publicWidget.Widget.extend({
    selector: '.attendance-calendar-view',
    events: {
        'click .attendance-calendar-view': 'on_click_attendance_calendar_view',
    },
    
    init() {
        this._super(...arguments);
        this.rpc = rpc;
        this.orm = this.bindService("orm");
  
    },

    start: function(){
        if ($('#attendance-calendar').length == 1) {
          this.on_click_attendance_calendar_view();
        }
      },

    async on_click_attendance_calendar_view() {
        var calendarEl = $('div#attendance-calendar')[0];
        var attendance_details = await this.rpc("/my/student/attendance", {});

        // Remove any existing calendar to avoid duplicate rendering
        if (calendarEl && calendarEl._fullCalendar) {
            calendarEl._fullCalendar.destroy();
        }

        var calendar = new window.FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            initialDate: new Date(),
            nowIndicator: true,
            headerToolbar: {
                left: 'prev,next',
                center: 'title',
                right: 'today',
            },
            views: {
                dayGridMonth: { buttonText: "Month" },
            },
            events: attendance_details['data'],
            dateClick: function(info) {
                var selectedDate = info.dateStr;
                window.location.href = '/my/attendances/detail?date=' + selectedDate;
            },
            dayCellDidMount: function(info) {
                // Center all dates and prevent overlap by using flex and min/max sizes
                $(info.el).find('.fc-daygrid-day-number').css({
                    'display': 'flex',
                    'align-items': 'center',
                    'justify-content': 'center',
                    'width': '2.2em !important',
                    'height': '2.2em !important',
                    'margin': '0 auto',
                    'font-weight': '500',
                    'min-width': '2.2em !important',
                    'min-height': '2.2em !important',
                    'box-sizing': 'border-box',
                });

                // Highlight Sundays
                if (info.date.getDay() === 0) {
                    $(info.el).find('a.fc-daygrid-day-number').addClass('fc-sunday-circle');
                }

                // Highlight days with events (add circular class)
                var cellDate = info.date;
                var hasEvent = isEventOnDate(cellDate, attendance_details['data']);
                if (hasEvent) {
                    var date = cellDate.toISOString().split('T')[0];
                    $(`[data-date=${date}]`).each(function() {
                        $(this).find('a.fc-daygrid-day-number').addClass('fc-event-circle');
                    });
                }
            },
            eventDidMount: function(info) {
                let state = info.event.extendedProps.state || info.event.extendedProps?.state;
                if (state === 'public_holiday') {
                    info.el.classList.add('fc-event-public_holiday');
                    // Add circular style to the date number
                    let dateAnchor = $(info.el).closest('td').find('a.fc-daygrid-day-number');
                    dateAnchor.addClass('fc-event-circle fc-event-public_holiday-circle');
                    // Add holiday name below the date
                    var holidayDiv = document.createElement('div');
                    holidayDiv.className = 'public-holiday-name';
                    holidayDiv.textContent = info.event.extendedProps.name;
                    info.el.appendChild(holidayDiv);

                    // Check if the holiday name overflows the grid block
                    setTimeout(function() {
                        var isOverflowing = holidayDiv.scrollWidth > holidayDiv.clientWidth || holidayDiv.scrollHeight > holidayDiv.clientHeight;
                        if (isOverflowing) {
                            // Add popover (using title attribute for simplicity)
                            holidayDiv.setAttribute('title', info.event.extendedProps.name);
                            $(holidayDiv).css({
                                'white-space': 'nowrap',
                                'overflow': 'hidden',
                                'text-overflow': 'ellipsis',
                                'cursor': 'pointer',
                            });
                            if ($.fn.tooltip) {
                                $(holidayDiv).tooltip({ placement: 'top', trigger: 'hover' });
                            }
                        }
                    }, 0);
                } else if (state === 'present') {
                    info.el.classList.add('fc-event-present');
                    let dateAnchor = $(info.el).closest('td').find('a.fc-daygrid-day-number');
                    dateAnchor.addClass('fc-event-circle fc-event-present-circle');
                } else if (state === 'absent') {
                    info.el.classList.add('fc-event-absent');
                    let dateAnchor = $(info.el).closest('td').find('a.fc-daygrid-day-number');
                    dateAnchor.addClass('fc-event-circle fc-event-absent-circle');
                }
            },
            height: window.innerWidth < 600 ? 'auto' : 'auto',
            contentHeight: window.innerWidth < 600 ? 'auto' : 'auto',
            aspectRatio: window.innerWidth < 600 ? 0.8 : 1.35,
        });

        function isEventOnDate(dateToCheck, events) {
            return events.some(function(event) {
                var eventDate = new Date(event.date);
                return eventDate.toISOString().split('T')[0] === dateToCheck.toISOString().split('T')[0];
            });
        }

        calendar.render();
        calendarEl._fullCalendar = calendar;
        
        if ($('.fc-view-container').length > 1) {
            $('.fc-view-container').not(':last').remove();
            $('.fc-toolbar').not(':last').remove();
        }

    },
})  

// DASHBOARD CALENDAR ATTENDANCE

publicWidget.registry.dashboard_attendance_calendar = publicWidget.Widget.extend({
    selector: '.attendance_card_calendar',
    events: {
        'click #student_dashboard': 'card_calendar_view',
    },
    init() {
        this._super(...arguments);
        this.rpc = rpc;
        this.orm = this.bindService("orm");
    },

    start: function () {
        if ($('.attendance_card_calendar').length === 1) {
            this.card_calendar_view();
        }
    },

    async card_calendar_view(ev) {
        const calendarEl = $('div.attendance_card_calendar')[0];
        const attendance_details = await this.rpc("/my/student/attendance", {});

        let filtered_events = [];
        let seen_dates = new Set();

        attendance_details['data'].forEach(event => {
            const dateStr = new Date(event.date).toISOString().split('T')[0];
            if (event.state === 'public_holiday') {
                filtered_events.push(event);
                seen_dates.add(dateStr);
            }
        });

        attendance_details['data'].forEach(event => {
            const dateStr = new Date(event.date).toISOString().split('T')[0];
            if ((event.state === 'present' || event.state === 'absent') && !seen_dates.has(dateStr)) {
                filtered_events.push(event);
            }
        });

        const calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            initialDate: new Date(),
            nowIndicator: true,
            events: filtered_events,

            dayCellDidMount: function (info) {
                $('td.fc-day.fc-day-sun').each(function () {
                    $(this).find('a.fc-daygrid-day-number').addClass('fc-sunday-circle');
                });

                if ($(info.el).hasClass("fc-day-other")) {
                    $(info.el).addClass("fc-past-day-opacity");
                    $(info.el).find(".fc-daygrid-day-top").removeClass();
                }

                const cellDate = info.date;
                const dateStr = cellDate.toISOString().split('T')[0];
                const hasEvent = isEventOnDate(dateStr, filtered_events);

                if (hasEvent) {
                    $(`[data-date=${dateStr}]`).each(function () {
                        $(this).find('a.fc-daygrid-day-number').css('color', 'white');
                    });
                }
            }
        });

        function isEventOnDate(dateStr, events) {
            return events.some(function (event) {
                const eventDate = new Date(event.date).toISOString().split('T')[0];
                return eventDate === dateStr;
            });
        }
        calendar.render();
    },
})  
