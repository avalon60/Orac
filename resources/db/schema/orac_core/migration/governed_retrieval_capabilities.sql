--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 29-Aug-2026
-- Description: Registers Phase 2A capability definitions without granting model evidence.

--changeset clive:seed_orac_core_governed_retrieval_capabilities_p2a context:core labels:core stripComments:false splitStatements:false endDelimiter:/
declare
  procedure seed_capability(
    p_capability_code in varchar2,
    p_display_name in varchar2,
    p_behaviour_summary in varchar2
  )
  is
  begin
    merge into orac_core.llm_capabilities dst
    using (
      select p_capability_code capability_code,
             p_display_name display_name,
             p_behaviour_summary behaviour_summary
        from dual
    ) src
       on (dst.capability_code = src.capability_code)
     when matched then update
          set dst.display_name = src.display_name,
              dst.capability_class_ref_value_code = 'DETERMINISTIC_INSPECTION',
              dst.capability_lifecycle_ref_value_code = 'DEFINED',
              dst.behaviour_summary = src.behaviour_summary
     when not matched then insert (
          capability_code, display_name,
          capability_class_ref_value_code,
          capability_lifecycle_ref_value_code,
          behaviour_summary
     ) values (
          src.capability_code, src.display_name,
          'DETERMINISTIC_INSPECTION', 'DEFINED', src.behaviour_summary
     );
  end seed_capability;
begin
  seed_capability(
    'structured_tool_calling',
    'Structured Tool Calling',
    'Emits schema-conforming structured tool calls through the provider adapter.'
  );
  seed_capability(
    'streamed_structured_tool_calling',
    'Streamed Structured Tool Calling',
    'Emits validated incremental structured tool frames while preserving assistant streaming.'
  );
end;
/
--rollback update orac_core.llm_capabilities set capability_lifecycle_ref_value_code = 'DEPRECATED' where capability_code in ('structured_tool_calling', 'streamed_structured_tool_calling');
