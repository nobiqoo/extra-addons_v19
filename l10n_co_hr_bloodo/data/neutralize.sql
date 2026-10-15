-- neutralize connection to production environment to ei and sd
UPDATE res_company
SET hr_target_environment = '2';