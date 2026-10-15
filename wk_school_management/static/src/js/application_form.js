import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { KeepLast } from "@web/core/utils/concurrency";

publicWidget.registry.ApplicationFormWidget = publicWidget.Widget.extend({
    selector: '.app_form',
    events: {
        'change #student_state': '_onStateChange',
        'change #student_country':'_onCountryChange',
        'change #disability': 'onDisabilityChange',
        'click .image-preview': 'triggerFileInput',
        'change #student_image': 'previewImage',
        'change #child_id': 'onBranchSelection',
        'submit': 'preventFormSubmit'
    },
    
    init() {
        this._super(...arguments);
        this.rpc = rpc;
        this.orm = this.bindService("orm");
		this.keepLast = new KeepLast();
    },

    start: function(){ 
        if($(document).find('#address_map').length){
            this.initialize();
        }
        var $childIdElement = $('#child_id');
        if ($childIdElement.length && $childIdElement.val()) {
            this.onBranchSelection();
        }
        const gradeSelect = document.getElementById('grade_id');
        if (gradeSelect && gradeSelect.options.length === 2) {
            gradeSelect.value = gradeSelect.options[1].value;
            gradeSelect.setAttribute('disabled', 'true');
        }
    },

    async initialize(branchId = null, isBranchChange = false){
        var map = new google.maps.Map(document.getElementById('address_map'), {
            zoom: 12,
            center: { lat: 28.0, lng: 70.0},
            mapTypeId: 'roadmap'
        });

        let companyDetails;

        if (isBranchChange && branchId) {
            companyDetails = await this.getCompanyAddress(branchId);
        } else {
            companyDetails = await this.getCompanyAddress();
        }

        var geocoder = new google.maps.Geocoder();
        geocoder.geocode({ 'address': companyDetails[0] }, (results, status) => {
            if (status === google.maps.GeocoderStatus.OK) {
                var location = results[0].geometry.location;
                map.setCenter(location);
                var marker = new google.maps.Marker({
                    map: map,
                    position: location,
                    title: companyDetails[1]
                });
            } else {
                console.error('Geocode failed: ' + status);
            }
        });
        
    },

    async getCompanyAddress(branchId = null) {
        const companyIdData = await this.keepLast.add(
            this.rpc("/company/details", {'branchId': branchId})
        );
            
        if (companyIdData && companyIdData.length >= 2) {
            const address = companyIdData[0];
            const companyName = companyIdData[1];
            const companyPhone = companyIdData[2];
            
            const companyNameElement = `${companyName}<br>`;
            const companyAddressElement = `${address}`;
            const companyPhoneElement = `${companyPhone}`;
            
            const companyAddressContainer = document.getElementById('company_adress');
            if (companyAddressContainer) {
                companyAddressContainer.innerHTML = companyNameElement + companyAddressElement + companyPhoneElement;
            }
        }
        return companyIdData
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onStateChange: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var $target = $(ev.currentTarget);
        var state_country_id = $target.find('option:selected').data('country');
        var country = $(`#student_country option:selected`);
        if(state_country_id && state_country_id != country.val()){
            $(`#student_country option[value=${state_country_id}]`).attr('selected', true); 
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onCountryChange: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var $target = $(ev.currentTarget);
        var country_id = $target.find('option:selected').val()
        var state_id = $(`#student_state option:selected`);
        if(country_id && state_id.data('country') != country_id){
            $(`#student_state`).val('0'); 
        }
        if (country_id){
            var select_state = $(`#student_state`)
            select_state.empty()
            select_state.append(`<option value="0" t-att-selected="'selected'">State</option>`)
            this.rpc('/filter/state', {
                country : country_id,
            }).then((states)=> {
                states.states.forEach(state => {
                    select_state.append(`<option value=${state['id']} data-country=${state['country_id'][0]}>`+`${state['name']}`+'</option>')
                });
            });
            select_state.append(`</select>`);
        }
    }, 
    onDisabilityChange(ev) {
        const disabilitySelect = document.getElementById('disability');
        const medicalIssueField = document.getElementById('medical_issue_field');
        const medicalIssue = document.getElementById('medical_issue');
        
        if (disabilitySelect.value === 'yes') {
            medicalIssueField.style.display = 'block';
            medicalIssue.setAttribute('required', '1');
        } else {
            medicalIssueField.style.display = 'none';
            medicalIssue.removeAttribute('required');
        }
    },

    triggerFileInput: function (event) {
        document.getElementById('student_image').click();
    },

    previewImage: function (event) {
        const input = event.target;
        const reader = new FileReader();
        const imgElement = document.querySelector('.student-image');
        const svgElement = document.querySelector('.student-image-placeholder');
        reader.onload = (function (image) {
            return function (e) {
                const base64Image = e.target.result;

                if (imgElement) {
                    imgElement.src = base64Image;
                    imgElement.classList.remove('d-none');
                    svgElement.classList.add('d-none');
                }
            };
        })(input.files[0]);

        if (input.files && input.files[0]) {
            reader.readAsDataURL(input.files[0]);
        } else {
            svgElement.classList.remove('d-none');
            imgElement.classList.add('d-none');
        }
    },

    async onBranchSelection(ev){
        var $target = document.querySelector('#child_id');
        var selectedOption = $target.options[$target.selectedIndex];
        var branch_id = selectedOption.value;
        var branch_id_label = selectedOption.text;
        const branchSpan = document.getElementById('branch_name');
        if (branch_id){
            branchSpan.innerHTML = "(" + branch_id_label + ")"
            var companyInput = document.querySelector('input[name="company_id"]');
            companyInput.value = branch_id;
            this.initialize(branch_id, true);
            const data = await this.rpc("/company/branch/grades", {'branch_id':branch_id})

            const directionsLink = document.getElementById('directionBtn');
            const branchGoogleMapLink = data.google_map_link;
            if (directionsLink) {
                directionsLink.setAttribute('href', branchGoogleMapLink);
            }

            var gradeSelect = $('#grade_id');
            gradeSelect.empty();
            gradeSelect.append('<option value="">Select Grade</option>')
            data.classes.forEach(function (cls) {
                gradeSelect.append('<option value="' + cls.id + '">' + cls.name + '</option>');
            });

            var documentSection = $('.document_section');
            var documentContainer = documentSection.find('.document_class');
            documentContainer.empty();
            if (data.document_ids && data.document_ids.length > 0) {
                var documentFields = `
                    <div style="border: 1px solid #E1E7EF;border-radius:8px;background:white;box-shadow: 0px 0px 24px -4px #00000008;">
                        <div class="p-4">
                            <div style="color:#0F172A;font-family: Inter;font-size: 24px;font-weight: 600;line-height: 29.05px;">
                                Documents Upload
                                <p style="color:#f35726;font-size:medium;">
                                    (Documents should be in PDF/JPEG format)
                                </p>
                            </div>
                `;
                data.document_ids.forEach(function (doc) {
                    documentFields += `
                        <div class="row mt-1">
                            <div class="col-md-6 col-12 mb-sm-1">
                                <div class="p-2" style="border: 1px solid #E1E7EF;border-radius:5px;">
                                    ${doc.name}
                                    <span style="color:red;"> *</span>
                                </div>
                            </div>
                            <div class="col-md-6 col-12">
                                <input autocomplete="off" name="${doc.name}" required="1" type="file" class="form-control" accept=".jpeg,.pdf"/>
                            </div>
                        </div>
                    `;
                });
                documentFields += `
                        </div>
                    </div>
                `;
                documentContainer.append(documentFields);
            }
        }
        else{
            this.initialize();
            branchSpan.innerHTML = ""
        }
    },

    preventFormSubmit: function(event) {
        event.preventDefault();
        const form = event.target;
        
        const email = form.querySelector('input[name="email"]').value;
        const gradeId = form.querySelector('select[name="grade_id"]').value;
        const studentImageInput = form.querySelector('input[name="student_image"]');
        const file = studentImageInput.files[0];

        if (!file) {
            alert('Please upload a student image.');
            return;
        }
        const data = {
            email: email,
            grade_id: gradeId
        };
        this.rpc('/application/check_duplicate', data).then((result) => {
            if (result.exists) {
            const notifDiv = document.getElementById('duplicate-notification');
            if (notifDiv) {
                notifDiv.innerHTML = `
                    <div style="
                        background-color: #f8d7da;
                        color: #721c24;
                        padding: 25px 30px;
                        border-radius: 5px;
                        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
                        font-weight: 500;
                    ">
                    <span style="
                        position: absolute;
                        top: 5px;
                        right: 10px;
                        cursor: pointer;
                        font-weight: bold;
                        font-size: 20px;
                    " id="close-duplicate-notif">&times;</span>
                        You have already applied for the "${result.grade_name}" using this email address.
                        <br>If you have any questions or would like to notify us of any changes, please contact us.
                    </div>
                `;
                notifDiv.style.display = 'block';
                const closeBtn = document.getElementById('close-duplicate-notif');
                if (closeBtn) {
                    closeBtn.addEventListener('click', () => {
                        notifDiv.style.display = 'none';
                        notifDiv.innerHTML = '';
                    });
                }
                setTimeout(() => {
                    notifDiv.style.display = 'none';
                    notifDiv.innerHTML = '';
                }, 10000);
            }
        }else {
                form.submit();
            }
        }).catch((err) => {
            console.error('Error during duplicate check:', err);
        });
    }
})
