--liquibase formatted sql

--changeset clive:grant_orac_api_plugin_services_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: allow code schema to manage plugin service lifecycle through API layer

grant select, insert, update, delete on orac_api.plugin_services_v to orac_code with grant option;

--rollback revoke select, insert, update, delete on orac_api.plugin_services_v from orac_code;

--changeset clive:grant_orac_api_plugin_services_tapi_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.plugin_services_tapi to orac_code;

--rollback revoke execute on orac_api.plugin_services_tapi from orac_code;
