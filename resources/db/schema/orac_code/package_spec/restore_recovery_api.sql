--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_restore_recovery_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-23
-- __description__: controlled post-restore recovery safety API

create or replace package orac_code.restore_recovery_api as
  procedure quarantine_plugin_state;
end restore_recovery_api;
/

--rollback drop package orac_code.restore_recovery_api;
