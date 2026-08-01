--liquibase formatted sql

--changeset clive:seed_knowledge_tags context:core labels:core stripComments:false splitStatements:false endDelimiter:/
declare
  procedure seed_tag(p_code varchar2, p_name varchar2, p_description varchar2, p_sort number) is
  begin
    merge into orac_core.knowledge_tags dst
    using (select p_code tag_code, p_name display_name, p_description description, p_sort sort_order from dual) src
       on (dst.tag_code = src.tag_code)
     when matched then update set dst.display_name = src.display_name,
       dst.description = src.description, dst.sort_order = src.sort_order,
       dst.active_yn = 'Y', dst.system_yn = 'Y'
     when not matched then insert
       (tag_code, display_name, description, active_yn, system_yn, sort_order)
       values (src.tag_code, src.display_name, src.description, 'Y', 'Y', src.sort_order);
  end;
begin
  seed_tag('raw_reference', 'Raw Reference', 'Untransformed reference material.', 10);
  seed_tag('concise_knowledge_note', 'Concise Knowledge Note', 'Classification for concise knowledge notes.', 20);
  seed_tag('implementation_decision_record', 'Implementation Decision Record', 'Classification for implementation decisions.', 30);
  seed_tag('technical_manual', 'Technical Manual', 'Classification for technical manuals.', 40);
  seed_tag('troubleshooting_note', 'Troubleshooting Note', 'Classification for troubleshooting material.', 50);
  seed_tag('automation_rule_note', 'Automation Rule Note', 'Classification for automation-rule material.', 60);

  insert into orac_core.knowledge_tags
    (tag_code, display_name, description, active_yn, system_yn, sort_order)
  select distinct req.processing_profile_code,
         'Legacy Classification: ' || req.processing_profile_code,
         'Inactive historical classification retained for provenance.',
         'N', 'N', 1000
    from orac_core.knowledge_ingestion_requests req
   where req.processing_profile_code is not null
     and regexp_like(req.processing_profile_code, '^[a-z][a-z0-9_]{1,99}$')
     and not exists (
       select 1 from orac_core.knowledge_tags tag
        where tag.tag_code = req.processing_profile_code
     );

  insert into orac_core.knowledge_document_version_tags
    (document_version_id, knowledge_tag_id, tag_order)
  select req.document_version_id, tag.knowledge_tag_id, 1
    from orac_core.knowledge_ingestion_requests req
    join orac_core.knowledge_tags tag
      on tag.tag_code = req.processing_profile_code
   where not exists (
     select 1 from orac_core.knowledge_document_version_tags link
      where link.document_version_id = req.document_version_id
        and link.knowledge_tag_id = tag.knowledge_tag_id
   );
end;
/
--rollback select 1 from dual;
