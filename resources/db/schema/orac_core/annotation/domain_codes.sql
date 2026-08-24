--liquibase formatted sql

--changeset clive:annotate_orac_core_domain_codes context:core labels:core stripComments:false runOnChange:true
alter table orac_core.domain_codes annotations (
  add if not exists display_name 'Reference-data domain',
  add if not exists plural_display_name 'Reference-data domains'
);

--changeset clive:annotate_orac_core_domain_codes_domain_code context:core labels:core stripComments:false runOnChange:true
alter table orac_core.domain_codes modify domain_code annotations (
  add if not exists display_name 'Domain code',
  add if not exists semantic_role 'primary_key',
  add if not exists data_kind 'code'
);

--changeset clive:annotate_orac_core_domain_codes_display_name context:core labels:core stripComments:false runOnChange:true
alter table orac_core.domain_codes modify display_name annotations (
  add if not exists display_name 'Display name',
  add if not exists data_kind 'text'
);
