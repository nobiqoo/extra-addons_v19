# -*- coding: utf-8 -*-
from . import hr_payslip_noveltys
from . import hr_payslip_period

from . import res_partner
from . import hr_employee
from . import hr_employee_public


from . import hr_contract

from . import hr_payslip
# hr_embargo extends hr.concept (models/hr_concept/), which is only pulled in
# transitively by hr_payslip's cross-import above; it must be imported after it
# so hr.concept's base class registers before hr_concept_embargo's extension.
from . import hr_embargo
from . import ir_module_module

from . import economic_variables

from . import res_config_settings

from . import hr_contribution_form

from . import res_company

from . import hr_days_off

from . import income_and_withholding_certificate

from . import hr_family_information
from . import hr_employee_medical_exam
from . import hr_personal_reference

from . import hr_payslip_report
