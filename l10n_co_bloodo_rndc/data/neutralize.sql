-- neutralize connection to production environment to RNDC
UPDATE res_company
SET rndc_env_id = '2';