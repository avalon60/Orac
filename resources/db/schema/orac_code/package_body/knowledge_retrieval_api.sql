--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Implements scope-authorised, audited retrieval descriptor and chunk access.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_body_orac_code_knowledge_retrieval_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.knowledge_retrieval_api
as
  c_max_request_bytes constant pls_integer := 65536;
  c_max_candidates    constant pls_integer := 1000;
  c_max_legacy_chars  constant pls_integer := 2097152;
  c_max_chunk_chars   constant pls_integer := 1048576;
  c_max_metadata_chars constant pls_integer := 262144;
  c_max_member_metadata_chars constant pls_integer := 65536;

  procedure empty_cursor(p_rows out sys_refcursor)
  is
  begin
    open p_rows for
      select cast(null as varchar2(20)) row_kind
        from dual
       where 1 = 0;
  end empty_cursor;

  function resolution_json(
    p_retrieval_id in varchar2,
    p_status       in varchar2,
    p_reason_code  in varchar2,
    p_operation    in varchar2,
    p_target_type  in varchar2 default null,
    p_target_id    in number default null,
    p_member_count in number default null,
    p_chunk_count  in number default null
  ) return clob
  is
    l_result clob;
  begin
    select json_object(
             'schema_version' value 1,
             'retrieval_id' value p_retrieval_id,
             'status' value p_status,
             'reason_code' value p_reason_code,
             'operation' value p_operation,
             'target' value json_object(
               'type' value p_target_type,
               'id' value p_target_id
             ),
             'member_count' value p_member_count,
             'chunk_count' value p_chunk_count
             absent on null
             returning clob
           )
      into l_result
      from dual;
    return l_result;
  end resolution_json;

  procedure write_event(
    p_retrieval_id       in varchar2,
    p_event_type         in varchar2,
    p_username           in varchar2,
    p_user_id            in number,
    p_scope_id           in number,
    p_operation          in varchar2,
    p_target_type        in varchar2,
    p_target_id          in number,
    p_status             in varchar2,
    p_reason_code        in varchar2,
    p_expected_byte_size in number default null,
    p_returned_byte_size in number default null,
    p_returned_sha256    in varchar2 default null,
    p_member_count       in number default null,
    p_chunk_count        in number default null,
    p_duration_ms        in number default null,
    p_detail_json        in json default null
  )
  is
    pragma autonomous_transaction;
    l_row orac_api.knowledge_retrieval_events_v%rowtype;
  begin
    l_row.retrieval_id := lower(trim(p_retrieval_id));
    l_row.event_type_code := p_event_type;
    l_row.username_snapshot := substr(coalesce(trim(p_username), '<unknown>'), 1, 128);
    l_row.user_id := p_user_id;
    l_row.knowledge_scope_id := p_scope_id;
    l_row.operation_code := p_operation;
    l_row.target_type_code := p_target_type;
    l_row.target_id := p_target_id;
    l_row.status_code := p_status;
    l_row.reason_code := p_reason_code;
    l_row.expected_byte_size := p_expected_byte_size;
    l_row.returned_byte_size := p_returned_byte_size;
    l_row.returned_sha256 := p_returned_sha256;
    l_row.member_count := p_member_count;
    l_row.chunk_count := p_chunk_count;
    l_row.duration_ms := p_duration_ms;
    l_row.detail_json := p_detail_json;
    orac_api.knowledge_retrieval_events_tapi.ins(l_row);
    commit;
  exception
    when others then
      rollback;
      raise_application_error(-20631, 'RETRIEVAL_AUDIT_UNAVAILABLE');
  end write_event;

  procedure resolve_identity(
    p_username   in  varchar2,
    p_scope_type in  varchar2,
    p_scope_key  in  varchar2,
    p_user_id    out number,
    p_scope_id   out number,
    p_authorized out varchar2
  )
  is
  begin
    p_user_id := null;
    p_scope_id := orac_code.knowledge_scope_api.resolve_scope_id(
                    p_scope_type, p_scope_key
                  );
    begin
      select user_id
        into p_user_id
        from orac_api.users_v
       where username = trim(p_username);
    exception
      when no_data_found then
        p_user_id := null;
    end;
    p_authorized := orac_code.rag_usage_authorization_api.authorization_result_by_id(
                      p_username, p_scope_id
                    );
  end resolve_identity;

  procedure resolve_request(
    p_retrieval_id    in  varchar2,
    p_username        in  varchar2,
    p_scope_type      in  varchar2,
    p_scope_key       in  varchar2,
    p_request_json    in  clob,
    p_resolution_json out clob,
    p_content_rows    out sys_refcursor
  )
  is
    l_operation        varchar2(30);
    l_target_type      varchar2(30);
    l_selection_type   varchar2(30);
    l_include_raw_metadata varchar2(5);
    l_target_id        number;
    l_user_id          number;
    l_scope_id         number;
    l_authorized       varchar2(100);
    l_target_count     number;
    l_extraction_count number;
    l_member_count     number;
    l_expected_size    number;
    l_legacy_chars     number;
    l_metadata_chars   number;
    l_max_metadata_chars number;
    l_first_chunk_id   number;
    l_last_chunk_id    number;
    l_chunk_set_id     number;
    l_first_chunk_no   number;
    l_last_chunk_no    number;
    l_context_before   number;
    l_context_after    number;
    l_max_chunk_no     number;
    l_chunk_count      number;
    l_chunk_chars      number;
  begin
    if not regexp_like(
         lower(trim(p_retrieval_id)),
         '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
       )
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;
    if p_request_json is null or dbms_lob.getlength(p_request_json) > c_max_request_bytes
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    l_operation := json_value(
      p_request_json, '$.operation' returning varchar2(30) error on error
    );
    l_target_type := json_value(
      p_request_json, '$.target.type' returning varchar2(30) error on error
    );
    l_target_id := json_value(
      p_request_json, '$.target.id' returning number error on error
    );
    l_selection_type := json_value(
      p_request_json, '$.selection.type' returning varchar2(30) error on error
    );
    l_include_raw_metadata := lower(coalesce(json_value(
      p_request_json, '$.include_raw_metadata'
      returning varchar2(5) default 'false' on empty error on error
    ), 'false'));
    if json_value(p_request_json, '$.schema_version' returning number error on error) <> 1
       or l_operation not in ('METADATA', 'CONTENT')
       or l_target_type not in (
         'DOCUMENT', 'DOCUMENT_VERSION', 'EXTRACTION', 'ARTEFACT', 'CHUNK_SET'
       )
       or l_target_id <= 0
       or l_selection_type not in (
         'COMPLETE', 'MEMBERS', 'MEMBER_RANGE', 'TEXT_RANGE',
         'CHUNK_RANGE', 'CHUNK_CONTEXT', 'SECTION_RANGE', 'TABLE_RANGE'
       )
       or (l_target_type = 'CHUNK_SET'
           and l_selection_type not in ('CHUNK_RANGE', 'CHUNK_CONTEXT', 'SECTION_RANGE'))
       or (l_selection_type in ('CHUNK_RANGE', 'CHUNK_CONTEXT', 'SECTION_RANGE')
           and l_target_type <> 'CHUNK_SET')
       or (l_selection_type in ('TEXT_RANGE', 'TABLE_RANGE')
           and l_target_type <> 'ARTEFACT')
       or (l_selection_type in ('MEMBERS', 'MEMBER_RANGE')
           and l_target_type not in ('DOCUMENT', 'DOCUMENT_VERSION', 'EXTRACTION'))
       or l_include_raw_metadata not in ('true', 'false')
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    resolve_identity(
      p_username, p_scope_type, p_scope_key,
      l_user_id, l_scope_id, l_authorized
    );
    if l_authorized <> 'RAG_USAGE_GRANTED'
    then
      write_event(
        p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
        l_operation, l_target_type, l_target_id, 'REJECTED', l_authorized
      );
      p_resolution_json := resolution_json(
        p_retrieval_id, 'REJECTED', 'RETRIEVAL_NOT_AUTHORISED',
        l_operation, l_target_type, l_target_id
      );
      empty_cursor(p_content_rows);
      return;
    end if;

    select count(distinct case l_target_type
             when 'DOCUMENT' then member.document_id
             when 'DOCUMENT_VERSION' then member.document_version_id
             when 'EXTRACTION' then member.extraction_id
             when 'ARTEFACT' then member.artefact_id
             when 'CHUNK_SET' then chunk_set.chunk_set_id
           end),
           count(distinct case when member.retrieval_eligible_yn = 'Y'
                               then member.extraction_id end),
           count(distinct member.artefact_id),
           sum(case when member.artefact_id is not null
                    then member.artefact_byte_size else 0 end),
           sum(case when member.artefact_id is null
                    then dbms_lob.getlength(member.legacy_extracted_text)
                    else 0 end),
           sum(coalesce(dbms_lob.getlength(json_serialize(
                 member.artefact_metadata_json returning clob
               )), 0)
               + case when l_include_raw_metadata = 'true'
                      then coalesce(dbms_lob.getlength(json_serialize(
                             member.extractor_metadata_json returning clob
                           )), 0)
                      else 0 end),
           max(greatest(
                 coalesce(dbms_lob.getlength(json_serialize(
                   member.artefact_metadata_json returning clob
                 )), 0),
                 case when l_include_raw_metadata = 'true'
                      then coalesce(dbms_lob.getlength(json_serialize(
                             member.extractor_metadata_json returning clob
                           )), 0)
                      else 0 end
               ))
      into l_target_count, l_extraction_count, l_member_count, l_expected_size,
           l_legacy_chars, l_metadata_chars, l_max_metadata_chars
      from orac_code.knowledge_retrieval_members_v member
      left join orac_api.knowledge_chunk_sets_v chunk_set
        on chunk_set.extraction_id = member.extraction_id
     where member.knowledge_scope_id = l_scope_id
       and (
         (l_target_type = 'DOCUMENT'
          and member.document_id = l_target_id
          and member.document_version_id = member.current_document_version_id)
         or (l_target_type = 'DOCUMENT_VERSION'
             and member.document_version_id = l_target_id)
         or (l_target_type = 'EXTRACTION' and member.extraction_id = l_target_id)
         or (l_target_type = 'ARTEFACT' and member.artefact_id = l_target_id)
         or (l_target_type = 'CHUNK_SET' and chunk_set.chunk_set_id = l_target_id)
       );

    if l_target_count = 0
    then
      write_event(
        p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
        l_operation, l_target_type, l_target_id, 'REJECTED',
        'RETRIEVAL_TARGET_NOT_FOUND'
      );
      p_resolution_json := resolution_json(
        p_retrieval_id, 'REJECTED', 'RETRIEVAL_TARGET_NOT_FOUND',
        l_operation, l_target_type, l_target_id
      );
      empty_cursor(p_content_rows);
      return;
    end if;
    if l_operation = 'CONTENT' and l_extraction_count = 0
    then
      write_event(
        p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
        l_operation, l_target_type, l_target_id, 'REJECTED',
        'RETRIEVAL_REPRESENTATION_UNAVAILABLE'
      );
      p_resolution_json := resolution_json(
        p_retrieval_id, 'REJECTED', 'RETRIEVAL_REPRESENTATION_UNAVAILABLE',
        l_operation, l_target_type, l_target_id
      );
      empty_cursor(p_content_rows);
      return;
    end if;
    if coalesce(l_metadata_chars, 0) > c_max_metadata_chars
       or coalesce(l_max_metadata_chars, 0) > c_max_member_metadata_chars
       or (l_operation = 'CONTENT'
           and coalesce(l_legacy_chars, 0) > c_max_legacy_chars)
    then
      write_event(
        p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
        l_operation, l_target_type, l_target_id, 'REJECTED',
        'RETRIEVAL_LIMIT_EXCEEDED'
      );
      p_resolution_json := resolution_json(
        p_retrieval_id, 'REJECTED', 'RETRIEVAL_LIMIT_EXCEEDED',
        l_operation, l_target_type, l_target_id
      );
      empty_cursor(p_content_rows);
      return;
    end if;
    if l_operation = 'CONTENT'
       and l_target_type in ('DOCUMENT', 'DOCUMENT_VERSION')
       and l_extraction_count > 1
    then
      write_event(
        p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
        l_operation, l_target_type, l_target_id, 'REJECTED',
        'RETRIEVAL_TARGET_AMBIGUOUS'
      );
      p_resolution_json := resolution_json(
        p_retrieval_id, 'REJECTED', 'RETRIEVAL_TARGET_AMBIGUOUS',
        l_operation, l_target_type, l_target_id
      );
      empty_cursor(p_content_rows);
      return;
    end if;

    if l_selection_type in ('CHUNK_RANGE', 'CHUNK_CONTEXT', 'SECTION_RANGE')
    then
      if l_selection_type = 'CHUNK_CONTEXT'
      then
        l_first_chunk_id := json_value(
          p_request_json, '$.selection.first_anchor_chunk_id'
          returning number error on error
        );
        l_last_chunk_id := json_value(
          p_request_json, '$.selection.last_anchor_chunk_id'
          returning number error on error
        );
        l_context_before := json_value(
          p_request_json, '$.selection.context_before'
          returning number default 0 on empty error on error
        );
        l_context_after := json_value(
          p_request_json, '$.selection.context_after'
          returning number default 0 on empty error on error
        );
      else
        l_first_chunk_id := json_value(
          p_request_json, '$.selection.first_chunk_id'
          returning number error on error
        );
        l_last_chunk_id := json_value(
          p_request_json, '$.selection.last_chunk_id'
          returning number error on error
        );
        l_context_before := 0;
        l_context_after := 0;
      end if;
      select min(chunk_set.chunk_set_id),
             min(case when chunk.chunk_id = l_first_chunk_id
                      then chunk.chunk_no end),
             min(case when chunk.chunk_id = l_last_chunk_id
                      then chunk.chunk_no end),
             count(distinct chunk_set.chunk_set_id)
        into l_chunk_set_id, l_first_chunk_no, l_last_chunk_no, l_chunk_count
        from orac_code.knowledge_retrieval_members_v member
        join orac_api.knowledge_chunk_sets_v chunk_set
          on chunk_set.extraction_id = member.extraction_id
         and (
           chunk_set.source_artefact_id = member.artefact_id
           or (chunk_set.source_artefact_id is null and member.artefact_id is null)
         )
        join orac_api.knowledge_chunks_v chunk
          on chunk.chunk_set_id = chunk_set.chunk_set_id
       where member.knowledge_scope_id = l_scope_id
         and member.retrieval_eligible_yn = 'Y'
         and chunk.chunk_id in (l_first_chunk_id, l_last_chunk_id)
         and (
           (l_target_type = 'DOCUMENT'
            and member.document_id = l_target_id
            and member.document_version_id = member.current_document_version_id)
           or (l_target_type = 'DOCUMENT_VERSION'
               and member.document_version_id = l_target_id)
           or (l_target_type = 'EXTRACTION' and member.extraction_id = l_target_id)
           or (l_target_type = 'ARTEFACT' and member.artefact_id = l_target_id)
           or (l_target_type = 'CHUNK_SET' and chunk_set.chunk_set_id = l_target_id)
         );
      if l_first_chunk_id is null
         or l_last_chunk_id is null
         or l_chunk_count <> 1
         or l_first_chunk_no is null
         or l_last_chunk_no is null
         or l_last_chunk_no < l_first_chunk_no
         or l_context_before not between 0 and 8
         or l_context_after not between 0 and 8
      then
        write_event(
          p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
          l_operation, l_target_type, l_target_id, 'REJECTED',
          'RETRIEVAL_RANGE_INVALID'
        );
        p_resolution_json := resolution_json(
          p_retrieval_id, 'REJECTED', 'RETRIEVAL_RANGE_INVALID',
          l_operation, l_target_type, l_target_id
        );
        empty_cursor(p_content_rows);
        return;
      end if;
      select max(chunk.chunk_no)
        into l_max_chunk_no
        from orac_api.knowledge_chunks_v chunk
       where chunk.chunk_set_id = l_chunk_set_id;
      l_first_chunk_no := greatest(1, l_first_chunk_no - l_context_before);
      l_last_chunk_no := least(l_max_chunk_no, l_last_chunk_no + l_context_after);
      if l_last_chunk_no - l_first_chunk_no + 1 > 64
      then
        write_event(
          p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
          l_operation, l_target_type, l_target_id, 'REJECTED',
          'RETRIEVAL_LIMIT_EXCEEDED'
        );
        p_resolution_json := resolution_json(
          p_retrieval_id, 'REJECTED', 'RETRIEVAL_LIMIT_EXCEEDED',
          l_operation, l_target_type, l_target_id
        );
        empty_cursor(p_content_rows);
        return;
      end if;
      select count(*),
             sum(coalesce(dbms_lob.getlength(chunk.chunk_text), 0))
        into l_chunk_count, l_chunk_chars
        from orac_api.knowledge_chunks_v chunk
       where chunk.chunk_set_id = l_chunk_set_id
         and chunk.chunk_no between l_first_chunk_no and l_last_chunk_no;
      if l_chunk_count <> l_last_chunk_no - l_first_chunk_no + 1
      then
        write_event(
          p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
          l_operation, l_target_type, l_target_id, 'REJECTED',
          'RETRIEVAL_RANGE_INVALID'
        );
        p_resolution_json := resolution_json(
          p_retrieval_id, 'REJECTED', 'RETRIEVAL_RANGE_INVALID',
          l_operation, l_target_type, l_target_id
        );
        empty_cursor(p_content_rows);
        return;
      end if;
      if l_operation = 'CONTENT'
         and l_selection_type = 'CHUNK_RANGE'
         and coalesce(l_chunk_chars, 0) > c_max_chunk_chars
      then
        write_event(
          p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
          l_operation, l_target_type, l_target_id, 'REJECTED',
          'RETRIEVAL_LIMIT_EXCEEDED'
        );
        p_resolution_json := resolution_json(
          p_retrieval_id, 'REJECTED', 'RETRIEVAL_LIMIT_EXCEEDED',
          l_operation, l_target_type, l_target_id
        );
        empty_cursor(p_content_rows);
        return;
      end if;
    end if;

    write_event(
      p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
      l_operation, l_target_type, l_target_id, 'APPROVED',
      'RETRIEVAL_APPROVED', l_expected_size, null, null,
      l_member_count, null
    );
    p_resolution_json := resolution_json(
      p_retrieval_id, 'APPROVED', 'RETRIEVAL_APPROVED',
      l_operation, l_target_type, l_target_id, l_member_count
    );

    if l_selection_type in ('CHUNK_RANGE', 'CHUNK_CONTEXT', 'SECTION_RANGE')
       or l_target_type = 'CHUNK_SET'
    then
      open p_content_rows for
        select 'CHUNK' row_kind,
               member.knowledge_scope_id,
               member.target_scope_type,
               member.target_scope_key,
               member.source_object_id,
               member.source_type,
               member.source_reference,
               member.parent_source_reference,
               member.document_id,
               member.document_title,
               member.document_version_id,
               member.revision_content_sha256,
               member.revision_mime_type,
               case when l_include_raw_metadata = 'true'
                    then member.original_filename end original_filename,
               member.revision_byte_size,
               member.source_format_code,
               member.extraction_id,
               member.normalised_text_sha256,
               member.output_mime_type,
               member.extractor_code,
               member.extractor_version,
               case when l_include_raw_metadata = 'true'
                    then member.extractor_metadata_json end extractor_metadata_json,
               case when l_operation = 'CONTENT' and chunk_set.source_artefact_id is null
                    then member.legacy_extracted_text end legacy_extracted_text,
               member.output_set_complete_yn,
               member.artefact_id,
               member.artefact_role_code,
               member.artefact_media_type,
               member.artefact_content_sha256,
               case when l_operation = 'CONTENT'
                    then member.artefact_storage_key end artefact_storage_key,
               member.artefact_byte_size,
               member.artefact_logical_name,
               member.member_ordinal,
               member.artefact_metadata_json,
               member.classification_tags_json,
               chunk_set.chunk_set_id,
               chunk.chunk_id,
               chunk.chunk_no,
               chunk.span_start,
               chunk.span_end,
               chunk.content_sha256 chunk_content_sha256,
               case when l_operation = 'CONTENT'
                          and l_selection_type = 'CHUNK_RANGE'
                    then chunk.chunk_text end chunk_text,
               chunk.chunk_metadata_json
          from orac_code.knowledge_retrieval_members_v member
          join orac_api.knowledge_chunk_sets_v chunk_set
            on chunk_set.extraction_id = member.extraction_id
           and (
             chunk_set.source_artefact_id = member.artefact_id
             or (chunk_set.source_artefact_id is null and member.artefact_id is null)
           )
          join orac_api.knowledge_chunks_v chunk
            on chunk.chunk_set_id = chunk_set.chunk_set_id
         where member.knowledge_scope_id = l_scope_id
           and member.retrieval_eligible_yn = 'Y'
           and (
             (l_target_type = 'DOCUMENT'
              and member.document_id = l_target_id
              and member.document_version_id = member.current_document_version_id)
             or (l_target_type = 'DOCUMENT_VERSION'
                 and member.document_version_id = l_target_id)
             or (l_target_type = 'EXTRACTION' and member.extraction_id = l_target_id)
             or (l_target_type = 'ARTEFACT' and member.artefact_id = l_target_id)
             or (l_target_type = 'CHUNK_SET' and chunk_set.chunk_set_id = l_target_id)
           )
           and (
             l_selection_type not in ('CHUNK_RANGE', 'CHUNK_CONTEXT', 'SECTION_RANGE')
             or (
               chunk_set.chunk_set_id = l_chunk_set_id
               and chunk.chunk_no between l_first_chunk_no and l_last_chunk_no
             )
           )
         order by chunk.chunk_no;
    else
      open p_content_rows for
        select 'MEMBER' row_kind,
               member.knowledge_scope_id,
               member.target_scope_type,
               member.target_scope_key,
               member.source_object_id,
               member.source_type,
               member.source_reference,
               member.parent_source_reference,
               member.document_id,
               member.document_title,
               member.document_version_id,
               member.revision_content_sha256,
               member.revision_mime_type,
               case when l_include_raw_metadata = 'true'
                    then member.original_filename end original_filename,
               member.revision_byte_size,
               member.source_modified_on,
               member.source_format_code,
               member.extraction_id,
               member.normalised_text_sha256,
               member.output_mime_type,
               member.extractor_code,
               member.extractor_version,
               case when l_include_raw_metadata = 'true'
                    then member.extractor_metadata_json end extractor_metadata_json,
               case when l_operation = 'CONTENT' and member.artefact_id is null
                    then member.legacy_extracted_text end legacy_extracted_text,
               member.output_member_count,
               member.output_set_complete_yn,
               member.artefact_id,
               member.artefact_role_code,
               member.artefact_media_type,
               member.artefact_content_sha256,
               case when l_operation = 'CONTENT'
                    then member.artefact_storage_key end artefact_storage_key,
               member.artefact_byte_size,
               member.artefact_logical_name,
               member.member_ordinal,
               member.artefact_metadata_json,
               member.classification_tags_json
          from orac_code.knowledge_retrieval_members_v member
         where member.knowledge_scope_id = l_scope_id
           and (l_operation = 'METADATA' or member.retrieval_eligible_yn = 'Y')
           and (
             (l_target_type = 'DOCUMENT'
              and member.document_id = l_target_id
              and member.document_version_id = member.current_document_version_id)
             or (l_target_type = 'DOCUMENT_VERSION'
                 and member.document_version_id = l_target_id)
             or (l_target_type = 'EXTRACTION' and member.extraction_id = l_target_id)
             or (l_target_type = 'ARTEFACT' and member.artefact_id = l_target_id)
             or (l_target_type = 'CHUNK_SET' and exists (
                   select 1
                     from orac_api.knowledge_chunk_sets_v chunk_set
                    where chunk_set.chunk_set_id = l_target_id
                      and chunk_set.extraction_id = member.extraction_id
                 ))
           )
         order by member.extraction_id, member.member_ordinal nulls first;
    end if;
  exception
    when others then
      if sqlcode in (-20631, -20632)
      then
        raise;
      end if;
      begin
        write_event(
          p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
          coalesce(l_operation, 'METADATA'), l_target_type, l_target_id,
          'REJECTED', 'RETRIEVAL_REQUEST_INVALID'
        );
      exception
        when others then
          raise_application_error(-20631, 'RETRIEVAL_AUDIT_UNAVAILABLE');
      end;
      p_resolution_json := resolution_json(
        p_retrieval_id, 'REJECTED', 'RETRIEVAL_REQUEST_INVALID',
        coalesce(l_operation, 'METADATA'), l_target_type, l_target_id
      );
      empty_cursor(p_content_rows);
  end resolve_request;

  function lexical_candidate_score(
    p_lexical_tokens_json in clob,
    p_lexical_phrase      in varchar2,
    p_chunk_text          in clob,
    p_source_name         in varchar2
  ) return number
  is
    l_text             varchar2(32767);
    l_source           varchar2(4000) := lower(coalesce(p_source_name, ''));
    l_token_count      number := 0;
    l_matched_count    number := 0;
    l_identifier_match boolean := false;
    l_source_match     boolean := false;
    l_score            number := 0;
    l_pattern          varchar2(1000);
  begin
    if p_lexical_tokens_json is null
       or p_lexical_tokens_json is not json
       or p_chunk_text is null
    then
      return 0;
    end if;
    l_text := lower(dbms_lob.substr(p_chunk_text, 32767, 1));
    for token in (
      select distinct lower(trim(value)) token_value
        from json_table(
               p_lexical_tokens_json,
               '$[*]' columns (value varchar2(200) path '$' error on error)
             )
       where regexp_like(
               lower(trim(value)),
               '^[a-z0-9]+([._-][a-z0-9]+)*$'
             )
    )
    loop
      l_token_count := l_token_count + 1;
      if l_token_count > 64
      then
        raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
      end if;
      l_pattern := replace(token.token_value, '.', '\.') ;
      l_pattern := replace(l_pattern, '-', '\-');
      l_pattern := '(^|[^a-z0-9._-])' || l_pattern
        || '($|[^a-z0-9._-])';
      if regexp_like(l_text, l_pattern)
      then
        l_matched_count := l_matched_count + 1;
        if instr(token.token_value, '.') > 0
           or instr(token.token_value, '_') > 0
           or instr(token.token_value, '-') > 0
        then
          l_identifier_match := true;
        end if;
      end if;
      if instr(l_source, token.token_value) > 0
      then
        l_source_match := true;
      end if;
    end loop;
    if l_token_count = 0
    then
      return 0;
    end if;
    l_score := (l_matched_count / l_token_count) * 0.75;
    if l_token_count > 1
       and trim(p_lexical_phrase) is not null
       and instr(l_text, lower(trim(p_lexical_phrase))) > 0
    then
      l_score := l_score + 0.15;
    end if;
    if l_identifier_match
    then
      l_score := l_score + 0.10;
    end if;
    if l_source_match
    then
      l_score := l_score + 0.10;
    end if;
    return least(1, l_score);
  exception
    when others then
      if sqlcode = -20632
      then
        raise;
      end if;
      return 0;
  end lexical_candidate_score;

  procedure open_hybrid_candidates_internal(
    p_retrieval_id          in  varchar2,
    p_username              in  varchar2,
    p_scope_type            in  varchar2,
    p_scope_key             in  varchar2,
    p_embedding_profile_id  in  number,
    p_query_vector_json     in  clob,
    p_lexical_tokens_json   in  clob,
    p_lexical_phrase        in  varchar2,
    p_semantic_limit        in  number,
    p_lexical_limit         in  number,
    p_executing_plugin_id   in  varchar2,
    p_correlation_id        in  varchar2,
    p_constraints_json      in  clob,
    p_min_lexical_score     in  number,
    p_parent_retrieval_id   in  varchar2,
    p_resolution_json       out clob,
    p_content_rows          out sys_refcursor
  )
  is
    l_user_id      number;
    l_scope_id     number;
    l_authorized   varchar2(100);
    l_query_vector vector(768, float32);
    l_semantic_threshold number;
    l_semantic_limit pls_integer;
    l_lexical_limit pls_integer;
    l_constraint_count pls_integer;
    l_constraint_length pls_integer;
    l_detail_json  json;
  begin
    if not regexp_like(
         lower(trim(p_retrieval_id)),
         '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
       )
       or p_embedding_profile_id <= 0
       or p_semantic_limit not between 1 and 50
       or p_lexical_limit not between 1 and 50
       or p_query_vector_json is null
       or p_query_vector_json is not json
       or p_lexical_tokens_json is null
       or p_lexical_tokens_json is not json
       or length(p_lexical_phrase) > 2000
       or length(p_correlation_id) > 128
       or p_min_lexical_score not between 0 and 1
       or (p_constraints_json is not null and p_constraints_json is not json)
       or (p_parent_retrieval_id is not null and not regexp_like(
             lower(trim(p_parent_retrieval_id)),
             '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
           ))
       or (p_executing_plugin_id is not null
           and upper(trim(p_scope_type)) <> 'PLUGIN')
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    select count(*), coalesce(max(length(trim(literal))), 0)
      into l_constraint_count, l_constraint_length
      from json_table(
             case when p_constraints_json is null
                  then to_clob('[]') else p_constraints_json end,
             '$[*]' columns (literal varchar2(4000) path '$' error on error)
           );
    if l_constraint_count > 4 or l_constraint_length > 120
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    resolve_identity(
      p_username,
      p_scope_type,
      p_scope_key,
      l_user_id,
      l_scope_id,
      l_authorized
    );
    if p_executing_plugin_id is not null
    then
      select json_object(
               'schema_version' value 2,
               'executing_plugin_id' value trim(p_executing_plugin_id),
               'correlation_id' value trim(p_correlation_id),
               'parent_retrieval_id' value trim(p_parent_retrieval_id),
               'embedding_profile_id' value p_embedding_profile_id
               absent on null returning json
             )
        into l_detail_json
        from dual;
    else
      select json_object(
               'schema_version' value 2,
               'embedding_profile_id' value p_embedding_profile_id,
               'parent_retrieval_id' value trim(p_parent_retrieval_id)
               absent on null
               returning json
             )
        into l_detail_json
        from dual;
    end if;
    if l_authorized <> 'RAG_USAGE_GRANTED'
    then
      write_event(
        p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
        'CHUNK_SEARCH', null, null, 'REJECTED', l_authorized,
        p_detail_json => l_detail_json
      );
      p_resolution_json := resolution_json(
        p_retrieval_id,
        'REJECTED',
        'RETRIEVAL_NOT_AUTHORISED',
        'CHUNK_SEARCH'
      );
      empty_cursor(p_content_rows);
      return;
    end if;

    select profile.semantic_threshold,
           least(p_semantic_limit, profile.semantic_candidate_limit),
           least(p_lexical_limit, profile.lexical_candidate_limit)
      into l_semantic_threshold, l_semantic_limit, l_lexical_limit
      from orac_api.knowledge_embedding_activations_v activation
      join orac_api.knowledge_embedding_profiles_v profile
        on profile.embedding_profile_id = activation.embedding_profile_id
       and profile.embedding_profile_id = p_embedding_profile_id
       and profile.purpose_code = 'KNOWLEDGE_CHUNK_RETRIEVAL'
       and profile.storage_layout_code = 'ORACLE_VECTOR_768_FLOAT32_V1'
       and profile.semantic_yn = 'Y'
       and profile.production_allowed_yn = 'Y'
      join orac_api.knowledge_embedding_models_v model
        on model.embedding_model_id = profile.embedding_model_id
       and model.dimensions = 768
       and model.distance_metric = 'COSINE'
     where activation.purpose_code = 'KNOWLEDGE_CHUNK_RETRIEVAL';

    l_query_vector := to_vector(p_query_vector_json, 768, float32);
    if vector_dimension_count(l_query_vector) <> 768
       or vector_dimension_format(l_query_vector) <> 'FLOAT32'
       or vector_norm(l_query_vector) not between 0.99 and 1.01
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    write_event(
      p_retrieval_id, 'DECISION', p_username, l_user_id, l_scope_id,
      'CHUNK_SEARCH', null, null, 'APPROVED', 'RETRIEVAL_APPROVED',
      p_detail_json => l_detail_json
    );
    p_resolution_json := resolution_json(
      p_retrieval_id,
      'APPROVED',
      'RETRIEVAL_APPROVED',
      'CHUNK_SEARCH'
    );

    open p_content_rows for
      with scope_chunks as (
        select chunk.*
          from orac_code.knowledge_native_searchable_chunks_v chunk
         where chunk.embedding_profile_id = p_embedding_profile_id
           and chunk.knowledge_scope_id = l_scope_id
           and chunk.target_scope_type = upper(trim(p_scope_type))
           and chunk.target_scope_key = trim(p_scope_key)
      ),
      semantic_ranked as (
        select chunk.chunk_id,
               1 - vector_distance(
                     chunk.embedding_vector,
                     l_query_vector,
                     cosine
                   ) semantic_score,
               row_number() over (
                 order by vector_distance(
                            chunk.embedding_vector,
                            l_query_vector,
                            cosine
                          ),
                          chunk.chunk_id
               ) semantic_rank
          from scope_chunks chunk
         order by vector_distance(
                    chunk.embedding_vector,
                    l_query_vector,
                    cosine
                  ),
                  chunk.chunk_id
         fetch exact first l_semantic_limit rows only
      ),
      semantic_candidates as (
        select chunk_id, semantic_score, semantic_rank
          from semantic_ranked
         where semantic_score >= l_semantic_threshold
      ),
      lexical_scored as (
        select chunk.chunk_id,
               orac_code.knowledge_retrieval_api.lexical_candidate_score(
                 p_lexical_tokens_json,
                 p_lexical_phrase,
                 chunk.chunk_text,
                 coalesce(chunk.original_filename, chunk.parent_source_reference)
               ) lexical_score
          from scope_chunks chunk
      ),
      lexical_ranked as (
        select lexical_scored.*,
               row_number() over (
                 order by lexical_score desc, chunk_id
               ) lexical_rank
          from lexical_scored
         order by lexical_score desc, chunk_id
         fetch first l_lexical_limit rows only
      ),
      lexical_candidates as (
        select chunk_id, lexical_score, lexical_rank
          from lexical_ranked
         where lexical_score >= p_min_lexical_score
      ),
      literal_candidates as (
        select chunk.chunk_id
          from scope_chunks chunk
         where p_constraints_json is not null
           and exists (
                 select 1
                   from json_table(
                          p_constraints_json,
                          '$[*]' columns (
                            literal varchar2(120) path '$' error on error
                          )
                        ) constraint_value
                  where trim(constraint_value.literal) is not null
                    and instr(
                          ' ' || regexp_replace(
                            lower(dbms_lob.substr(chunk.chunk_text, 32767, 1)),
                            '[^[:alnum:]]+', ' '
                          ) || ' ',
                          ' ' || regexp_replace(
                            lower(trim(constraint_value.literal)),
                            '[^[:alnum:]]+', ' '
                          ) || ' '
                        ) > 0
               )
         order by chunk.chunk_id
         fetch first l_lexical_limit rows only
      ),
      candidate_keys as (
        select chunk_id from semantic_candidates
        union
        select chunk_id from lexical_candidates
        union
        select chunk_id from literal_candidates
      )
      select chunk.ingestion_request_id,
             chunk.source_object_id,
             chunk.source_type,
             chunk.source_reference,
             chunk.parent_source_reference,
             chunk.document_id,
             chunk.title document_title,
             chunk.document_version_id,
             chunk.original_filename,
             chunk.target_scope_type,
             chunk.target_scope_key,
             chunk.chunk_set_id,
             chunk.chunk_id,
             chunk.chunk_no,
             chunk.span_start,
             chunk.span_end,
             chunk.chunk_content_sha256,
             chunk.chunk_text,
             chunk.chunk_metadata_json,
             chunk.source_artefact_id,
             chunk.source_artefact_role_code,
             chunk.source_artefact_logical_name,
             chunk.source_artefact_media_type,
             chunk.source_artefact_sha256,
             chunk.source_artefact_ordinal,
             chunk.source_sheet_name,
             chunk.source_table_name,
             chunk.source_member_cell_range,
             chunk.source_header_rows_json,
             chunk.source_hidden_sheet,
             chunk.source_row_start,
             chunk.source_row_end,
             chunk.source_chunk_cell_range,
             chunk.source_format_code,
             chunk.normalised_text_sha256,
             chunk.output_mime_type,
             chunk.extractor_code,
             chunk.extractor_version,
             chunk.extractor_metadata_json,
             chunk.classification_tags_json,
             chunk.provider_code embedding_provider_code,
             chunk.embedding_model_revision,
             chunk.embedding_model_identifier,
             chunk.embedding_dimensions,
             chunk.embedding_profile_id,
             chunk.profile_version embedding_profile_version,
             chunk.retrieval_policy_version,
             semantic.semantic_score,
             coalesce(lexical.lexical_score, 0) lexical_score,
             semantic.semantic_rank,
             lexical.lexical_rank,
             chunk.processing_profile_code
        from candidate_keys candidate
        join scope_chunks chunk
          on chunk.chunk_id = candidate.chunk_id
        left join semantic_candidates semantic
          on semantic.chunk_id = candidate.chunk_id
        left join lexical_candidates lexical
          on lexical.chunk_id = candidate.chunk_id
       order by chunk.chunk_id;
  exception
    when no_data_found or too_many_rows then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    when others then
      if sqlcode in (-20631, -20632)
      then
        raise;
      end if;
      raise_application_error(-20633, 'RETRIEVAL_AUTHORIZATION_UNAVAILABLE');
  end open_hybrid_candidates_internal;

  procedure open_hybrid_search_candidates(
    p_retrieval_id          in  varchar2,
    p_username              in  varchar2,
    p_scope_type            in  varchar2,
    p_scope_key             in  varchar2,
    p_embedding_profile_id  in  number,
    p_query_vector_json     in  clob,
    p_lexical_tokens_json   in  clob,
    p_lexical_phrase        in  varchar2,
    p_semantic_limit        in  number default 50,
    p_lexical_limit         in  number default 50,
    p_resolution_json       out clob,
    p_content_rows          out sys_refcursor
  )
  is
  begin
    open_hybrid_candidates_internal(
      p_retrieval_id, p_username, p_scope_type, p_scope_key,
      p_embedding_profile_id, p_query_vector_json, p_lexical_tokens_json,
      p_lexical_phrase, p_semantic_limit, p_lexical_limit, null, null,
      null, 0.25, null, p_resolution_json, p_content_rows
    );
  end open_hybrid_search_candidates;

  procedure open_hybrid_search_candidates_v2(
    p_retrieval_id          in  varchar2,
    p_username              in  varchar2,
    p_scope_type            in  varchar2,
    p_scope_key             in  varchar2,
    p_embedding_profile_id  in  number,
    p_query_vector_json     in  clob,
    p_lexical_tokens_json   in  clob,
    p_lexical_phrase        in  varchar2,
    p_semantic_limit        in  number default 50,
    p_lexical_limit         in  number default 50,
    p_constraints_json      in  clob default null,
    p_min_lexical_score     in  number default 0.25,
    p_parent_retrieval_id   in  varchar2 default null,
    p_resolution_json       out clob,
    p_content_rows          out sys_refcursor
  )
  is
  begin
    open_hybrid_candidates_internal(
      p_retrieval_id,
      p_username,
      p_scope_type,
      p_scope_key,
      p_embedding_profile_id,
      p_query_vector_json,
      p_lexical_tokens_json,
      p_lexical_phrase,
      p_semantic_limit,
      p_lexical_limit,
      null,
      null,
      p_constraints_json,
      p_min_lexical_score,
      p_parent_retrieval_id,
      p_resolution_json,
      p_content_rows
    );
  end open_hybrid_search_candidates_v2;

  procedure open_authorised_project_candidates(
    p_retrieval_id          in  varchar2,
    p_username              in  varchar2,
    p_embedding_profile_id  in  number,
    p_query_vector_json     in  clob,
    p_lexical_tokens_json   in  clob,
    p_lexical_phrase        in  varchar2,
    p_semantic_limit        in  number default 50,
    p_lexical_limit         in  number default 50,
    p_resolution_json       out clob,
    p_content_rows          out sys_refcursor
  )
  is
  begin
    open_authorised_project_candidates_v2(
      p_retrieval_id, p_username, p_embedding_profile_id, p_query_vector_json,
      p_lexical_tokens_json, p_lexical_phrase, p_semantic_limit,
      p_lexical_limit, null, 0.25, null, p_resolution_json, p_content_rows
    );
  end open_authorised_project_candidates;

  procedure open_authorised_project_candidates_v2(
    p_retrieval_id          in  varchar2,
    p_username              in  varchar2,
    p_embedding_profile_id  in  number,
    p_query_vector_json     in  clob,
    p_lexical_tokens_json   in  clob,
    p_lexical_phrase        in  varchar2,
    p_semantic_limit        in  number default 50,
    p_lexical_limit         in  number default 50,
    p_constraints_json      in  clob default null,
    p_min_lexical_score     in  number default 0.25,
    p_parent_retrieval_id   in  varchar2 default null,
    p_resolution_json       out clob,
    p_content_rows          out sys_refcursor
  )
  is
    l_user_id         number;
    l_scope_count     pls_integer;
    l_query_vector    vector(768, float32);
    l_semantic_limit  pls_integer;
    l_lexical_limit   pls_integer;
    l_constraint_count pls_integer;
    l_constraint_length pls_integer;
    l_detail_json     json;
  begin
    if not regexp_like(
         lower(trim(p_retrieval_id)),
         '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
       )
       or p_embedding_profile_id <= 0
       or p_semantic_limit not between 1 and 50
       or p_lexical_limit not between 1 and 50
       or p_query_vector_json is null
       or p_query_vector_json is not json
       or p_lexical_tokens_json is null
       or p_lexical_tokens_json is not json
       or length(p_lexical_phrase) > 2000
       or p_min_lexical_score not between 0 and 1
       or (p_constraints_json is not null and p_constraints_json is not json)
       or (p_parent_retrieval_id is not null and not regexp_like(
             lower(trim(p_parent_retrieval_id)),
             '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
           ))
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    select count(*), coalesce(max(length(trim(literal))), 0)
      into l_constraint_count, l_constraint_length
      from json_table(
             case when p_constraints_json is null
                  then to_clob('[]') else p_constraints_json end,
             '$[*]' columns (literal varchar2(4000) path '$' error on error)
           );
    if l_constraint_count > 4 or l_constraint_length > 120
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    begin
      select user_id
        into l_user_id
        from orac_api.users_v
       where lower(username) = lower(trim(p_username))
         and is_active = 'Y';
    exception
      when no_data_found then
        write_event(
          p_retrieval_id, 'DECISION', p_username, null, null,
          'AUTHORISED_PROJECT_SEARCH', null, null, 'REJECTED',
          'RAG_USAGE_PRINCIPAL_UNKNOWN'
        );
        p_resolution_json := resolution_json(
          p_retrieval_id,
          'REJECTED',
          'RAG_USAGE_PRINCIPAL_UNKNOWN',
          'AUTHORISED_PROJECT_SEARCH'
        );
        empty_cursor(p_content_rows);
        return;
    end;

    select count(distinct knowledge_scope.knowledge_scope_id)
      into l_scope_count
      from orac_api.rag_usage_privileges_v privilege
      join orac_api.knowledge_scopes_v knowledge_scope
        on knowledge_scope.knowledge_scope_id = privilege.knowledge_scope_id
       and knowledge_scope.scope_type = 'PROJECT'
      join orac_api.project_registry_v project
        on project.project_id = knowledge_scope.project_id
       and project.active_yn = 'Y'
     where privilege.user_id = l_user_id
       and privilege.privilege_code = 'USE'
       and privilege.active_yn = 'Y'
       and privilege.effective_on <= systimestamp
       and (
             privilege.expires_on is null
             or privilege.expires_on > systimestamp
           );
    if l_scope_count = 0
    then
      write_event(
        p_retrieval_id, 'DECISION', p_username, l_user_id, null,
        'AUTHORISED_PROJECT_SEARCH', null, null, 'REJECTED',
        'RAG_USAGE_NOT_GRANTED'
      );
      p_resolution_json := resolution_json(
        p_retrieval_id,
        'REJECTED',
        'RAG_USAGE_NOT_GRANTED',
        'AUTHORISED_PROJECT_SEARCH'
      );
      empty_cursor(p_content_rows);
      return;
    end if;

    select least(p_semantic_limit, profile.semantic_candidate_limit),
           least(p_lexical_limit, profile.lexical_candidate_limit)
      into l_semantic_limit, l_lexical_limit
      from orac_api.knowledge_embedding_activations_v activation
      join orac_api.knowledge_embedding_profiles_v profile
        on profile.embedding_profile_id = activation.embedding_profile_id
       and profile.embedding_profile_id = p_embedding_profile_id
       and profile.purpose_code = 'KNOWLEDGE_CHUNK_RETRIEVAL'
       and profile.storage_layout_code = 'ORACLE_VECTOR_768_FLOAT32_V1'
       and profile.semantic_yn = 'Y'
       and profile.production_allowed_yn = 'Y'
      join orac_api.knowledge_embedding_models_v model
        on model.embedding_model_id = profile.embedding_model_id
       and model.dimensions = 768
       and model.distance_metric = 'COSINE'
     where activation.purpose_code = 'KNOWLEDGE_CHUNK_RETRIEVAL';

    l_query_vector := to_vector(p_query_vector_json, 768, float32);
    if vector_dimension_count(l_query_vector) <> 768
       or vector_dimension_format(l_query_vector) <> 'FLOAT32'
       or vector_norm(l_query_vector) not between 0.99 and 1.01
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    select json_object(
             'schema_version' value 1,
             'embedding_profile_id' value p_embedding_profile_id,
             'authorised_project_count' value l_scope_count,
             'parent_retrieval_id' value trim(p_parent_retrieval_id)
             absent on null
             returning json
           )
      into l_detail_json
      from dual;
    write_event(
      p_retrieval_id, 'DECISION', p_username, l_user_id, null,
      'AUTHORISED_PROJECT_SEARCH', null, null, 'APPROVED',
      'RETRIEVAL_APPROVED', p_detail_json => l_detail_json
    );
    p_resolution_json := resolution_json(
      p_retrieval_id,
      'APPROVED',
      'RETRIEVAL_APPROVED',
      'AUTHORISED_PROJECT_SEARCH'
    );

    open p_content_rows for
      with authorised_scopes as (
        select distinct knowledge_scope.knowledge_scope_id
          from orac_api.rag_usage_privileges_v privilege
          join orac_api.knowledge_scopes_v knowledge_scope
            on knowledge_scope.knowledge_scope_id = privilege.knowledge_scope_id
           and knowledge_scope.scope_type = 'PROJECT'
          join orac_api.project_registry_v project
            on project.project_id = knowledge_scope.project_id
           and project.active_yn = 'Y'
         where privilege.user_id = l_user_id
           and privilege.privilege_code = 'USE'
           and privilege.active_yn = 'Y'
           and privilege.effective_on <= systimestamp
           and (
                 privilege.expires_on is null
                 or privilege.expires_on > systimestamp
               )
      ),
      project_chunks as (
        select chunk.*
          from orac_code.knowledge_native_searchable_chunks_v chunk
          join authorised_scopes authorised
            on authorised.knowledge_scope_id = chunk.knowledge_scope_id
         where chunk.embedding_profile_id = p_embedding_profile_id
           and chunk.target_scope_type = 'PROJECT'
      ),
      semantic_ranked as (
        select chunk.chunk_id,
               1 - vector_distance(
                     chunk.embedding_vector,
                     l_query_vector,
                     cosine
                   ) semantic_score,
               row_number() over (
                 order by vector_distance(
                            chunk.embedding_vector,
                            l_query_vector,
                            cosine
                          ),
                          chunk.chunk_id
               ) semantic_rank
          from project_chunks chunk
         order by vector_distance(
                    chunk.embedding_vector,
                    l_query_vector,
                    cosine
                  ),
                  chunk.chunk_id
         fetch exact first l_semantic_limit rows only
      ),
      semantic_candidates as (
        select ranked.chunk_id,
               ranked.semantic_score,
               ranked.semantic_rank
          from semantic_ranked ranked
          join project_chunks chunk
            on chunk.chunk_id = ranked.chunk_id
         where ranked.semantic_score >= chunk.semantic_threshold
      ),
      lexical_scored as (
        select chunk.chunk_id,
               orac_code.knowledge_retrieval_api.lexical_candidate_score(
                 p_lexical_tokens_json,
                 p_lexical_phrase,
                 chunk.chunk_text,
                 coalesce(chunk.original_filename, chunk.parent_source_reference)
               ) lexical_score
          from project_chunks chunk
      ),
      lexical_ranked as (
        select lexical_scored.*,
               row_number() over (
                 order by lexical_score desc, chunk_id
               ) lexical_rank
          from lexical_scored
         order by lexical_score desc, chunk_id
         fetch first l_lexical_limit rows only
      ),
      lexical_candidates as (
        select chunk_id, lexical_score, lexical_rank
          from lexical_ranked
         where lexical_score >= p_min_lexical_score
      ),
      literal_candidates as (
        select chunk.chunk_id
          from project_chunks chunk
         where p_constraints_json is not null
           and exists (
                 select 1
                   from json_table(
                          p_constraints_json,
                          '$[*]' columns (
                            literal varchar2(120) path '$' error on error
                          )
                        ) constraint_value
                  where trim(constraint_value.literal) is not null
                    and instr(
                          ' ' || regexp_replace(
                            lower(dbms_lob.substr(chunk.chunk_text, 32767, 1)),
                            '[^[:alnum:]]+', ' '
                          ) || ' ',
                          ' ' || regexp_replace(
                            lower(trim(constraint_value.literal)),
                            '[^[:alnum:]]+', ' '
                          ) || ' '
                        ) > 0
               )
         order by chunk.chunk_id
         fetch first l_lexical_limit rows only
      ),
      candidate_keys as (
        select chunk_id from semantic_candidates
        union
        select chunk_id from lexical_candidates
        union
        select chunk_id from literal_candidates
      )
      select chunk.ingestion_request_id,
             chunk.source_object_id,
             chunk.source_type,
             chunk.source_reference,
             chunk.parent_source_reference,
             chunk.document_id,
             chunk.title document_title,
             chunk.document_version_id,
             chunk.original_filename,
             chunk.target_scope_type,
             chunk.target_scope_key,
             chunk.chunk_set_id,
             chunk.chunk_id,
             chunk.chunk_no,
             chunk.span_start,
             chunk.span_end,
             chunk.chunk_content_sha256,
             chunk.chunk_text,
             chunk.chunk_metadata_json,
             chunk.source_artefact_id,
             chunk.source_artefact_role_code,
             chunk.source_artefact_logical_name,
             chunk.source_artefact_media_type,
             chunk.source_artefact_sha256,
             chunk.source_artefact_ordinal,
             chunk.source_sheet_name,
             chunk.source_table_name,
             chunk.source_member_cell_range,
             chunk.source_header_rows_json,
             chunk.source_hidden_sheet,
             chunk.source_row_start,
             chunk.source_row_end,
             chunk.source_chunk_cell_range,
             chunk.source_format_code,
             chunk.normalised_text_sha256,
             chunk.output_mime_type,
             chunk.extractor_code,
             chunk.extractor_version,
             chunk.extractor_metadata_json,
             chunk.classification_tags_json,
             chunk.provider_code embedding_provider_code,
             chunk.embedding_model_revision,
             chunk.embedding_model_identifier,
             chunk.embedding_dimensions,
             chunk.embedding_profile_id,
             chunk.profile_version embedding_profile_version,
             chunk.retrieval_policy_version,
             semantic.semantic_score,
             coalesce(lexical.lexical_score, 0) lexical_score,
             semantic.semantic_rank,
             lexical.lexical_rank,
             chunk.processing_profile_code
        from candidate_keys candidate
        join project_chunks chunk
          on chunk.chunk_id = candidate.chunk_id
        left join semantic_candidates semantic
          on semantic.chunk_id = candidate.chunk_id
        left join lexical_candidates lexical
          on lexical.chunk_id = candidate.chunk_id
       order by chunk.chunk_id;
  exception
    when no_data_found or too_many_rows then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    when others then
      if sqlcode in (-20631, -20632)
      then
        raise;
      end if;
      raise_application_error(-20633, 'RETRIEVAL_AUTHORIZATION_UNAVAILABLE');
  end open_authorised_project_candidates_v2;

  procedure open_plugin_hybrid_candidates(
    p_retrieval_id          in  varchar2,
    p_username              in  varchar2,
    p_plugin_id             in  varchar2,
    p_embedding_profile_id  in  number,
    p_query_vector_json     in  clob,
    p_lexical_tokens_json   in  clob,
    p_lexical_phrase        in  varchar2,
    p_semantic_limit        in  number default 50,
    p_lexical_limit         in  number default 50,
    p_correlation_id        in  varchar2 default null,
    p_resolution_json       out clob,
    p_content_rows          out sys_refcursor
  )
  is
  begin
    open_plugin_hybrid_candidates_v2(
      p_retrieval_id, p_username, p_plugin_id, p_embedding_profile_id,
      p_query_vector_json, p_lexical_tokens_json, p_lexical_phrase,
      p_semantic_limit, p_lexical_limit, p_correlation_id, null, 0.25, null,
      p_resolution_json, p_content_rows
    );
  end open_plugin_hybrid_candidates;

  procedure open_plugin_hybrid_candidates_v2(
    p_retrieval_id          in  varchar2,
    p_username              in  varchar2,
    p_plugin_id             in  varchar2,
    p_embedding_profile_id  in  number,
    p_query_vector_json     in  clob,
    p_lexical_tokens_json   in  clob,
    p_lexical_phrase        in  varchar2,
    p_semantic_limit        in  number default 50,
    p_lexical_limit         in  number default 50,
    p_correlation_id        in  varchar2 default null,
    p_constraints_json      in  clob default null,
    p_min_lexical_score     in  number default 0.25,
    p_parent_retrieval_id   in  varchar2 default null,
    p_resolution_json       out clob,
    p_content_rows          out sys_refcursor
  )
  is
  begin
    if trim(p_plugin_id) is null
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;
    open_hybrid_candidates_internal(
      p_retrieval_id,
      p_username,
      'PLUGIN',
      trim(p_plugin_id),
      p_embedding_profile_id,
      p_query_vector_json,
      p_lexical_tokens_json,
      p_lexical_phrase,
      p_semantic_limit,
      p_lexical_limit,
      trim(p_plugin_id),
      p_correlation_id,
      p_constraints_json,
      p_min_lexical_score,
      p_parent_retrieval_id,
      p_resolution_json,
      p_content_rows
    );
  end open_plugin_hybrid_candidates_v2;

  procedure record_policy_decision(
    p_policy_request_id       in varchar2,
    p_username                in varchar2,
    p_scope_type              in varchar2,
    p_scope_key               in varchar2,
    p_target_type             in varchar2,
    p_target_id               in number,
    p_decision_code           in varchar2,
    p_reason_code             in varchar2,
    p_purpose_code            in varchar2,
    p_requested_level_code    in varchar2,
    p_effective_level_code    in varchar2,
    p_policy_version          in varchar2,
    p_estimator_code          in varchar2,
    p_estimated_byte_size     in number default null,
    p_estimated_token_count   in number default null,
    p_usable_context_tokens   in number default null,
    p_member_count            in number default null,
    p_chunk_count             in number default null,
    p_complete_yn             in varchar2 default 'N',
    p_selected_yn             in varchar2 default 'N',
    p_downgraded_yn           in varchar2 default 'N',
    p_truncated_yn            in varchar2 default 'N'
  )
  is
    l_user_id      number;
    l_scope_id     number;
    l_authorized   varchar2(100);
    l_status_code  varchar2(30);
    l_detail_json  json;
  begin
    if not regexp_like(
         lower(trim(p_policy_request_id)),
         '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
       )
       or p_target_type not in (
         'DOCUMENT', 'DOCUMENT_VERSION', 'EXTRACTION', 'ARTEFACT', 'CHUNK_SET'
       )
       or p_target_id <= 0
       or p_decision_code not in (
         'APPROVED', 'DOWNGRADED', 'NEEDS_EVIDENCE', 'REJECTED'
       )
       or not regexp_like(p_reason_code, '^MAT_[A-Z0-9_]{1,96}$')
       or p_purpose_code not in (
         'INSPECT_STRUCTURE', 'QUESTION_ANSWERING', 'FOLLOW_UP', 'SUMMARISE',
         'REVIEW', 'EXTRACT', 'ANALYSE', 'COMPARE'
       )
       or p_requested_level_code not in (
         'METADATA_STRUCTURE', 'RELEVANT_CHUNKS', 'SURROUNDING_CONTEXT',
         'LOGICAL_SELECTION', 'SELECTED_ARTEFACTS',
         'COMPLETE_NORMALISED_DOCUMENT'
       )
       or (p_effective_level_code is not null and p_effective_level_code not in (
         'METADATA_STRUCTURE', 'RELEVANT_CHUNKS', 'SURROUNDING_CONTEXT',
         'LOGICAL_SELECTION', 'SELECTED_ARTEFACTS',
         'COMPLETE_NORMALISED_DOCUMENT'
       ))
       or not regexp_like(p_policy_version, '^[A-Z0-9._-]{1,30}$')
       or (p_estimator_code is not null
           and not regexp_like(p_estimator_code, '^[A-Z0-9_]{1,30}$'))
       or p_estimated_byte_size < 0
       or p_estimated_token_count < 0
       or p_usable_context_tokens < 0
       or p_member_count < 0
       or p_chunk_count < 0
       or p_complete_yn not in ('Y', 'N')
       or p_selected_yn not in ('Y', 'N')
       or p_downgraded_yn not in ('Y', 'N')
       or p_truncated_yn <> 'N'
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    resolve_identity(
      p_username, p_scope_type, p_scope_key,
      l_user_id, l_scope_id, l_authorized
    );
    if l_authorized <> 'RAG_USAGE_GRANTED'
    then
      raise_application_error(-20634, 'MATERIALISATION_POLICY_NOT_AUTHORISED');
    end if;

    l_status_code := case
      when p_decision_code in ('APPROVED', 'DOWNGRADED') then 'APPROVED'
      else 'REJECTED'
    end;
    select json_object(
             'schema_version' value 1,
             'policy_version' value p_policy_version,
             'decision_code' value p_decision_code,
             'purpose_code' value p_purpose_code,
             'requested_level_code' value p_requested_level_code,
             'effective_level_code' value p_effective_level_code,
             'estimator_code' value p_estimator_code,
             'estimated_token_count' value p_estimated_token_count,
             'usable_context_tokens' value p_usable_context_tokens,
             'complete' value p_complete_yn,
             'selected' value p_selected_yn,
             'downgraded' value p_downgraded_yn,
             'truncated' value p_truncated_yn
             absent on null
             returning json
           )
      into l_detail_json
      from dual;
    write_event(
      p_policy_request_id, 'DECISION', p_username, l_user_id, l_scope_id,
      'MATERIALISATION_POLICY', p_target_type, p_target_id, l_status_code,
      p_reason_code, p_estimated_byte_size, null, null,
      p_member_count, p_chunk_count, null, l_detail_json
    );
  end record_policy_decision;

  procedure record_model_submission_decision(
    p_submission_id             in varchar2,
    p_policy_request_id         in varchar2,
    p_username                  in varchar2,
    p_scope_type                in varchar2,
    p_scope_key                 in varchar2,
    p_target_type               in varchar2,
    p_target_id                 in number,
    p_llm_id                    in number,
    p_registry_row_version      in number,
    p_provider_capability_code  in varchar2,
    p_context_policy_code       in varchar2,
    p_envelope_version          in number,
    p_effective_level_code      in varchar2,
    p_part_count                in number,
    p_member_count              in number default null,
    p_chunk_count               in number default null,
    p_verified_source_bytes     in number,
    p_envelope_bytes            in number,
    p_evidence_tokens           in number,
    p_occupied_tokens           in number,
    p_final_input_tokens        in number,
    p_reserved_output_tokens    in number,
    p_safety_tokens             in number,
    p_complete_yn               in varchar2 default 'N',
    p_selected_yn               in varchar2 default 'N',
    p_downgraded_yn             in varchar2 default 'N',
    p_non_truncated_yn          in varchar2 default 'Y',
    p_retry_count               in number default 0,
    p_reason_code               in varchar2 default 'MAT_SUB_APPROVED'
  )
  is
    l_user_id         number;
    l_scope_id        number;
    l_authorized      varchar2(100);
    l_policy_decision orac_api.knowledge_retrieval_events_v%rowtype;
    l_detail_json     json;
    l_existing_count  pls_integer;
    l_outcome_count   pls_integer;
  begin
    if not regexp_like(
         lower(trim(p_submission_id)),
         '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
       )
       or not regexp_like(
         lower(trim(p_policy_request_id)),
         '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
       )
       or p_target_type not in (
         'DOCUMENT', 'DOCUMENT_VERSION', 'EXTRACTION', 'ARTEFACT', 'CHUNK_SET'
       )
       or p_target_id <= 0
       or p_llm_id <= 0
       or p_registry_row_version <= 0
       or not regexp_like(p_provider_capability_code, '^[a-z0-9_]{1,30}$')
       or not regexp_like(p_context_policy_code, '^[A-Z0-9_]{1,30}$')
       or p_envelope_version <> 1
       or p_effective_level_code not in (
         'RELEVANT_CHUNKS', 'SURROUNDING_CONTEXT', 'LOGICAL_SELECTION',
         'SELECTED_ARTEFACTS', 'COMPLETE_NORMALISED_DOCUMENT'
       )
       or p_part_count <= 0
       or p_member_count < 0
       or p_chunk_count < 0
       or p_verified_source_bytes < 0
       or p_envelope_bytes <= 0
       or p_evidence_tokens <= 0
       or p_occupied_tokens < 0
       or p_final_input_tokens <= 0
       or p_reserved_output_tokens <> 2048
       or p_safety_tokens < 0
       or p_complete_yn not in ('Y', 'N')
       or p_selected_yn not in ('Y', 'N')
       or p_downgraded_yn not in ('Y', 'N')
       or p_non_truncated_yn <> 'Y'
       or p_retry_count not between 0 and 1
       or not regexp_like(p_reason_code, '^MAT_SUB_[A-Z0-9_]{1,80}$')
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    resolve_identity(
      p_username, p_scope_type, p_scope_key,
      l_user_id, l_scope_id, l_authorized
    );
    if l_authorized <> 'RAG_USAGE_GRANTED'
    then
      raise_application_error(-20635, 'MODEL_SUBMISSION_NOT_AUTHORISED');
    end if;

    select count(*)
      into l_existing_count
      from orac_api.knowledge_retrieval_events_v
     where retrieval_id = lower(trim(p_submission_id))
       and event_type_code = 'DECISION';
    if l_existing_count > 0
    then
      select count(*)
        into l_existing_count
        from orac_api.knowledge_retrieval_events_v existing_event
       where existing_event.retrieval_id = lower(trim(p_submission_id))
         and existing_event.event_type_code = 'DECISION'
         and existing_event.operation_code = 'MODEL_SUBMISSION'
         and existing_event.username_snapshot = trim(p_username)
         and existing_event.knowledge_scope_id = l_scope_id
         and existing_event.target_type_code = p_target_type
         and existing_event.target_id = p_target_id
         and json_value(
               existing_event.detail_json,
               '$.policy_request_id' returning varchar2(36)
             ) = lower(trim(p_policy_request_id))
         and json_value(
               existing_event.detail_json,
               '$.llm_id' returning number
             ) = p_llm_id
         and json_value(
               existing_event.detail_json,
               '$.registry_row_version' returning number
             ) = p_registry_row_version
         and json_value(
               existing_event.detail_json,
               '$.rendered_envelope_bytes' returning number
             ) = p_envelope_bytes
         and json_value(
               existing_event.detail_json,
               '$.estimated_final_input_tokens' returning number
             ) = p_final_input_tokens;
      if l_existing_count = 1
      then
        return;
      end if;
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    begin
      select *
        into l_policy_decision
        from orac_api.knowledge_retrieval_events_v
       where retrieval_id = lower(trim(p_policy_request_id))
         and event_type_code = 'DECISION'
         and operation_code = 'MATERIALISATION_POLICY'
         and status_code = 'APPROVED';
    exception
      when no_data_found then
        raise_application_error(-20636, 'MODEL_SUBMISSION_POLICY_INVALID');
    end;

    select count(*)
      into l_outcome_count
      from orac_api.knowledge_retrieval_events_v
     where retrieval_id = lower(trim(p_policy_request_id))
       and event_type_code = 'OUTCOME'
       and operation_code = 'MATERIALISATION_POLICY'
       and status_code = 'COMPLETED';
    if l_outcome_count <> 1
       or l_policy_decision.username_snapshot <> trim(p_username)
       or l_policy_decision.knowledge_scope_id <> l_scope_id
       or l_policy_decision.target_type_code <> p_target_type
       or l_policy_decision.target_id <> p_target_id
       or json_value(
            l_policy_decision.detail_json,
            '$.effective_level_code' returning varchar2(40)
          ) <> p_effective_level_code
    then
      raise_application_error(-20636, 'MODEL_SUBMISSION_POLICY_INVALID');
    end if;

    select json_object(
             'schema_version' value 1,
             'policy_request_id' value lower(trim(p_policy_request_id)),
             'llm_id' value p_llm_id,
             'registry_row_version' value p_registry_row_version,
             'provider_capability_code' value p_provider_capability_code,
             'context_policy_code' value p_context_policy_code,
             'envelope_version' value p_envelope_version,
             'effective_level_code' value p_effective_level_code,
             'part_count' value p_part_count,
             'member_count' value p_member_count,
             'chunk_count' value p_chunk_count,
             'verified_source_bytes' value p_verified_source_bytes,
             'rendered_envelope_bytes' value p_envelope_bytes,
             'estimated_evidence_tokens' value p_evidence_tokens,
             'estimated_occupied_tokens' value p_occupied_tokens,
             'estimated_final_input_tokens' value p_final_input_tokens,
             'reserved_output_tokens' value p_reserved_output_tokens,
             'context_safety_tokens' value p_safety_tokens,
             'complete' value p_complete_yn,
             'selected' value p_selected_yn,
             'downgraded' value p_downgraded_yn,
             'non_truncated' value p_non_truncated_yn,
             'retry_count' value p_retry_count
             absent on null
             returning json
           )
      into l_detail_json
      from dual;
    write_event(
      p_submission_id, 'DECISION', p_username, l_user_id, l_scope_id,
      'MODEL_SUBMISSION', p_target_type, p_target_id, 'APPROVED',
      p_reason_code, p_verified_source_bytes, p_envelope_bytes, null,
      p_member_count, p_chunk_count, null, l_detail_json
    );
  end record_model_submission_decision;

  procedure record_outcome(
    p_retrieval_id       in varchar2,
    p_outcome_code       in varchar2,
    p_reason_code        in varchar2,
    p_returned_byte_size in number default null,
    p_returned_sha256    in varchar2 default null,
    p_member_count       in number default null,
    p_chunk_count        in number default null,
    p_duration_ms        in number default null,
    p_selected_chunk_ids_json in clob default null
  )
  is
    l_decision       orac_api.knowledge_retrieval_events_v%rowtype;
    l_existing_count pls_integer;
    l_selected_count pls_integer;
    l_distinct_count pls_integer;
    l_scope_count    pls_integer;
    l_detail_json    json;
  begin
    if p_outcome_code not in ('COMPLETED', 'FAILED', 'CANCELLED')
       or not regexp_like(p_reason_code, '^[A-Z0-9_]{1,100}$')
       or p_returned_byte_size < 0
       or (p_returned_sha256 is not null
           and not regexp_like(p_returned_sha256, '^[0-9a-f]{64}$'))
       or p_member_count < 0
       or p_chunk_count < 0
       or p_duration_ms < 0
       or (p_selected_chunk_ids_json is not null
           and (dbms_lob.getlength(p_selected_chunk_ids_json) > 4096
                or p_selected_chunk_ids_json is not json))
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;
    select count(*)
      into l_existing_count
      from orac_api.knowledge_retrieval_events_v
     where retrieval_id = lower(trim(p_retrieval_id))
       and event_type_code = 'OUTCOME';
    if l_existing_count > 0
    then
      select count(*)
        into l_existing_count
        from orac_api.knowledge_retrieval_events_v
       where retrieval_id = lower(trim(p_retrieval_id))
         and event_type_code = 'OUTCOME'
         and status_code = p_outcome_code
         and reason_code = p_reason_code;
      if l_existing_count = 1
      then
        return;
      end if;
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;
    select *
      into l_decision
      from orac_api.knowledge_retrieval_events_v
     where retrieval_id = lower(trim(p_retrieval_id))
       and event_type_code = 'DECISION';
    if p_selected_chunk_ids_json is not null
    then
      select count(*), count(distinct selected.chunk_id)
        into l_selected_count, l_distinct_count
        from json_table(
               p_selected_chunk_ids_json,
               '$[*]' columns (
                 chunk_id number path '$' error on error
               )
             ) selected;
      if l_selected_count > 64
         or l_selected_count <> l_distinct_count
         or l_selected_count <> coalesce(p_chunk_count, 0)
      then
        raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
      end if;
      select count(*)
        into l_scope_count
        from (
          select distinct selected.chunk_id
            from json_table(
                   p_selected_chunk_ids_json,
                   '$[*]' columns (
                     chunk_id number path '$' error on error
                   )
                 ) selected
            join orac_code.knowledge_searchable_chunk_content_v chunk
              on chunk.chunk_id = selected.chunk_id
            join orac_api.knowledge_source_objects_v source_object
              on source_object.source_object_id = chunk.source_object_id
             and (
                   (
                     l_decision.operation_code = 'AUTHORISED_PROJECT_SEARCH'
                     and exists (
                       select 1
                         from orac_api.rag_usage_privileges_v privilege
                         join orac_api.knowledge_scopes_v knowledge_scope
                           on knowledge_scope.knowledge_scope_id =
                              privilege.knowledge_scope_id
                          and knowledge_scope.scope_type = 'PROJECT'
                         join orac_api.project_registry_v project
                           on project.project_id = knowledge_scope.project_id
                          and project.active_yn = 'Y'
                        where privilege.user_id = l_decision.user_id
                          and privilege.knowledge_scope_id =
                              source_object.knowledge_scope_id
                          and privilege.privilege_code = 'USE'
                          and privilege.active_yn = 'Y'
                          and privilege.effective_on <= systimestamp
                          and (
                                privilege.expires_on is null
                                or privilege.expires_on > systimestamp
                              )
                     )
                   )
                   or (
                     l_decision.operation_code <> 'AUTHORISED_PROJECT_SEARCH'
                     and source_object.knowledge_scope_id =
                         l_decision.knowledge_scope_id
                   )
                 )
           where selected.chunk_id > 0
        );
      if l_scope_count <> l_selected_count
      then
        raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
      end if;
      select json_object(
               'schema_version' value 2,
               'executing_plugin_id' value json_value(
                 l_decision.detail_json,
                 '$.executing_plugin_id' returning varchar2(255)
               ),
               'correlation_id' value json_value(
                 l_decision.detail_json,
                 '$.correlation_id' returning varchar2(128)
               ),
               'selected_chunks' value coalesce((
                 select json_arrayagg(
                          json_object(
                            'ordinal' value provenance.selected_ordinal,
                            'document_id' value provenance.document_id,
                            'document_version_id' value provenance.document_version_id,
                            'chunk_id' value provenance.chunk_id
                            returning clob
                          ) order by provenance.selected_ordinal
                          returning clob
                        )
                   from (
                     select selected.selected_ordinal,
                                     chunk.document_id,
                                     chunk.document_version_id,
                                     chunk.chunk_id
                       from json_table(
                              p_selected_chunk_ids_json,
                              '$[*]' columns (
                                selected_ordinal for ordinality,
                                chunk_id number path '$' error on error
                              )
                            ) selected
                       join orac_code.knowledge_searchable_chunk_content_v chunk
                         on chunk.chunk_id = selected.chunk_id
                       join orac_api.knowledge_source_objects_v source_object
                         on source_object.source_object_id = chunk.source_object_id
                        and (
                              (
                                l_decision.operation_code =
                                  'AUTHORISED_PROJECT_SEARCH'
                                and exists (
                                  select 1
                                    from orac_api.rag_usage_privileges_v privilege
                                    join orac_api.knowledge_scopes_v knowledge_scope
                                      on knowledge_scope.knowledge_scope_id =
                                         privilege.knowledge_scope_id
                                     and knowledge_scope.scope_type = 'PROJECT'
                                    join orac_api.project_registry_v project
                                      on project.project_id =
                                         knowledge_scope.project_id
                                     and project.active_yn = 'Y'
                                   where privilege.user_id = l_decision.user_id
                                     and privilege.knowledge_scope_id =
                                         source_object.knowledge_scope_id
                                     and privilege.privilege_code = 'USE'
                                     and privilege.active_yn = 'Y'
                                     and privilege.effective_on <= systimestamp
                                     and (
                                           privilege.expires_on is null
                                           or privilege.expires_on > systimestamp
                                         )
                                )
                              )
                              or (
                                l_decision.operation_code <>
                                  'AUTHORISED_PROJECT_SEARCH'
                                and source_object.knowledge_scope_id =
                                    l_decision.knowledge_scope_id
                              )
                            )
                   ) provenance
               ), to_clob('[]')) format json
               absent on null
               returning json
             )
        into l_detail_json
        from dual;
    end if;
    write_event(
      p_retrieval_id, 'OUTCOME', l_decision.username_snapshot,
      l_decision.user_id, l_decision.knowledge_scope_id,
      l_decision.operation_code, l_decision.target_type_code,
      l_decision.target_id, p_outcome_code, p_reason_code,
      l_decision.expected_byte_size, p_returned_byte_size,
      p_returned_sha256, p_member_count, p_chunk_count, p_duration_ms,
      l_detail_json
    );
  exception
    when no_data_found then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
  end record_outcome;

  procedure record_governed_retrieval_event(
    p_event_id                    in varchar2,
    p_username                    in varchar2,
    p_domain_code                 in varchar2,
    p_status_code                 in varchar2,
    p_reason_code                 in varchar2,
    p_tool_mode                   in varchar2,
    p_tool_timing                 in varchar2,
    p_stream_health_state         in varchar2,
    p_committed_before_tool_yn    in varchar2 default 'N',
    p_continuation_recovery_yn    in varchar2 default 'N',
    p_final_invocation_id         in varchar2 default null,
    p_duration_ms                 in number default null,
    p_phase2c_detail_json         in clob default null
  )
  is
    l_user_id     number;
    l_detail_json json;
    l_domain      varchar2(30) := upper(trim(p_domain_code));
    l_mode        varchar2(20) := upper(trim(p_tool_mode));
    l_timing      varchar2(20) := upper(trim(p_tool_timing));
    l_json_valid  number;
  begin
    if l_domain not in ('CONVERSATION', 'PROJECT', 'PLUGIN', 'MULTIPLE', 'NONE')
       or l_mode not in ('STREAMING', 'BUFFERED')
       or l_timing not in ('EARLY', 'LATE', 'NONE')
       or p_status_code not in ('COMPLETED', 'FAILED', 'CANCELLED')
       or p_committed_before_tool_yn not in ('Y', 'N')
       or p_continuation_recovery_yn not in ('Y', 'N')
       or length(trim(p_reason_code)) > 100
       or length(trim(p_stream_health_state)) > 100
       or length(trim(p_final_invocation_id)) > 128
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    begin
      select user_id
        into l_user_id
        from orac_api.users_v
       where username = trim(p_username);
    exception
      when no_data_found then
        l_user_id := null;
    end;

    select json_object(
             'schema_version' value 1,
             'retrieval_domain' value l_domain,
             'tool_mode' value l_mode,
             'tool_timing' value l_timing,
             'stream_health_state' value substr(trim(p_stream_health_state), 1, 100),
             'committed_before_tool_yn' value p_committed_before_tool_yn,
             'continuation_recovery_yn' value p_continuation_recovery_yn,
             'final_invocation_id' value substr(trim(p_final_invocation_id), 1, 128)
             absent on null
             returning json
           )
      into l_detail_json
      from dual;

    if p_phase2c_detail_json is not null
    then
      if dbms_lob.getlength(p_phase2c_detail_json) > 8192
      then
        raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
      end if;
      select count(*)
        into l_json_valid
        from dual
       where p_phase2c_detail_json is json;
      if l_json_valid <> 1
      then
        raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
      end if;
      select json_mergepatch(
               l_detail_json,
               json_object(
                 'phase2c' value p_phase2c_detail_json format json
                 returning json
               )
               returning json
             )
        into l_detail_json
        from dual;
    end if;

    write_event(
      p_event_id, 'OUTCOME', p_username, l_user_id, null,
      'GOVERNED_RETRIEVAL', 'RETRIEVAL_DOMAIN', null,
      p_status_code, substr(trim(p_reason_code), 1, 100),
      null, null, null, null, null, p_duration_ms, l_detail_json
    );
  end record_governed_retrieval_event;
end knowledge_retrieval_api;
/
--rollback drop package body orac_code.knowledge_retrieval_api;
