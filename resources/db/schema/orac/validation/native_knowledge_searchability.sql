--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Sep-2026
-- Description: Rejects installed states whose native-ready requests report non-searchable.

--changeset clive:validate_native_knowledge_searchability context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runAlways:true
declare
  l_violation_count number;
begin
  select count(*)
    into l_violation_count
    from (
      select content.ingestion_request_id
        from orac_code.knowledge_searchable_chunk_content_v content
        left join orac_code.knowledge_native_searchable_chunks_v native
          on native.chunk_id = content.chunk_id
         and native.ingestion_request_id = content.ingestion_request_id
       group by content.ingestion_request_id
      having count(*) > 0
         and count(*) = count(native.chunk_vector_embedding_id)
    ) native_ready
    join orac_code.knowledge_ingestion_requests_v report
      on report.ingestion_request_id = native_ready.ingestion_request_id
   where report.status_code = 'COMPLETED'
     and report.searchable_yn <> 'Y';

  if l_violation_count <> 0
  then
    raise_application_error(
      -20992,
      'NATIVE_READY_KNOWLEDGE_REQUEST_REPORTED_NON_SEARCHABLE'
    );
  end if;
end;
/
