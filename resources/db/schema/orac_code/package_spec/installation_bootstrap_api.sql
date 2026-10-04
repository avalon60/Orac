--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_installation_bootstrap_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-10-03
-- __description__: provision reserved and installer-derived Orac principals

create or replace package orac_code.installation_bootstrap_api as
  gc_system_username constant varchar2(100) := 'system';

  procedure ensure_principals(
    p_installer_username in varchar2,
    p_user_created       out varchar2
  );
end installation_bootstrap_api;
/

--rollback drop package orac_code.installation_bootstrap_api;
