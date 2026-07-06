--liquibase formatted sql

--changeset clive:grant_orac_code_plugin_service_api_to_orac context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: allow Orac runtime to manage plugin service lifecycle through code API

grant execute on orac_code.plugin_service_api to orac;

--rollback revoke execute on orac_code.plugin_service_api from orac;

--changeset clive:grant_orac_code_plugin_service_status_v_to_orac context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.plugin_service_status_v to orac;

--rollback revoke read on orac_code.plugin_service_status_v from orac;
