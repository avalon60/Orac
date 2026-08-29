--liquibase formatted sql
--changeset clive:create_trigger_orac_core_conv_sumchk_immutable context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.conv_sumchk_immutable
before update on orac_core.conversation_summary_checkpoints
begin
  raise_application_error(-20071, 'Completed conversation checkpoints are immutable.');
end;
/
--rollback drop trigger orac_core.conv_sumchk_immutable;
