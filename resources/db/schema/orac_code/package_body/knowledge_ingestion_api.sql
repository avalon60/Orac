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

  procedure append_conflicting_field(
    p_conflicting_fields in out nocopy varchar2,
    p_field_name         in varchar2
  )
  is
  begin
    if p_conflicting_fields is null
    then
      p_conflicting_fields := p_field_name;
    else
      p_conflicting_fields := p_conflicting_fields || ', ' || p_field_name;
    end if;
  end append_conflicting_field;

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
       and exists (
         select 1 from orac_api.knowledge_source_objects_v src
          where src.source_object_id = req.source_object_id
            and orac_code.knowledge_scope_api.scope_status_by_id(src.knowledge_scope_id) = 'RAG_USAGE_SCOPE_ELIGIBLE'
       )
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
    p_target_knowledge_scope_id in number default null,
    p_source_format_code        in varchar2 default null,
    p_normalised_markdown       in clob default null,
    p_normalised_text_sha256    in varchar2 default null,
    p_normalised_byte_size      in number default null,
    p_output_mime_type          in varchar2 default null,
    p_extractor_code            in varchar2 default null,
    p_extractor_version         in varchar2 default null,
    p_extraction_metadata_json  in clob default null,
    p_classification_tags_json  in clob default null,
    p_output_set_json           in clob default null
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
    l_conflicting_fields  varchar2(1000);
    l_ingestion_request_id number;
    l_existing_count       number;
    l_extraction_id        number;
    l_tag_array            json_array_t;
    l_tag_count            number;
    l_classification_code  varchar2(100);
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
    l_output_set_result      clob;
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
    if (l_source_type = 'DROP_BOX' and p_target_knowledge_scope_id is null)
       or (p_target_knowledge_scope_id is not null
           and (p_target_knowledge_scope_id <> l_knowledge_scope_id
                or orac_code.knowledge_scope_api.scope_status_by_id(
                     p_target_knowledge_scope_id
                   ) <> 'RAG_USAGE_SCOPE_ELIGIBLE'))
    then
      raise_application_error(-20409, 'Pinned knowledge scope is not eligible.');
    end if;
    if p_target_knowledge_scope_id is not null
    then
      l_knowledge_scope_id := p_target_knowledge_scope_id;
    end if;

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
      orac_code.knowledge_text_identity_api.calculate_canonical_markdown(
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
           or not l_metadata_object.has('producer_knowledge_scope_id')
           or l_metadata_object.get_number('producer_knowledge_scope_id') is null
           or l_metadata_object.get_number('producer_knowledge_scope_id') <>
              orac_code.knowledge_scope_api.resolve_scope_id('PLUGIN', 'drop_box')
           or orac_code.knowledge_scope_api.scope_status_by_id(
                l_metadata_object.get_number('producer_knowledge_scope_id')
              ) <> 'RAG_USAGE_SCOPE_ELIGIBLE'
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
               'producer_knowledge_scope_id',
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
       where knowledge_scope_id = l_knowledge_scope_id
         and source_type = l_source_type
         and source_reference = l_source_reference
         for update;

      update orac_api.knowledge_source_objects_v
         set parent_source_reference = p_parent_source_reference
       where source_object_id = l_source_object_id;
    exception
      when no_data_found then
        select count(*)
          into l_existing_count
          from orac_api.knowledge_source_objects_v
         where knowledge_scope_id = l_knowledge_scope_id
           and source_type = l_source_type
           and source_reference = l_source_reference;

        if l_existing_count > 0
        then
          raise_application_error(-20407, 'Stable source reference collision detected.');
        end if;

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

      l_conflicting_fields := null;
      if l_existing_source_object_id <> l_source_object_id
      then
        append_conflicting_field(l_conflicting_fields, 'source_object_id');
      end if;
      if not equivalent_storage_key(
               l_existing_content_uri,
               l_content_sha256
             )
      then
        append_conflicting_field(l_conflicting_fields, 'content_uri');
      end if;
      if text_differs(l_existing_mime_type, l_mime_type)
      then
        append_conflicting_field(l_conflicting_fields, 'mime_type');
      end if;
      if text_differs(l_existing_original_filename, p_original_filename)
      then
        append_conflicting_field(l_conflicting_fields, 'original_filename');
      end if;
      if number_differs(l_existing_byte_size, p_byte_size)
      then
        append_conflicting_field(l_conflicting_fields, 'byte_size');
      end if;
      if timestamp_differs(
           l_existing_source_modified_on,
           p_source_modified_on
         )
      then
        append_conflicting_field(l_conflicting_fields, 'source_modified_on');
      end if;
      if text_differs(
           l_existing_source_format_code,
           p_source_format_code
         )
      then
        append_conflicting_field(l_conflicting_fields, 'source_format_code');
      end if;

      if l_conflicting_fields is not null
      then
        raise_application_error(
          -20429,
          'Immutable raw document-version metadata conflicts with the existing version. '
          || 'Conflicting fields: ' || l_conflicting_fields || '.'
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
      if p_output_set_json is null
      then
        raise_application_error(-20430, 'New normalised content requires a managed artefact output set.');
      end if;
      l_output_set_result := orac_code.knowledge_artefact_api.register_output_set(
        p_extraction_id   => l_extraction_id,
        p_output_set_json => p_output_set_json
      );
    elsif p_output_set_json is not null
    then
      raise_application_error(-20431, 'An output set requires normalised extraction content.');
    end if;

    if p_classification_tags_json is null
       and l_source_type = 'DROP_BOX'
    then
      raise_application_error(
        -20416,
        'Drop Box requires at least one classification tag.'
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
          l_classification_code := l_tag_array.get_string(l_index);
          if l_seen_tags.exists(l_classification_code)
          then
            raise_application_error(-20421, 'Duplicate classification tags are not allowed.');
          end if;
          l_seen_tags(l_classification_code) := true;
          select count(*)
            into l_duplicate_count
            from orac_api.domain_codes_v dom
            join orac_api.domain_ref_values_v ref
              on ref.domain_code = dom.domain_code
           where dom.domain_code = 'DOC_CLASS'
             and dom.active_yn = 'Y'
             and ref.ref_value_code = l_classification_code
             and ref.active_yn = 'Y';
          if l_duplicate_count <> 1
          then
            raise_application_error(-20419, 'Classification tag is unknown or inactive.');
          end if;
        end loop;
      end if;

      select count(*)
        into l_existing_tag_count
        from orac_api.knowledge_document_version_tags_v
       where document_version_id = l_document_version_id
         and doc_class_domain_code = 'DOC_CLASS';
      if l_existing_tag_count not in (0, l_tag_count)
      then
        raise_application_error(
          -20422,
          'Idempotency conflict: classification tags do not match.'
        );
      end if;

      l_tag_order := 0;
      for tag_rec in (
        select ref.ref_value_code
          from orac_api.domain_codes_v dom
          join orac_api.domain_ref_values_v ref
            on ref.domain_code = dom.domain_code
          join json_table(
                 p_classification_tags_json,
                 '$[*]' columns (
                   ref_value_code varchar2(100) path '$'
                 )
               ) selected
            on selected.ref_value_code = ref.ref_value_code
         where dom.domain_code = 'DOC_CLASS'
           and dom.active_yn = 'Y'
           and ref.active_yn = 'Y'
         order by ref.display_sequence, ref.ref_value_code
      )
      loop
        l_tag_order := l_tag_order + 1;
        if l_existing_tag_count = 0
        then
          l_tag_link_row.document_version_id := l_document_version_id;
          l_tag_link_row.doc_class_domain_code := 'DOC_CLASS';
          l_tag_link_row.doc_class_ref_value_code := tag_rec.ref_value_code;
          l_tag_link_row.tag_order := l_tag_order;
          orac_api.knowledge_document_version_tags_tapi.ins(l_tag_link_row);
        else
          select count(*)
            into l_duplicate_count
            from orac_api.knowledge_document_version_tags_v
           where document_version_id = l_document_version_id
             and doc_class_domain_code = 'DOC_CLASS'
             and doc_class_ref_value_code = tag_rec.ref_value_code
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
        from orac_api.knowledge_ingestion_requests_v req
       where (status_code = c_status_queued
          or (status_code = c_status_retry_wait and next_attempt_on <= systimestamp)
          or (status_code = c_status_processing and lease_expires_on <= systimestamp))
         and exists (
           select 1 from orac_api.knowledge_source_objects_v src
            where src.source_object_id = req.source_object_id
              and orac_code.knowledge_scope_api.scope_status_by_id(src.knowledge_scope_id) = 'RAG_USAGE_SCOPE_ELIGIBLE'
         )
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

  procedure requeue_failed_request(
    p_ingestion_request_id in number
  )
  is
    l_updated_count number;
  begin
    update orac_api.knowledge_ingestion_requests_v
       set status_code        = c_status_queued,
           stage_code         = 'SUBMITTED',
           attempts           = 0,
           next_attempt_on    = systimestamp,
           lease_owner        = null,
           lease_token        = null,
           lease_expires_on   = null,
           completed_on       = null,
           last_error_code    = null,
           last_error_message = null
     where ingestion_request_id = p_ingestion_request_id
       and status_code = c_status_failed;

    l_updated_count := sql%rowcount;
    if l_updated_count <> 1
    then
      raise_application_error(
        -20434,
        'Only one failed knowledge ingestion request can be requeued.'
      );
    end if;

    add_event(
      p_ingestion_request_id,
      'requeued',
      'Failed Core knowledge ingestion requeued by an operator.'
    );
  end requeue_failed_request;

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
        'Immutable raw document-version metadata conflicts with the request. '
        || 'Conflicting fields: source_modified_on.'
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
    p_overlap_tokens     in number,
    p_source_artefact_id in number default null
  ) return number
  is
    l_chunk_set_id number;
    l_chunker_code varchar2(100);
    l_chunker_version varchar2(100);
    l_artefact_count number;
    l_valid_source_count number;
  begin
    l_chunker_code := normalised_required(p_chunker_code, 'Chunker code');
    l_chunker_version := normalised_required(p_chunker_version, 'Chunker version');
    select count(*)
      into l_artefact_count
      from orac_api.knowledge_artefacts_v
     where extraction_id = p_extraction_id;
    if p_source_artefact_id is null and l_artefact_count > 0
    then
      raise_application_error(-20432, 'Artefact-backed extractions require a source artefact.');
    elsif p_source_artefact_id is not null
    then
      select count(*)
        into l_valid_source_count
        from orac_api.knowledge_artefacts_v
       where extraction_id = p_extraction_id
         and artefact_id = p_source_artefact_id
         and artefact_role_code in ('PRIMARY', 'MANIFEST', 'TABLE');
      if l_valid_source_count <> 1
      then
        raise_application_error(-20433, 'Chunk source artefact is invalid for this extraction.');
      end if;
    end if;
    begin
      insert into orac_api.knowledge_chunk_sets_v (
        extraction_id,
        source_artefact_id,
        chunker_code,
        chunker_version,
        chunk_size_tokens,
        overlap_tokens
      )
      values (
        p_extraction_id,
        p_source_artefact_id,
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
           and nvl(source_artefact_id, -1) = nvl(p_source_artefact_id, -1)
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

  function worker_output_set_json(
    p_extraction_id in number
  ) return clob
  is
  begin
    return orac_code.knowledge_artefact_api.output_set_json(p_extraction_id);
  end worker_output_set_json;

  procedure complete_request(
    p_ingestion_request_id in number,
    p_owner_id             in varchar2,
    p_lease_token          in varchar2,
    p_embedding_profile_id in number
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
    l_extraction_id          number;
    l_artefact_count         number;
    l_profile_count          number;
  begin
    assert_lease(p_ingestion_request_id, p_owner_id, p_lease_token);

    select count(*)
      into l_profile_count
      from orac_api.knowledge_embedding_activations_v activation
      join orac_api.knowledge_embedding_profiles_v profile
        on profile.embedding_profile_id = activation.embedding_profile_id
       and profile.purpose_code = activation.purpose_code
       and profile.semantic_yn = 'Y'
       and profile.production_allowed_yn = 'Y'
      join orac_api.knowledge_embedding_models_v model
        on model.embedding_model_id = profile.embedding_model_id
       and model.dimensions > 0
       and profile.storage_layout_code =
           'ORACLE_VECTOR_' || to_char(model.dimensions) || '_FLOAT32_V1'
     where activation.purpose_code = 'KNOWLEDGE_CHUNK_RETRIEVAL'
       and activation.embedding_profile_id = p_embedding_profile_id;

    if l_profile_count <> 1
    then
      raise_application_error(
        -20412,
        'Cannot complete a knowledge request without the active production embedding profile.'
      );
    end if;

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

    select min(ext.extraction_id), count(art.artefact_id)
      into l_extraction_id, l_artefact_count
      from orac_api.knowledge_ingestion_requests_v req
      join orac_api.knowledge_extractions_v ext
        on ext.document_version_id = req.document_version_id
      left join orac_api.knowledge_artefacts_v art
        on art.extraction_id = ext.extraction_id
     where req.ingestion_request_id = p_ingestion_request_id;
    if l_artefact_count > 0
    then
      orac_code.knowledge_artefact_api.assert_complete_set(l_extraction_id);
    end if;

    for rec in (
      select chn.chunk_id,
             chn.chunk_text,
             chn.content_sha256 chunk_content_sha256,
             native_emb.chunk_vector_embedding_id chunk_embedding_id,
             native_emb.embedding_vector,
             native_emb.embedding_text_sha256,
             model.provider_code,
             model.model_name,
             model.model_revision,
             model.dimensions,
             profile.profile_version,
             profile.model_digest,
             profile.storage_layout_code
        from orac_api.knowledge_ingestion_requests_v req
        join orac_api.knowledge_extractions_v ext
          on ext.document_version_id = req.document_version_id
        join orac_api.knowledge_chunk_sets_v chs
          on chs.extraction_id = ext.extraction_id
        join orac_api.knowledge_chunks_v chn
          on chn.chunk_set_id = chs.chunk_set_id
        join orac_api.knowledge_embedding_activations_v activation
          on activation.purpose_code = 'KNOWLEDGE_CHUNK_RETRIEVAL'
         and activation.embedding_profile_id = p_embedding_profile_id
        join orac_api.knowledge_embedding_profiles_v profile
          on profile.embedding_profile_id = activation.embedding_profile_id
         and profile.purpose_code = activation.purpose_code
         and profile.semantic_yn = 'Y'
         and profile.production_allowed_yn = 'Y'
        join orac_api.knowledge_embedding_models_v model
          on model.embedding_model_id = profile.embedding_model_id
        left join orac_api.knowledge_chunk_vector_embeddings_v native_emb
          on native_emb.chunk_id = chn.chunk_id
         and native_emb.embedding_profile_id = p_embedding_profile_id
       where req.ingestion_request_id = p_ingestion_request_id
         and not exists (
           select 1
             from orac_api.knowledge_chunk_sets_v newer
            where newer.extraction_id = chs.extraction_id
              and nvl(newer.source_artefact_id, -1) =
                  nvl(chs.source_artefact_id, -1)
              and newer.chunk_set_id > chs.chunk_set_id
         )
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

        if rec.embedding_text_sha256 <> rec.chunk_content_sha256
        then
          l_bad_vector_count := l_bad_vector_count + 1;
        elsif rec.dimensions is null
           or rec.dimensions <= 0
           or rec.storage_layout_code <>
              'ORACLE_VECTOR_' || to_char(rec.dimensions) || '_FLOAT32_V1'
           or vector_dimension_count(rec.embedding_vector) <> rec.dimensions
           or vector_dimension_format(rec.embedding_vector) <> 'FLOAT32'
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

  procedure set_document_retrieval_enabled(
    p_document_id          in number,
    p_expected_row_version in number,
    p_enabled_yn           in varchar2
  )
  is
  begin
    if p_document_id is null
       or p_document_id <= 0
       or p_expected_row_version is null
       or p_expected_row_version <= 0
       or p_enabled_yn is null
       or p_enabled_yn not in ('Y', 'N')
    then
      raise_application_error(-20632, 'RETRIEVAL_REQUEST_INVALID');
    end if;

    update orac_api.knowledge_documents_v
       set retrieval_enabled_yn = p_enabled_yn
     where document_id = p_document_id
       and row_version = p_expected_row_version;

    if sql%rowcount <> 1
    then
      raise_application_error(-20632, 'RETRIEVAL_DOCUMENT_CHANGED');
    end if;
  end set_document_retrieval_enabled;
end knowledge_ingestion_api;
/

--rollback drop package body orac_code.knowledge_ingestion_api;
