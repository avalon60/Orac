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

  procedure add_event_for_source(
    p_source_object_id in number,
    p_event_type       in varchar2,
    p_event_message    in clob default null
  )
  is
  begin
    for req in (
      select ingestion_request_id
        from orac_api.knowledge_ingestion_requests_v
       where source_object_id = p_source_object_id
       order by ingestion_request_id
    )
    loop
      add_event(req.ingestion_request_id, p_event_type, p_event_message);
    end loop;
  end add_event_for_source;

  function vector_dimension(
    p_embedding_vector in clob
  ) return number
  is
    l_array   json_array_t;
    l_element json_element_t;
  begin
    l_array := json_array_t.parse(p_embedding_vector);
    for l_index in 0 .. l_array.get_size - 1
    loop
      l_element := l_array.get(l_index);
      if not l_element.is_number
      then
        return -1;
      end if;
    end loop;
    return l_array.get_size;
  exception
    when others then
      return -1;
  end vector_dimension;

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

  procedure assert_canonical_scope(
    p_scope_type in varchar2,
    p_scope_key  in varchar2
  )
  is
    l_status varchar2(100 char);
  begin
    l_status := orac_code.knowledge_scope_api.scope_status(
                  p_scope_type, p_scope_key
                );
    if l_status <> 'RAG_USAGE_SCOPE_ELIGIBLE'
    then
      raise_application_error(
        -20409,
        'Target knowledge scope is unknown, inactive, or not runtime eligible.'
      );
    end if;
  end assert_canonical_scope;

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

  function equivalent_storage_key(
    p_storage_key   in varchar2,
    p_content_sha256 in varchar2
  ) return boolean
  is
  begin
    return p_storage_key = 'sha256:' || p_content_sha256
        or p_storage_key = 'sha256/'
                           || substr(p_content_sha256, 1, 2)
                           || '/'
                           || substr(p_content_sha256, 3, 2)
                           || '/'
                           || p_content_sha256;
  end equivalent_storage_key;

  function text_differs(
    p_left  in varchar2,
    p_right in varchar2
  ) return boolean
  is
  begin
    return (p_left <> p_right)
        or (p_left is null and p_right is not null)
        or (p_left is not null and p_right is null);
  end text_differs;

  function number_differs(
    p_left  in number,
    p_right in number
  ) return boolean
  is
  begin
    return (p_left <> p_right)
        or (p_left is null and p_right is not null)
        or (p_left is not null and p_right is null);
  end number_differs;

  function timestamp_differs(
    p_left  in timestamp with time zone,
    p_right in timestamp with time zone
  ) return boolean
  is
  begin
    return (p_left <> p_right)
        or (p_left is null and p_right is not null)
        or (p_left is not null and p_right is null);
  end timestamp_differs;

  procedure calculate_utf8_identity(
    p_text      in clob,
    p_sha256    out varchar2,
    p_byte_size out number
  )
  is
    l_blob         blob;
    l_destination_offset integer := 1;
    l_source_offset integer := 1;
    l_language_context integer := dbms_lob.default_lang_ctx;
    l_warning      integer;
  begin
    dbms_lob.createtemporary(l_blob, true);
    dbms_lob.converttoblob(
      dest_lob     => l_blob,
      src_clob     => p_text,
      amount       => dbms_lob.lobmaxsize,
      dest_offset  => l_destination_offset,
      src_offset   => l_source_offset,
      blob_csid    => nls_charset_id('AL32UTF8'),
      lang_context => l_language_context,
      warning      => l_warning
    );
    if l_warning <> dbms_lob.no_warning
    then
      raise_application_error(-20427, 'Normalised Markdown UTF-8 conversion failed.');
    end if;
    p_byte_size := dbms_lob.getlength(l_blob);
    p_sha256 := lower(
      rawtohex(dbms_crypto.hash(l_blob, dbms_crypto.hash_sh256))
    );
    dbms_lob.freetemporary(l_blob);
  exception
    when others then
      if dbms_lob.istemporary(l_blob) = 1
      then
        dbms_lob.freetemporary(l_blob);
      end if;
      raise;
  end calculate_utf8_identity;

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
    p_source_modified_on       in timestamp with time zone default null,
    p_legacy_parent_source_reference in varchar2 default null,
    p_source_format_code        in varchar2 default null,
    p_normalised_markdown       in clob default null,
    p_normalised_text_sha256    in varchar2 default null,
    p_normalised_byte_size      in number default null,
    p_output_mime_type          in varchar2 default null,
    p_extractor_code            in varchar2 default null,
    p_extractor_version         in varchar2 default null,
    p_extraction_metadata_json  in clob default null,
    p_classification_tags_json  in clob default null
  ) return number
  is
    l_source_type          varchar2(50);
    l_source_reference     varchar2(700);
    l_content_sha256       varchar2(64);
    l_content_uri          varchar2(1000);
    l_mime_type            varchar2(255);
    l_scope_type           varchar2(50);
    l_scope_key            varchar2(200);
    l_knowledge_scope_id   number;
    l_source_object_id     number;
    l_document_id          number;
    l_document_version_id  number;
    l_existing_source_object_id number;
    l_existing_content_uri varchar2(1000);
    l_existing_mime_type varchar2(255);
    l_existing_original_filename varchar2(500);
    l_existing_byte_size number;
    l_existing_source_modified_on timestamp with time zone;
    l_existing_source_format_code varchar2(50);
    l_ingestion_request_id number;
    l_legacy_count         number;
    l_existing_count       number;
    l_extraction_id        number;
    l_tag_array            json_array_t;
    l_tag_count            number;
    l_tag_code             varchar2(100);
    l_tag_id               number;
    l_duplicate_count      number;
    l_existing_tag_count   number;
    l_tag_order            number;
    l_existing_extraction_count number;
    l_existing_text_sha256 varchar2(64);
    l_existing_extractor_code varchar2(100);
    l_existing_extractor_version varchar2(100);
    l_calculated_text_sha256 varchar2(64);
    l_calculated_byte_size number;
    l_metadata_object        json_object_t;
    l_metadata_keys          json_key_list;
    type tag_seen_type is table of boolean index by varchar2(100);
    l_seen_tags tag_seen_type;
    l_tag_element json_element_t;
    l_tag_link_row orac_api.knowledge_document_version_tags_v%rowtype;
  begin
    l_source_type := upper(normalised_required(p_source_type, 'Source type'));
    l_source_reference := normalised_required(p_source_reference, 'Source reference');
    l_content_sha256 := normalised_sha256(p_content_sha256, 'Content SHA-256');
    l_content_uri := normalised_required(p_content_uri, 'Content URI');
    if l_content_uri <> 'sha256:' || l_content_sha256
    then
      raise_application_error(
        -20428,
        'New managed content must use its canonical logical storage key.'
      );
    end if;
    l_mime_type := normalised_required(p_mime_type, 'MIME type');
    l_scope_type := normalised_scope(p_target_scope_type);
    l_scope_key := normalised_required(p_target_scope_key, 'Target scope key');
    assert_canonical_scope(l_scope_type, l_scope_key);
    l_knowledge_scope_id := orac_code.knowledge_scope_api.resolve_scope_id(
                              l_scope_type, l_scope_key
                            );

    if p_byte_size is null or p_byte_size < 0
    then
      raise_application_error(-20404, 'Byte size must be zero or greater.');
    end if;
    if p_normalised_markdown is not null
    then
      if p_normalised_byte_size is null
         or p_normalised_byte_size > 52428800
         or dbms_lob.getlength(p_normalised_markdown) = 0
      then
        raise_application_error(-20410, 'Normalised Markdown is empty or oversized.');
      end if;
      if p_output_mime_type <> 'text/markdown; charset=utf-8'
      then
        raise_application_error(-20411, 'Normalised output MIME type is invalid.');
      end if;
      if p_extractor_code not in (
           'dropbox_markdown_passthrough',
           'dropbox_text_to_markdown',
           'dropbox_pandoc_gfm'
         ) or p_extractor_version <> '1'
      then
        raise_application_error(-20412, 'Extractor identity is invalid.');
      end if;
      if dbms_lob.getlength(p_extraction_metadata_json) > 16384
      then
        raise_application_error(-20413, 'Extraction metadata is oversized.');
      end if;
      calculate_utf8_identity(
        p_normalised_markdown,
        l_calculated_text_sha256,
        l_calculated_byte_size
      );
      if l_calculated_text_sha256 <> p_normalised_text_sha256
         or l_calculated_byte_size <> p_normalised_byte_size
      then
        raise_application_error(-20423, 'Normalised Markdown identity is inconsistent.');
      end if;
      begin
        l_metadata_object := json_object_t.parse(p_extraction_metadata_json);
        if l_metadata_object.get_number('schema_version') <> 1
           or l_metadata_object.get_string('producer_plugin_id') <> 'drop_box'
           or l_metadata_object.get_string('source_format') <> p_source_format_code
        then
          raise_application_error(-20424, 'Extraction metadata does not match the handoff.');
        end if;
        l_metadata_keys := l_metadata_object.get_keys;
        for l_index in 1 .. l_metadata_keys.count
        loop
          if l_metadata_keys(l_index) not in (
               'schema_version',
               'producer_plugin_id',
               'drop_location_id',
               'drop_job_id',
               'source_format',
               'converter_name',
               'converter_version',
               'fixed_option_identifiers'
             )
          then
            raise_application_error(-20425, 'Extraction metadata contains unsupported fields.');
          end if;
        end loop;
      exception
        when others then
          if sqlcode between -20425 and -20424
          then
            raise;
          end if;
          raise_application_error(-20426, 'Extraction metadata must be a valid object.');
      end;
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
             knowledge_scope_id      = l_knowledge_scope_id
       where source_object_id = l_source_object_id;
    exception
      when no_data_found then
        select count(*)
          into l_existing_count
          from orac_api.knowledge_source_objects_v
         where source_type = l_source_type
           and source_reference = l_source_reference;

        if l_existing_count > 0
        then
          raise_application_error(-20407, 'Stable source reference collision detected.');
        end if;

        if l_source_type = 'DROP_BOX'
           and p_legacy_parent_source_reference is not null
        then
          select count(*),
                 min(source_object_id)
            into l_legacy_count,
                 l_source_object_id
            from orac_api.knowledge_source_objects_v
           where source_type = l_source_type
             and source_reference like 'drop_box:drop_job:%'
             and knowledge_scope_id = l_knowledge_scope_id
             and parent_source_reference in (
                   p_parent_source_reference,
                   p_legacy_parent_source_reference
                 );

          if l_legacy_count = 1
          then
            update orac_api.knowledge_source_objects_v
               set source_reference        = l_source_reference,
                   parent_source_reference = p_parent_source_reference,
                   knowledge_scope_id      = l_knowledge_scope_id
             where source_object_id = l_source_object_id;

            add_event_for_source(
              l_source_object_id,
              'source_rekeyed',
              'Conservatively re-keyed legacy Drop Box job source to stable source identity.'
            );
          elsif l_legacy_count > 1
          then
            raise_application_error(-20408, 'Ambiguous legacy Drop Box source identity; refusing re-key.');
          end if;
        else
          l_legacy_count := 0;
        end if;

        if l_legacy_count = 0
        then
          insert into orac_api.knowledge_source_objects_v (
            source_type,
            source_reference,
            parent_source_reference,
            knowledge_scope_id
          )
          values (
            l_source_type,
            l_source_reference,
            p_parent_source_reference,
            l_knowledge_scope_id
          )
          returning source_object_id into l_source_object_id;
        end if;
    end;

    begin
      select document_id
        into l_document_id
        from orac_api.knowledge_documents_v
       where source_object_id = l_source_object_id
         for update;

      update orac_api.knowledge_documents_v
         set title = coalesce(p_original_filename, title)
       where document_id = l_document_id;
    exception
      when no_data_found then
        insert into orac_api.knowledge_documents_v (
          source_object_id,
          title
        )
        values (
          l_source_object_id,
          p_original_filename
        )
        returning document_id into l_document_id;
    end;

    begin
      select document_version_id,
             source_object_id,
             content_uri,
             mime_type,
             original_filename,
             byte_size,
             source_modified_on,
             source_format_code
        into l_document_version_id,
             l_existing_source_object_id,
             l_existing_content_uri,
             l_existing_mime_type,
             l_existing_original_filename,
             l_existing_byte_size,
             l_existing_source_modified_on,
             l_existing_source_format_code
        from orac_api.knowledge_document_versions_v
       where document_id = l_document_id
         and content_sha256 = l_content_sha256
         for update;

      if l_existing_source_object_id <> l_source_object_id
         or not equivalent_storage_key(
                  l_existing_content_uri,
                  l_content_sha256
                )
         or text_differs(l_existing_mime_type, l_mime_type)
         or text_differs(l_existing_original_filename, p_original_filename)
         or number_differs(l_existing_byte_size, p_byte_size)
         or timestamp_differs(
              l_existing_source_modified_on,
              p_source_modified_on
            )
         or text_differs(
              l_existing_source_format_code,
              p_source_format_code
            )
      then
        raise_application_error(
          -20429,
          'Immutable raw document-version metadata conflicts with the existing version.'
        );
      end if;
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
          , source_format_code
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
          , p_source_format_code
        )
        returning document_version_id into l_document_version_id;
    end;

    update orac_api.knowledge_documents_v
       set current_document_version_id = l_document_version_id
     where document_id = l_document_id;

    if p_normalised_markdown is not null
    then
      select count(*),
             min(text_sha256),
             min(extractor_code),
             min(extractor_version)
        into l_existing_extraction_count,
             l_existing_text_sha256,
             l_existing_extractor_code,
             l_existing_extractor_version
        from orac_api.knowledge_extractions_v
       where document_version_id = l_document_version_id;
      if l_existing_extraction_count > 0
         and (
           l_existing_text_sha256 <> p_normalised_text_sha256
           or l_existing_extractor_code <> p_extractor_code
           or l_existing_extractor_version <> p_extractor_version
         )
      then
        raise_application_error(
          -20420,
          'Idempotency conflict: canonical extraction does not match.'
        );
      end if;
      l_extraction_id := create_extraction(
        l_document_version_id,
        p_extractor_code,
        p_extractor_version,
        p_normalised_markdown,
        p_normalised_text_sha256,
        p_output_mime_type,
        p_extraction_metadata_json
      );
    end if;

    if p_classification_tags_json is not null
    then
      if dbms_lob.getlength(p_classification_tags_json) > 4096
      then
        raise_application_error(-20414, 'Classification tag JSON is oversized.');
      end if;
      begin
        l_tag_array := json_array_t.parse(p_classification_tags_json);
      exception when others then
        raise_application_error(-20415, 'Classification tags must be a JSON array.');
      end;
      l_tag_count := l_tag_array.get_size;
      if l_source_type = 'DROP_BOX' and l_tag_count = 0
      then
        raise_application_error(-20416, 'Drop Box requires at least one classification tag.');
      end if;
      if l_tag_count > 10
      then
        raise_application_error(-20417, 'No more than ten classification tags are allowed.');
      end if;
      if l_tag_count > 0
      then
        for l_index in 0 .. l_tag_count - 1
        loop
          l_tag_element := l_tag_array.get(l_index);
          if l_tag_element is null or not l_tag_element.is_string
          then
            raise_application_error(-20418, 'Classification tag entries must be strings.');
          end if;
          l_tag_code := l_tag_array.get_string(l_index);
          if l_seen_tags.exists(l_tag_code)
          then
            raise_application_error(-20421, 'Duplicate classification tags are not allowed.');
          end if;
          l_seen_tags(l_tag_code) := true;
          select count(*)
            into l_duplicate_count
            from orac_api.knowledge_tags_v
           where tag_code = l_tag_code
             and active_yn = 'Y';
          if l_duplicate_count <> 1
          then
            raise_application_error(-20419, 'Classification tag is unknown or inactive.');
          end if;
        end loop;
      end if;

      select count(*)
        into l_existing_tag_count
        from orac_api.knowledge_document_version_tags_v
       where document_version_id = l_document_version_id;
      if l_existing_tag_count not in (0, l_tag_count)
      then
        raise_application_error(
          -20422,
          'Idempotency conflict: classification tags do not match.'
        );
      end if;

      l_tag_order := 0;
      for tag_rec in (
        select tag.knowledge_tag_id
          from orac_api.knowledge_tags_v tag
          join json_table(
                 p_classification_tags_json,
                 '$[*]' columns (
                   tag_code varchar2(100) path '$'
                 )
               ) selected
            on selected.tag_code = tag.tag_code
         order by tag.sort_order, tag.tag_code
      )
      loop
        l_tag_order := l_tag_order + 1;
        if l_existing_tag_count = 0
        then
          l_tag_link_row.document_version_id := l_document_version_id;
          l_tag_link_row.knowledge_tag_id := tag_rec.knowledge_tag_id;
          l_tag_link_row.tag_order := l_tag_order;
          orac_api.knowledge_document_version_tags_tapi.ins(l_tag_link_row);
        else
          select count(*)
            into l_duplicate_count
            from orac_api.knowledge_document_version_tags_v
           where document_version_id = l_document_version_id
             and knowledge_tag_id = tag_rec.knowledge_tag_id
             and tag_order = l_tag_order;
          if l_duplicate_count <> 1
          then
            raise_application_error(
              -20422,
              'Idempotency conflict: classification tags do not match.'
            );
          end if;
        end if;
      end loop;
    elsif p_processing_profile_code is not null
    then
      begin
        select knowledge_tag_id into l_tag_id
          from orac_api.knowledge_tags_v
         where tag_code = p_processing_profile_code and active_yn = 'Y';
        l_tag_link_row.document_version_id := l_document_version_id;
        l_tag_link_row.knowledge_tag_id := l_tag_id;
        l_tag_link_row.tag_order := 1;
        orac_api.knowledge_document_version_tags_tapi.ins(l_tag_link_row);
      exception when dup_val_on_index then null;
               when no_data_found then
                 raise_application_error(-20419, 'Legacy profile tag is unknown or inactive.');
      end;
    end if;

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
    l_source_modified_on  timestamp with time zone;
  begin
    select req.document_id,
           req.document_version_id,
           docver.source_modified_on
      into l_document_id,
           l_document_version_id,
           l_source_modified_on
      from orac_api.knowledge_ingestion_requests_v req
      join orac_api.knowledge_document_versions_v docver
        on docver.document_version_id = req.document_version_id
     where req.ingestion_request_id = p_ingestion_request_id;

    if timestamp_differs(l_source_modified_on, p_source_modified_on)
    then
      raise_application_error(
        -20429,
        'Immutable raw document-version metadata conflicts with the request.'
      );
    end if;

    update orac_api.knowledge_documents_v
       set title = coalesce(p_title, title),
           current_document_version_id = l_document_version_id
     where document_id = l_document_id;

    return l_document_version_id;
  end ensure_document_version;

  function create_extraction(
    p_document_version_id in number,
    p_extractor_code      in varchar2,
    p_extractor_version   in varchar2,
    p_extracted_text      in clob,
    p_text_sha256         in varchar2,
    p_output_mime_type    in varchar2 default null,
    p_extractor_metadata_json in clob default null
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
        , output_mime_type
        , extractor_metadata_json
      )
      values (
        p_document_version_id,
        l_extractor_code,
        l_extractor_version,
        l_text_sha256,
        p_extracted_text
        , p_output_mime_type
        , p_extractor_metadata_json
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
    p_content_sha256  in varchar2,
    p_chunk_metadata_json in clob default null
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
        , chunk_metadata_json
      )
      values (
        p_chunk_set_id,
        p_chunk_no,
        p_span_start,
        p_span_end,
        p_chunk_text,
        p_token_count,
        l_content_sha256
        , p_chunk_metadata_json
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
    l_request_count          number;
    l_chunk_count            number := 0;
    l_embedding_count        number := 0;
    l_missing_embedding_count number := 0;
    l_bad_chunk_count        number := 0;
    l_bad_vector_count       number := 0;
    l_model_key              varchar2(600);
    l_expected_model_key     varchar2(600);
  begin
    assert_lease(p_ingestion_request_id, p_owner_id, p_lease_token);

    select count(*)
      into l_request_count
      from orac_api.knowledge_ingestion_requests_v req
      join orac_api.knowledge_documents_v doc
        on doc.document_id = req.document_id
      join orac_api.knowledge_document_versions_v ver
        on ver.document_version_id = req.document_version_id
       and ver.document_id = doc.document_id
     where req.ingestion_request_id = p_ingestion_request_id;

    if l_request_count <> 1
    then
      raise_application_error(-20406, 'Cannot complete a knowledge request without a valid document and revision.');
    end if;

    for rec in (
      select chn.chunk_id,
             chn.chunk_text,
             emb.chunk_embedding_id,
             emb.embedding_vector,
             modl.provider_code,
             modl.model_name,
             modl.model_revision,
             modl.dimensions
        from orac_api.knowledge_ingestion_requests_v req
        join orac_api.knowledge_extractions_v ext
          on ext.document_version_id = req.document_version_id
        join orac_api.knowledge_chunk_sets_v chs
          on chs.extraction_id = ext.extraction_id
        join orac_api.knowledge_chunks_v chn
          on chn.chunk_set_id = chs.chunk_set_id
        left join orac_api.knowledge_chunk_embeddings_v emb
          on emb.chunk_id = chn.chunk_id
        left join orac_api.knowledge_embedding_models_v modl
          on modl.embedding_model_id = emb.embedding_model_id
       where req.ingestion_request_id = p_ingestion_request_id
       order by chn.chunk_id
    )
    loop
      l_chunk_count := l_chunk_count + 1;
      if rec.chunk_text is null
         or dbms_lob.getlength(rec.chunk_text) = 0
         or trim(dbms_lob.substr(rec.chunk_text, 4000, 1)) is null
      then
        l_bad_chunk_count := l_bad_chunk_count + 1;
      end if;

      if rec.chunk_embedding_id is null
      then
        l_missing_embedding_count := l_missing_embedding_count + 1;
      else
        l_embedding_count := l_embedding_count + 1;
        l_model_key := rec.provider_code || ':' || rec.model_name || ':'
          || rec.model_revision || ':' || to_char(rec.dimensions);
        if l_expected_model_key is null
        then
          l_expected_model_key := l_model_key;
        elsif l_expected_model_key <> l_model_key
        then
          l_bad_vector_count := l_bad_vector_count + 1;
        end if;

        if rec.dimensions is null
           or vector_dimension(rec.embedding_vector) <> rec.dimensions
        then
          l_bad_vector_count := l_bad_vector_count + 1;
        end if;
      end if;
    end loop;

    if l_chunk_count = 0
    then
      raise_application_error(-20409, 'Cannot complete a knowledge request without searchable chunks.');
    elsif l_bad_chunk_count > 0
    then
      raise_application_error(-20410, 'Cannot complete a knowledge request with empty or whitespace-only chunks.');
    elsif l_missing_embedding_count > 0 or l_embedding_count <> l_chunk_count
    then
      raise_application_error(-20411, 'Cannot complete a knowledge request until every searchable chunk has an embedding.');
    elsif l_bad_vector_count > 0 or l_expected_model_key is null
    then
      raise_application_error(-20412, 'Cannot complete a knowledge request with inconsistent or malformed chunk embeddings.');
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
