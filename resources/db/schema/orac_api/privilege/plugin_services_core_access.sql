--liquibase formatted sql

--changeset clive:grant_orac_core_plugin_services_to_orac_api context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: grant API schema controlled access to plugin service lifecycle state

grant select, insert, update, delete on orac_core.plugin_services to orac_api with grant option;

--rollback revoke select, insert, update, delete on orac_core.plugin_services from orac_api;
