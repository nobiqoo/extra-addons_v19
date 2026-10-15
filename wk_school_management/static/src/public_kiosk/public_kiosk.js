import { App, whenReady, Component, useState, onMounted, onWillDestroy, onWillStart  } from "@odoo/owl";
import { BarcodeScanner } from "@barcodes/components/barcode_scanner";
import { makeEnv, startServices } from "@web/env";
import { getTemplate } from "@web/core/templates";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useService , useBus } from "@web/core/utils/hooks";
import { url } from "@web/core/utils/urls";
import { StudentKioskBarcodeScanner } from "@wk_school_management/components/kiosk_barcode/kiosk_barcode";
import { session } from "@web/session";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { AssetsLoadingError, loadJS } from '@web/core/assets';

const { DateTime } = luxon;

class kioskAttendanceApp extends Component{
    static template = "wk_school_management.public_kiosk_app";
    static props = {
        token: { type: String },
        companyId: { type: Number },
        companyName: { type: String },
        kioskMode: { type: String },
        barcodeSource: { type: String },
        fromTrialMode: { type: Boolean },
    };

    static components = {
        MainComponentsContainer,
        StudentKioskBarcodeScanner,
        BarcodeScanner,
    };

    setup() {
        const barcode = useService("barcode");
        useBus(barcode.bus, "barcode_scanned", (ev) => this.onBarcodeScanned(ev.detail.barcode));
        this.notification = useService("notification");
        this.userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        this.companyImageUrl = url("/web/binary/company_logo", {
            company: this.props.companyId,
        });
        this.state = useState({
            time: '',
            date: '',
            dayOfWeek: '',
            barcode: false,
            barcodeIsSet: false,
            companyImageUrl: this.companyImageUrl,
        });   

        onWillStart(async () => {
            try {
                await Promise.all([
                    loadJS('https://cdn.jsdelivr.net/npm/sweetalert2@11')
                ])
            } catch (error) {
                if (!(error instanceof AssetsLoadingError)) {
                    throw error;
                }
            }
        });

        onMounted(async () => {
            await this.fetchUserTimezone();
            this.startClock();
        });

        onWillDestroy(() => {
            if (this.clockInterval) {
                clearInterval(this.clockInterval);
            }
        });
    }

    async fetchUserTimezone() {
        try {
            const userTimezone = await rpc('/school_management/user_timezone',{});
            this.userTimezone = userTimezone || Intl.DateTimeFormat().resolvedOptions().timeZone;
            this.getDateTime();
        } catch (error) {
            this.userTimezone = 'UTC';
            this.getDateTime();
        }
    }

    getDateTime() {
        const now = DateTime.now().setZone(this.userTimezone);
        const dateTimeData = {
            dayOfWeek: now.toFormat("cccc"),
            date: now.toLocaleString({
                ...DateTime.DATE_FULL,
                weekday: undefined,
            }),
            time: now.toFormat("hh:mm:ss a"),
        };
        return dateTimeData;
    }  

    startClock(){
        this.clockInterval = setInterval(() => {
            const currentTime = this.getDateTime();
            this.state.time = currentTime.time;
            this.state.date = currentTime.date;
            this.state.dayOfWeek = currentTime.dayOfWeek;
        }, 1000);
    }

    displayNotification(text){
        this.notification.add(text, { type: "danger" });
    }

    async onBarcodeScanned(barcode){
        if (this.lockScanner) {
            return;
        }
        this.lockScanner = true;
        let result;
        if (barcode.includes('/student/kiosk/attendance/')) {
            const urlParts = barcode.split('/');
            const enrollment_number = urlParts[4];

            result = await rpc('/school_management/mark_attendance', {
                'enrollment_number': enrollment_number,
                'token': this.props.token,
            });

        }else{
            result = await rpc('/school_management/attendance_barcode_scanned',
            {
                'barcode': barcode,
                'token': this.props.token
            })
        }
        if (result && result.student_name) {
            Swal.fire({
                title: 'Attendance Marked',
                text: `Dear ${result.student_name}, your attendance has been successfully marked.`,
                imageUrl: result.student_avatar || '',
                imageWidth: 100,
                imageHeight: 100,
                imageAlt: 'Student Avatar',
                icon: 'success',
                timer: 3000,
                showConfirmButton: false
            });
        }else{
            this.displayNotification(_t("No student corresponding to Badge ID '%(barcode)s.'", { barcode }))
        }
        this.lockScanner = false
    }
}

export async function createPublicKioskAttendance(document, kiosk_backend_info) {
    await whenReady();
    const env = makeEnv();
    await startServices(env);
    session.server_version_info = kiosk_backend_info.server_version_info;
    const app = new App(kioskAttendanceApp, {
        getTemplate,
        env: env,
        props:
            {
                token : kiosk_backend_info.token,
                companyId: kiosk_backend_info.company_id,
                companyName: kiosk_backend_info.company_name,
                kioskMode: kiosk_backend_info.kiosk_mode,
                barcodeSource: kiosk_backend_info.barcode_source,
                fromTrialMode: kiosk_backend_info.from_trial_mode,
            },
        dev: env.debug,
        translateFn: _t,
        translatableAttributes: ["data-tooltip"],
    });
    return app.mount(document.body);
}
export default { kioskAttendanceApp, createPublicKioskAttendance };
