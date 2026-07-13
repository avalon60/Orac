--liquibase formatted sql

--changeset clive:create_package_body_orac_code_knowledge_ingestion_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.knowledge_ingestion_api
as
  c_status_queued     constant varchar2(50) := 'QUEUED';
  c_status_processing constant varchar2(50) := 'PROCESSING';
  c_status_retry_wait constant varchar2(50) := 'RETRY_WAIT';
  c_status_completed  constant varchar2(50) := 'COMPLETED';
  c_status_failed     constant varchar2(50) := 'FAILED';

  procedure add_event(
    p_ingestion_request_id in number,
    p_event_type           in varchar2,
    p_event_message        in clob default null
  )
  is
  begin
    insert into orac_api.knowledge_ingestion_events_v (
      ingestion_request_id,
      event_type,
      event_message
    )
    values (
      p_ingestion_request_id,
      p_event_type,
      p_event_message
    );
  end add_event;

  function normalised_scope(
    p_scope_type in varchar2
  ) return varchar2
  is
    l_scope_type varchar2(50);
  begin
    l_scope_type := upper(trim(p_scope_type));
    if l_scope_type not in ('PROJECT', 'PLUGIN')
    then
      raise_application_error(-20400, 'Target scope type must be PROJECT or PLUGIN.');
    end if;
    return l_scope_type;
  end normalised_scope;

  function normalised_required(
    p_value in varchar2,
    p_name  in varchar2
  ) return varchar2
  is
    l_value varchar2(4000);
  begin
    l_value := trim(p_value);
    if l_value is null
    then
      raise_application_error(-20401, p_name || ' is required.');
    end if;
    return l_value;
  end normalised_required;

  function normalised_sha256(
    p_value in varchar2,
    p_name  in varchar2
  ) return varchar2
  is
    l_value varchar2(64);
  begin
    l_value := lower(trim(p_value));
    if not regexp_like(l_value, '^[0-9a-f]{64}$')
    then
      raise_application_error(-20402, p_name || ' must be a lowercase SHA-256 hash.');
    end if;
    return l_value;
  end normalised_sha256;

  procedure assert_lease(
    p_ingestion_request_id in number,
    p_owner_id             in varchar2,
    p_lease_token          in varchar2
  )
  is
    l_count number;
  begin
    select count(*)
      into l_count
      from orac_api.knowledge_ingestion_requests_v req
     where req.ingestion_request_id = p_ingestion_request_id
       and req.status_code = c_status_processing
       and req.lease_owner = p_owner_id
       and req.lease_token = p_lease_token
       and req.lease_expires_on > systimestamp;

    if l_count = 0
    then
      raise_application_error(-20403, 'Knowledge ingestion request lease is not active.');
    end if;
  end assert_lease;

  function submit_managed_file(
    p_source_type              in varchar2,
    p_source_reference         in varchar2,
    p_parent_source_reference  in varchar2,
    p_content_sha256           in varchar2,
    p_content_uri              in varchar2,
    p_mime_type                in varchar2,
    p_original_filename        in varchar2,
    p_byte_size                in number,
    p_target_scope_type        in varchar2,
    p_target_scope_key         in varchar2,
    p_processing_profile_code  in varchar2 default null,
    p_processing_instruction   in clob default null,
    p_source_modified_on       in timestamp with time zone default null
  ) return number
  is
    l_source_type          varchar2(50);
    l_source_reference     varchar2(700);
    l_content_sha256       varchar2(64);
    l_content_uri          varchar2(1000);
    l_mime_type            varchar2(255);
    l_scope_type           varchar2(50);
    l_scope_key            varchar2(200);
    l_source_object_id     number;
    l_document_id          number;
    l_document_version_id  number;
    l_ingestion_request_id number;
  begin
    l_source_type := upper(normalised_required(p_source_type, 'Source type'));
    l_source_reference := normalised_required(p_source_reference, 'Source reference');
    l_content_sha256 := normalised_sha256(p_content_sha256, 'Content SHA-256');
    l_content_uri := normalised_required(p_content_uri, 'Content URI');
    l_mime_type := normalised_required(p_mime_type, 'MIME type');
    l_scope_type := normalised_scope(p_target_scope_type);
    l_scope_key := normalised_required(p_target_scope_key, 'Target scope key');

    if p_byte_size is null or p_byte_size < 0
    then
      raise_application_error(-20404, 'Byte size must be zero or greater.');
    end if;

    begin
      select source_object_id
        into l_source_object_id
        from orac_api.knowledge_source_objects_v
       where source_type = l_source_type
         and source_reference = l_source_reference
         for update;

      update orac_api.knowledge_source_objects_v
         set parent_source_reference = p_parent_source_reference,
             target_scope_type       = l_scope_type,
             target_scope_key        = l_scope_key
       where source_object_id = l_source_object_id;
    exception
      when no_data_found then
        insert into orac_api.knowledge_source_objects_v (
          source_type,
          source_reference,
          parent_source_reference,
          target_scope_type,
          target_scope_key
        )
        values (
          l_source_type,
          l_source_reference,
          p_parent_source_reference,
          l_scope_type,
          l_scope_key
        )
        returning source_object_id into l_source_object_id;
    end;

    begin
      select document_id
        into l_document_id
        from orac_api.knowledge_documents_v
       where source_object_id = l_source_object_id
         for update;

      update orac_api.knowledge_documents_v
         set target_scope_type = l_scope_type,
             target_scope_key  = l_scope_key,
             title             = coalesce(p_original_filename, title)
       where document_id = l_document_id;
    exception
      when no_data_found then
        insert into orac_api.knowledge_documents_v (
          source_object_id,
          target_scope_type,
          target_scope_key,
          title
        )
        values (
          l_source_object_id,
          l_scope_type,
          l_scope_key,
          p_original_filename
        )
        returning document_id into l_document_id;
    end;

    begin
      select document_version_id
        into l_document_version_id
        from orac_api.knowledge_document_versions_v
       where document_id = l_document_id
         and content_sha256 = l_content_sha256
         for update;

      update orac_api.knowledge_document_versions_v
         set content_uri        = l_content_uri,
             mime_type          = l_mime_type,
             original_filename  = p_original_filename,
             byte_size          = p_byte_size,
             source_modified_on = coalesce(p_source_modified_on, source_modified_on)
       where document_version_id = l_document_version_id;
    exception
      when no_data_found then
        insert into orac_api.knowledge_document_versions_v (
          document_id,
          source_object_id,
          content_sha256,
          content_uri,
          mime_type,
          original_filename,
          byte_size,
          source_modified_on
        )
        values (
          l_document_id,
          l_source_object_id,
          l_content_sha256,
          l_content_uri,
          l_mime_type,
          p_original_filename,
          p_byte_size,
          p_source_modified_on
        )
        returning document_version_id into l_document_version_id;
    end;

    update orac_api.knowledge_documents_v
       set current_document_version_id = l_document_version_id
     where document_id = l_document_id;

    begin
      select ingestion_request_id
        into l_ingestion_request_id
        from orac_api.knowledge_ingestion_requests_v
       where source_object_id = l_source_object_id
         and document_version_id = l_document_version_id;
      return l_ingestion_request_id;
    exception
      when no_data_found then
        insert into orac_api.knowledge_ingestion_requests_v (
          source_object_id,
          document_id,
          document_version_id,
          processing_profile_code,
          processing_instruction,
          status_code,
          stage_code
        )
        values (
          l_source_object_id,
          l_document_id,
          l_document_version_id,
          p_processing_profile_code,
          p_processing_instruction,
          c_status_queued,
          'SUBMITTED'
        )
        returning ingestion_request_id into l_ingestion_request_id;
        add_event(
          l_ingestion_request_id,
          'submitted',
          'Managed file accepted for Core knowledge ingestion.'
        );
        return l_ingestion_request_id;
    end;
  end submit_managed_file;

  function try_claim_next_request(
    p_owner_id      in varchar2,
    p_lease_seconds in number default 300
  ) return number
  is
    l_lease_token varchar2(64);
    l_owner_id    varchar2(500);
  begin
    l_owner_id := normalised_required(p_owner_id, 'Owner id');
    for rec in (
      select ingestion_request_id
        from orac_api.knowledge_ingestion_requests_v
       where status_code = c_status_queued
          or (status_code = c_status_retry_wait and next_attempt_on <= systimestamp)
          or (status_code = c_status_processing and lease_expires_on <= systimestamp)
       order by created_on, ingestion_request_id
       for update skip locked
    )
    loop
      l_lease_token := lower(rawtohex(sys_guid()));
      update orac_api.knowledge_ingestion_requests_v
         set status_code      = c_status_processing,
             stage_code       = 'CLAIMED',
             attempts         = attempts + 1,
             lease_owner      = l_owner_id,
             lease_token      = l_lease_token,
             lease_expires_on = systimestamp + numtodsinterval(greatest(30, nvl(p_lease_seconds, 300)), 'second'),
             last_error_code  = null,
             last_error_message = null
       where ingestion_request_id = rec.ingestion_request_id;

      add_event(rec.ingestion_request_id, 'claimed', 'Core worker claimed ingestion request.');
      return rec.ingestion_request_id;
    end loop;
    return null;
  end try_claim_next_request;

  procedure mark_stage(
    p_ingestion_request_id in number,
    p_owner_id             in varchar2,
    p_lease_token          in varchar2,
    p_status_code          in varchar2,
    p_stage_code           in varchar2
  )
  is
    l_status_code varchar2(50);
    l_stage_code  varchar2(50);
  begin
    assert_lease(p_ingestion_request_id, p_owner_id, p_lease_token);
    l_status_code := upper(trim(p_status_code));
    l_stage_code := upper(trim(p_stage_code));
    if l_status_code <> c_status_processing
    then
      raise_application_error(-20405, 'Worker stage updates must remain PROCESSING.');
    end if;

    update orac_api.knowledge_ingestion_requests_v
       set status_code = l_status_code,
           stage_code  = l_stage_code
     where ingestion_request_id = p_ingestion_request_id;

    add_event(p_ingestion_request_id, lower(l_stage_code), 'Core worker entered ' || l_stage_code || ' stage.');
  end mark_stage;

  function ensure_document_version(
    p_ingestion_request_id in number,
    p_title                in varchar2 default null,
    p_source_modified_on   in timestamp with time zone default null
  ) return number
  is
    l_document_id         number;
    l_document_version_id number;
  begin
    select document_id,
           document_version_id
      into l_document_id,
           l_document_version_id
      from orac_api.knowledge_ingestion_requests_v
     where ingestion_request_id = p_ingestion_request_id;

    update orac_api.knowledge_documents_v
       set title = coalesce(p_title, title),
           current_document_version_id = l_document_version_id
     where document_id = l_document_id;

    update orac_api.knowledge_document_versions_v
       set source_modified_on = coalesce(p_source_modified_on, source_modified_on)
     where document_version_id = l_document_version_id;

    return l_document_version_id;
  end ensure_document_version;

  function create_extraction(
    p_document_version_id in number,
    p_extractor_code      in varchar2,
    p_extractor_version   in varchar2,
    p_extracted_text      in clob,
    p_text_sha256         in varchar2
  ) return number
  is
    l_extraction_id number;
    l_text_sha256   varchar2(64);
    l_extractor_code varchar2(100);
    l_extractor_version varchar2(100);
  begin
    l_text_sha256 := normalised_sha256(p_text_sha256, 'Text SHA-256');
    l_extractor_code := normalised_required(p_extractor_code, 'Extractor code');
    l_extractor_version := normalised_required(p_extractor_version, 'Extractor version');
    begin
      insert into orac_api.knowledge_extractions_v (
        document_version_id,
        extractor_code,
        extractor_version,
        text_sha256,
        extracted_text
      )
      values (
        p_document_version_id,
        l_extractor_code,
        l_extractor_version,
        l_text_sha256,
        p_extracted_text
      )
      returning extraction_id into l_extraction_id;
    exception
      when dup_val_on_index then
        select extraction_id
          into l_extraction_id
          from orac_api.knowledge_extractions_v
         where document_version_id = p_document_version_id
           and extractor_code = l_extractor_code
           and extractor_version = l_extractor_version
           and text_sha256 = l_text_sha256;
    end;
    return l_extraction_id;
  end create_extraction;

  function create_chunk_set(
    p_extraction_id      in number,
    p_chunker_code       in varchar2,
    p_chunker_version    in varchar2,
    p_chunk_size_tokens  in number,
    p_overlap_tokens     in number
  ) return number
  is
    l_chunk_set_id number;
    l_chunker_code varchar2(100);
    l_chunker_version varchar2(100);
  begin
    l_chunker_code := normalised_required(p_chunker_code, 'Chunker code');
    l_chunker_version := normalised_required(p_chunker_version, 'Chunker version');
    begin
      insert into orac_api.knowledge_chunk_sets_v (
        extraction_id,
        chunker_code,
        chunker_version,
        chunk_size_tokens,
        overlap_tokens
      )
      values (
        p_extraction_id,
        l_chunker_code,
        l_chunker_version,
        p_chunk_size_tokens,
        p_overlap_tokens
      )
      returning chunk_set_id into l_chunk_set_id;
    exception
      when dup_val_on_index then
        select chunk_set_id
          into l_chunk_set_id
          from orac_api.knowledge_chunk_sets_v
         where extraction_id = p_extraction_id
           and chunker_code = l_chunker_code
           and chunker_version = l_chunker_version
           and chunk_size_tokens = p_chunk_size_tokens
           and overlap_tokens = p_overlap_tokens;
    end;
    return l_chunk_set_id;
  end create_chunk_set;

  function insert_chunk(
    p_chunk_set_id    in number,
    p_chunk_no        in number,
    p_span_start      in number,
    p_span_end        in number,
    p_chunk_text      in clob,
    p_token_count     in number,
    p_content_sha256  in varchar2
  ) return number
  is
    l_chunk_id number;
    l_content_sha256 varchar2(64);
  begin
    l_content_sha256 := normalised_sha256(p_content_sha256, 'Chunk content SHA-256');
    begin
      insert into orac_api.knowledge_chunks_v (
        chunk_set_id,
        chunk_no,
        span_start,
        span_end,
        chunk_text,
        token_count,
        content_sha256
      )
      values (
        p_chunk_set_id,
        p_chunk_no,
        p_span_start,
        p_span_end,
        p_chunk_text,
        p_token_count,
        l_content_sha256
      )
      returning chunk_id into l_chunk_id;
    exception
      when dup_val_on_index then
        select chunk_id
          into l_chunk_id
          from orac_api.knowledge_chunks_v
         where chunk_set_id = p_chunk_set_id
           and chunk_no = p_chunk_no;
    end;
    return l_chunk_id;
  end insert_chunk;

  function upsert_embedding_model(
    p_provider_code    in varchar2,
    p_model_name       in varchar2,
    p_model_revision   in varchar2,
    p_dimensions       in number,
    p_distance_metric  in varchar2 default 'COSINE',
    p_normalisation    in varchar2 default 'UNIT'
  ) return number
  is
    l_embedding_model_id number;
    l_provider_code      varchar2(100);
    l_model_name         varchar2(255);
    l_model_revision     varchar2(100);
    l_distance_metric    varchar2(50) := upper(normalised_required(p_distance_metric, 'Distance metric'));
    l_normalisation      varchar2(50) := upper(normalised_required(p_normalisation, 'Normalisation'));
  begin
    l_provider_code := lower(normalised_required(p_provider_code, 'Provider code'));
    l_model_name := normalised_required(p_model_name, 'Model name');
    l_model_revision := normalised_required(p_model_revision, 'Model revision');
    begin
      insert into orac_api.knowledge_embedding_models_v (
        provider_code,
        model_name,
        model_revision,
        dimensions,
        distance_metric,
        normalisation
      )
      values (
        l_provider_code,
        l_model_name,
        l_model_revision,
        p_dimensions,
        l_distance_metric,
        l_normalisation
      )
      returning embedding_model_id into l_embedding_model_id;
    exception
      when dup_val_on_index then
        select embedding_model_id
          into l_embedding_model_id
          from orac_api.knowledge_embedding_models_v
         where provider_code = l_provider_code
           and model_name = l_model_name
           and model_revision = l_model_revision
           and dimensions = p_dimensions
           and distance_metric = l_distance_metric
           and normalisation = l_normalisation;
    end;
    return l_embedding_model_id;
  end upsert_embedding_model;

  function insert_chunk_embedding(
    p_chunk_id              in number,
    p_embedding_model_id    in number,
    p_embedding_vector      in clob,
    p_embedding_text_sha256 in varchar2
  ) return number
  is
    l_chunk_embedding_id number;
    l_embedding_sha      varchar2(64);
  begin
    l_embedding_sha := normalised_sha256(p_embedding_text_sha256, 'Embedding text SHA-256');
    begin
      insert into orac_api.knowledge_chunk_embeddings_v (
        chunk_id,
        embedding_model_id,
        embedding_vector,
        embedding_text_sha256
      )
      values (
        p_chunk_id,
        p_embedding_model_id,
        p_embedding_vector,
        l_embedding_sha
      )
      returning chunk_embedding_id into l_chunk_embedding_id;
    exception
      when dup_val_on_index then
        select chunk_embedding_id
          into l_chunk_embedding_id
          from orac_api.knowledge_chunk_embeddings_v
         where chunk_id = p_chunk_id
           and embedding_model_id = p_embedding_model_id
           and embedding_text_sha256 = l_embedding_sha;
    end;
    return l_chunk_embedding_id;
  end insert_chunk_embedding;

  procedure complete_request(
    p_ingestion_request_id in number,
    p_owner_id             in varchar2,
    p_lease_token          in varchar2
  )
  is
    l_embedding_count number;
  begin
    assert_lease(p_ingestion_request_id, p_owner_id, p_lease_token);

    select count(*)
      into l_embedding_count
      from orac_api.knowledge_ingestion_requests_v req
      join orac_api.knowledge_extractions_v ext
        on ext.document_version_id = req.document_version_id
      join orac_api.knowledge_chunk_sets_v chs
        on chs.extraction_id = ext.extraction_id
      join orac_api.knowledge_chunks_v chn
        on chn.chunk_set_id = chs.chunk_set_id
      join orac_api.knowledge_chunk_embeddings_v emb
        on emb.chunk_id = chn.chunk_id
     where req.ingestion_request_id = p_ingestion_request_id;

    if l_embedding_count = 0
    then
      raise_application_error(-20406, 'Cannot complete a knowledge request without at least one chunk embedding.');
    end if;

    update orac_api.knowledge_ingestion_requests_v
       set status_code        = c_status_completed,
           stage_code         = 'COMPLETED',
           lease_owner        = null,
           lease_token        = null,
           lease_expires_on   = null,
           completed_on       = systimestamp,
           last_error_code    = null,
           last_error_message = null
     where ingestion_request_id = p_ingestion_request_id;

    add_event(p_ingestion_request_id, 'completed', 'Core knowledge ingestion completed.');
  end complete_request;

  procedure fail_request(
    p_ingestion_request_id in number,
    p_owner_id             in varchar2,
    p_lease_token          in varchar2,
    p_error_code           in varchar2,
    p_error_message        in clob,
    p_retryable_yn         in varchar2 default 'Y'
  )
  is
    l_attempts     number;
    l_max_attempts number;
    l_retryable    boolean;
    l_status_code  varchar2(50);
    l_stage_code   varchar2(50);
    l_delay_secs   number;
  begin
    assert_lease(p_ingestion_request_id, p_owner_id, p_lease_token);

    select attempts,
           max_attempts
      into l_attempts,
           l_max_attempts
      from orac_api.knowledge_ingestion_requests_v
     where ingestion_request_id = p_ingestion_request_id;

    l_retryable := upper(coalesce(p_retryable_yn, 'N')) = 'Y' and l_attempts < l_max_attempts;
    if l_retryable
    then
      l_status_code := c_status_retry_wait;
      l_stage_code := 'RETRY_WAIT';
      l_delay_secs := least(3600, power(2, greatest(0, l_attempts - 1)) * 30);
    else
      l_status_code := c_status_failed;
      l_stage_code := 'FAILED';
      l_delay_secs := null;
    end if;

    update orac_api.knowledge_ingestion_requests_v
       set status_code        = l_status_code,
           stage_code         = l_stage_code,
           next_attempt_on    = case
                                  when l_retryable then systimestamp + numtodsinterval(l_delay_secs, 'second')
                                  else next_attempt_on
                                end,
           lease_owner        = null,
           lease_token        = null,
           lease_expires_on   = null,
           last_error_code    = p_error_code,
           last_error_message = p_error_message
     where ingestion_request_id = p_ingestion_request_id;

    add_event(
      p_ingestion_request_id,
      case when l_retryable then 'retry_wait' else 'failed' end,
      p_error_message
    );
  end fail_request;
end knowledge_ingestion_api;
/

--rollback drop package body orac_code.knowledge_ingestion_api;
