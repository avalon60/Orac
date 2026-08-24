--liquibase formatted sql

--changeset clive:grant_read_timezone_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-08
-- __description__: expose timezone semantics to the APEX access schema

grant read on orac_code.timezone_v to orac_apx_pub;

--rollback revoke read on orac_code.timezone_v from orac_apx_pub;

--changeset clive:grant_read_timezone_lov_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-08
-- __description__: expose active timezone selector values to the APEX access schema

grant read on orac_code.timezone_lov_v to orac_apx_pub;

--rollback revoke read on orac_code.timezone_lov_v from orac_apx_pub;
