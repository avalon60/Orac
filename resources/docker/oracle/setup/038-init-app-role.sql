-- Author: Clive Bostock
--   Date: 15 Mar 2026
--
-- Orac script to add ADMINISTRATOR role etc. for the ORAC_ADMIN user.
--
-- 038-init-app-role.sql
begin
    -- 1. Tell APEX which workspace you are working in
    -- Use 'ORAC' (based on your footer in the first screenshot)
    apex_util.set_workspace(p_workspace => 'ORAC'); 

    -- 2. Grant the role
    apex_acl.add_user_role (
        p_application_id => 1042,
        p_user_name      => 'ORAC_ADMIN',
        p_role_static_id => 'ADMINISTRATOR'
    );


    apex_acl.add_user_role (
        p_application_id => 1042,
        p_user_name      => 'ORAC_ADMIN',
        p_role_static_id => 'CONTRIBUTOR'
    );


    apex_acl.add_user_role (
        p_application_id => 1042,
        p_user_name      => 'ORAC_ADMIN',
        p_role_static_id => 'READER'
    );

    commit;
end;
/
