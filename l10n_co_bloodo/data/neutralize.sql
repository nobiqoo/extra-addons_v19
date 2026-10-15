-- neutralize connection to production environment to ei and sd
UPDATE res_company
SET target_environment_id = '2',
    ds_target_environment_id = '2';