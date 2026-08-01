--liquibase formatted sql

--changeset clive:add_plugin_registry_command_dependencies context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner = 'ORAC_CORE' and table_name = 'PLUGIN_REGISTRY' and column_name = 'COMMAND_PREREQUISITE_STATUS';
alter table orac_core.plugin_registry add (
  command_dependency_declarations json,
  command_dependency_fingerprint varchar2(64 char)
    default 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' not null,
  command_prerequisite_status varchar2(64 char)
    default 'not_applicable' not null,
  command_dependency_report json
);
--rollback alter table orac_core.plugin_registry drop (command_dependency_declarations, command_dependency_fingerprint, command_prerequisite_status, command_dependency_report);

--changeset clive:add_plugin_registry_command_status_check context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLGREG_CMDSTS_CK';
alter table orac_core.plugin_registry add constraint plgreg_cmdsts_ck check (
  command_prerequisite_status in (
    'not_applicable', 'success', 'degraded', 'failed', 'not_run'
  )
);
--rollback alter table orac_core.plugin_registry drop constraint plgreg_cmdsts_ck;
