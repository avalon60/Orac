--liquibase formatted sql

--changeset clive:grant_orac_code_pref_value_type_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.pref_value_type_v to orac_apx_pub;
--rollback revoke read on orac_code.pref_value_type_v from orac_apx_pub;

--changeset clive:grant_orac_code_pref_value_type_lov_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.pref_value_type_lov_v to orac_apx_pub;
--rollback revoke read on orac_code.pref_value_type_lov_v from orac_apx_pub;

--changeset clive:grant_orac_code_pref_control_type_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.pref_control_type_v to orac_apx_pub;
--rollback revoke read on orac_code.pref_control_type_v from orac_apx_pub;

--changeset clive:grant_orac_code_pref_control_type_lov_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.pref_control_type_lov_v to orac_apx_pub;
--rollback revoke read on orac_code.pref_control_type_lov_v from orac_apx_pub;

--changeset clive:grant_orac_code_pref_lov_type_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.pref_lov_type_v to orac_apx_pub;
--rollback revoke read on orac_code.pref_lov_type_v from orac_apx_pub;

--changeset clive:grant_orac_code_pref_lov_type_lov_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.pref_lov_type_lov_v to orac_apx_pub;
--rollback revoke read on orac_code.pref_lov_type_lov_v from orac_apx_pub;

--changeset clive:grant_orac_code_llm_context_policy_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.llm_context_policy_v to orac_apx_pub;
--rollback revoke read on orac_code.llm_context_policy_v from orac_apx_pub;

--changeset clive:grant_orac_code_llm_context_policy_lov_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.llm_context_policy_lov_v to orac_apx_pub;
--rollback revoke read on orac_code.llm_context_policy_lov_v from orac_apx_pub;

--changeset clive:grant_orac_code_user_alias_type_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.user_alias_type_v to orac_apx_pub;
--rollback revoke read on orac_code.user_alias_type_v from orac_apx_pub;

--changeset clive:grant_orac_code_user_alias_type_lov_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.user_alias_type_lov_v to orac_apx_pub;
--rollback revoke read on orac_code.user_alias_type_lov_v from orac_apx_pub;
