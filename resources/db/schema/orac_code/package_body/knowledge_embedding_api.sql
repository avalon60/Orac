--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Implements native VECTOR profile registration and atomic activation.

--changeset clive:create_package_body_orac_code_knowledge_embedding_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.knowledge_embedding_api
as
  c_purpose constant varchar2(100) := 'KNOWLEDGE_CHUNK_RETRIEVAL';
  c_storage constant varchar2(100) := 'ORACLE_VECTOR_768_FLOAT32_V1';

  function required_text(
    p_value in varchar2,
    p_name  in varchar2
  ) return varchar2
  is
    l_value varchar2(4000) := trim(p_value);
  begin
    if l_value is null
    then
      raise_application_error(-20710, p_name || ' is required.');
    end if;
    return l_value;
  end required_text;

  function ensure_profile(
    p_profile_version          in varchar2,
    p_provider_code            in varchar2,
    p_model_name               in varchar2,
    p_model_digest             in varchar2,
    p_document_input_prefix    in varchar2,
    p_query_input_prefix       in varchar2,
    p_retrieval_policy_version in varchar2 default 'knowledge-hybrid-v1',
    p_semantic_threshold       in number default 0.60
  ) return number
  is
    l_profile_id number;
    l_model_id   number;
    l_digest     varchar2(128) := lower(required_text(p_model_digest, 'Model digest'));
    l_profile_version varchar2(100) := required_text(
      p_profile_version, 'Profile version'
    );
    l_provider_code varchar2(100) := lower(required_text(
      p_provider_code, 'Provider code'
    ));
    l_model_name varchar2(255) := required_text(p_model_name, 'Model name');
    l_document_prefix varchar2(100) := required_text(
      p_document_input_prefix, 'Document input prefix'
    );
    l_query_prefix varchar2(100) := required_text(
      p_query_input_prefix, 'Query input prefix'
    );
    l_policy_version varchar2(100) := required_text(
      p_retrieval_policy_version, 'Retrieval policy version'
    );
  begin
    if not regexp_like(l_digest, '^[0-9a-f]{12,128}$')
       or p_semantic_threshold not between 0 and 1
    then
      raise_application_error(-20711, 'KNOWLEDGE_EMBEDDING_PROFILE_INVALID');
    end if;

    l_model_id := orac_code.knowledge_ingestion_api.upsert_embedding_model(
      p_provider_code   => l_provider_code,
      p_model_name      => l_model_name,
      p_model_revision  => l_digest,
      p_dimensions      => 768,
      p_distance_metric => 'COSINE',
      p_normalisation   => 'UNIT'
    );

    begin
      insert into orac_api.knowledge_embedding_profiles_v (
        purpose_code,
        profile_version,
        embedding_model_id,
        model_digest,
        document_input_prefix,
        query_input_prefix,
        truncate_yn,
        storage_layout_code,
        retrieval_policy_version,
        semantic_threshold,
        semantic_candidate_limit,
        lexical_candidate_limit,
        semantic_yn,
        production_allowed_yn
      ) values (
        c_purpose,
        l_profile_version,
        l_model_id,
        l_digest,
        l_document_prefix,
        l_query_prefix,
        'N',
        c_storage,
        l_policy_version,
        p_semantic_threshold,
        50,
        50,
        'Y',
        'Y'
      ) returning embedding_profile_id into l_profile_id;
    exception
      when dup_val_on_index then
        select profile.embedding_profile_id
          into l_profile_id
          from orac_api.knowledge_embedding_profiles_v profile
         where profile.purpose_code = c_purpose
           and profile.profile_version = l_profile_version
           and profile.embedding_model_id = l_model_id
           and profile.model_digest = l_digest
           and profile.document_input_prefix = l_document_prefix
           and profile.query_input_prefix = l_query_prefix
           and profile.truncate_yn = 'N'
           and profile.storage_layout_code = c_storage
           and profile.retrieval_policy_version = l_policy_version
           and profile.semantic_threshold = p_semantic_threshold
           and profile.semantic_yn = 'Y'
           and profile.production_allowed_yn = 'Y';
    end;
    return l_profile_id;
  exception
    when no_data_found then
      raise_application_error(-20712, 'KNOWLEDGE_EMBEDDING_PROFILE_IMMUTABLE');
  end ensure_profile;

  function active_profile_json return clob
  is
    l_result clob;
  begin
    select json_object(
             'embedding_profile_id' value profile.embedding_profile_id,
             'purpose_code' value profile.purpose_code,
             'profile_version' value profile.profile_version,
             'provider_code' value model.provider_code,
             'model_name' value model.model_name,
             'model_digest' value profile.model_digest,
             'dimensions' value model.dimensions,
             'document_input_prefix' value profile.document_input_prefix,
             'query_input_prefix' value profile.query_input_prefix,
             'truncate' value 'false' format json,
             'storage_layout_code' value profile.storage_layout_code,
             'retrieval_policy_version' value profile.retrieval_policy_version,
             'semantic_threshold' value profile.semantic_threshold,
             'semantic_candidate_limit' value profile.semantic_candidate_limit,
             'lexical_candidate_limit' value profile.lexical_candidate_limit,
             'searchable_chunk_count' value (
               select count(*)
                 from orac_code.knowledge_searchable_chunk_content_v
             ),
             'current_chunk_count' value (
               select count(*)
                 from orac_code.knowledge_searchable_chunk_content_v chunk
                 join orac_api.knowledge_chunk_vector_embeddings_v embedding
                   on embedding.chunk_id = chunk.chunk_id
                  and embedding.embedding_profile_id = profile.embedding_profile_id
                  and embedding.embedding_text_sha256 = chunk.chunk_content_sha256
             ),
             'missing_chunk_count' value (
               (select count(*)
                  from orac_code.knowledge_searchable_chunk_content_v)
               -
               (select count(*)
                  from orac_code.knowledge_searchable_chunk_content_v chunk
                  join orac_api.knowledge_chunk_vector_embeddings_v embedding
                    on embedding.chunk_id = chunk.chunk_id
                   and embedding.embedding_profile_id = profile.embedding_profile_id
                   and embedding.embedding_text_sha256 = chunk.chunk_content_sha256)
             ),
             'stale_chunk_count' value (
               select count(*)
                 from orac_api.knowledge_chunk_vector_embeddings_v embedding
                 join orac_code.knowledge_searchable_chunk_content_v chunk
                   on chunk.chunk_id = embedding.chunk_id
                where embedding.embedding_profile_id = profile.embedding_profile_id
                  and embedding.embedding_text_sha256 <> chunk.chunk_content_sha256
             )
             returning clob
           )
      into l_result
      from orac_api.knowledge_embedding_activations_v activation
      join orac_api.knowledge_embedding_profiles_v profile
        on profile.embedding_profile_id = activation.embedding_profile_id
      join orac_api.knowledge_embedding_models_v model
        on model.embedding_model_id = profile.embedding_model_id
     where activation.purpose_code = c_purpose;
    return l_result;
  exception
    when no_data_found then
      return null;
  end active_profile_json;

  function begin_reembedding_run(
    p_embedding_profile_id in number
  ) return number
  is
    l_run_id number;
    l_count  number;
  begin
    select count(*)
      into l_count
      from orac_api.knowledge_embedding_profiles_v
     where embedding_profile_id = p_embedding_profile_id
       and purpose_code = c_purpose
       and storage_layout_code = c_storage
       and semantic_yn = 'Y'
       and production_allowed_yn = 'Y';
    if l_count <> 1
    then
      raise_application_error(-20713, 'KNOWLEDGE_EMBEDDING_PROFILE_NOT_PRODUCTION');
    end if;

    select count(*)
      into l_count
      from orac_code.knowledge_searchable_chunk_content_v;
    insert into orac_api.knowledge_reembedding_runs_v (
      embedding_profile_id,
      status_code,
      expected_chunk_count
    ) values (
      p_embedding_profile_id,
      'BUILDING',
      l_count
    ) returning reembedding_run_id into l_run_id;
    return l_run_id;
  end begin_reembedding_run;

  procedure open_reembedding_chunks(
    p_reembedding_run_id in number,
    p_chunk_limit        in number,
    p_content_rows       out sys_refcursor
  )
  is
    l_profile_id number;
  begin
    if p_chunk_limit not between 1 and 500
    then
      raise_application_error(-20714, 'KNOWLEDGE_REEMBEDDING_LIMIT_INVALID');
    end if;
    select embedding_profile_id
      into l_profile_id
      from orac_api.knowledge_reembedding_runs_v
     where reembedding_run_id = p_reembedding_run_id
       and status_code in ('BUILDING', 'FAILED');

    open p_content_rows for
      select chunk_id,
             chunk_content_sha256,
             chunk_text
        from (
          select chunk.chunk_id,
                 chunk.chunk_content_sha256,
                 chunk.chunk_text
            from orac_code.knowledge_searchable_chunk_content_v chunk
           where not exists (
             select 1
               from orac_api.knowledge_chunk_vector_embeddings_v embedding
              where embedding.chunk_id = chunk.chunk_id
                and embedding.embedding_profile_id = l_profile_id
                and embedding.embedding_text_sha256 = chunk.chunk_content_sha256
           )
           order by chunk.chunk_id
        )
       where rownum <= p_chunk_limit;
  exception
    when no_data_found then
      raise_application_error(-20715, 'KNOWLEDGE_REEMBEDDING_RUN_INVALID');
  end open_reembedding_chunks;

  function store_native_embedding(
    p_embedding_profile_id  in number,
    p_chunk_id              in number,
    p_embedding_text_sha256 in varchar2,
    p_embedding_vector_json in clob,
    p_reembedding_run_id    in number default null
  ) return number
  is
    l_embedding_id number;
    l_vector       vector(768, float32);
    l_hash         varchar2(64) := lower(trim(p_embedding_text_sha256));
    l_count        number;
  begin
    if not regexp_like(l_hash, '^[0-9a-f]{64}$')
       or p_embedding_vector_json is null
       or p_embedding_vector_json is not json
    then
      raise_application_error(-20716, 'KNOWLEDGE_NATIVE_VECTOR_INVALID');
    end if;
    select count(*)
      into l_count
      from orac_api.knowledge_chunks_v chunk
      join orac_api.knowledge_embedding_profiles_v profile
        on profile.embedding_profile_id = p_embedding_profile_id
       and profile.storage_layout_code = c_storage
       and profile.semantic_yn = 'Y'
     where chunk.chunk_id = p_chunk_id
       and chunk.content_sha256 = l_hash;
    if l_count <> 1
    then
      raise_application_error(-20717, 'KNOWLEDGE_NATIVE_VECTOR_LINEAGE_INVALID');
    end if;
    if p_reembedding_run_id is not null
    then
      select count(*)
        into l_count
        from orac_api.knowledge_reembedding_runs_v
       where reembedding_run_id = p_reembedding_run_id
         and embedding_profile_id = p_embedding_profile_id
         and status_code in ('BUILDING', 'FAILED');
      if l_count <> 1
      then
        raise_application_error(-20715, 'KNOWLEDGE_REEMBEDDING_RUN_INVALID');
      end if;
    end if;

    l_vector := to_vector(p_embedding_vector_json, 768, float32);
    if vector_dimension_count(l_vector) <> 768
       or vector_dimension_format(l_vector) <> 'FLOAT32'
       or vector_norm(l_vector) not between 0.99 and 1.01
    then
      raise_application_error(-20716, 'KNOWLEDGE_NATIVE_VECTOR_INVALID');
    end if;

    begin
      insert into orac_api.knowledge_chunk_vector_embeddings_v (
        chunk_id,
        embedding_profile_id,
        reembedding_run_id,
        embedding_text_sha256,
        embedding_vector
      ) values (
        p_chunk_id,
        p_embedding_profile_id,
        p_reembedding_run_id,
        l_hash,
        l_vector
      ) returning chunk_vector_embedding_id into l_embedding_id;
      if p_reembedding_run_id is not null
      then
        update orac_api.knowledge_reembedding_runs_v
           set completed_chunk_count = completed_chunk_count + 1,
               updated_on = systimestamp,
               row_version = row_version + 1
         where reembedding_run_id = p_reembedding_run_id;
      end if;
    exception
      when dup_val_on_index then
        select chunk_vector_embedding_id
          into l_embedding_id
          from orac_api.knowledge_chunk_vector_embeddings_v
         where chunk_id = p_chunk_id
           and embedding_profile_id = p_embedding_profile_id
           and embedding_text_sha256 = l_hash;
    end;
    return l_embedding_id;
  exception
    when value_error then
      raise_application_error(-20716, 'KNOWLEDGE_NATIVE_VECTOR_INVALID');
  end store_native_embedding;

  procedure validate_reembedding_run(
    p_reembedding_run_id in number
  )
  is
    l_profile_id number;
    l_expected   number;
    l_completed  number;
    l_stale      number;
  begin
    select embedding_profile_id
      into l_profile_id
      from orac_api.knowledge_reembedding_runs_v
     where reembedding_run_id = p_reembedding_run_id
       and status_code in ('BUILDING', 'FAILED', 'VALIDATING');

    update orac_api.knowledge_reembedding_runs_v
       set status_code = 'VALIDATING',
           updated_on = systimestamp,
           row_version = row_version + 1
     where reembedding_run_id = p_reembedding_run_id;

    select count(*)
      into l_expected
      from orac_code.knowledge_searchable_chunk_content_v;
    select count(*)
      into l_completed
      from orac_code.knowledge_searchable_chunk_content_v chunk
      join orac_api.knowledge_chunk_vector_embeddings_v embedding
        on embedding.chunk_id = chunk.chunk_id
       and embedding.embedding_profile_id = l_profile_id
       and embedding.embedding_text_sha256 = chunk.chunk_content_sha256;
    select count(*)
      into l_stale
      from orac_api.knowledge_chunk_vector_embeddings_v embedding
      join orac_code.knowledge_searchable_chunk_content_v chunk
        on chunk.chunk_id = embedding.chunk_id
     where embedding.embedding_profile_id = l_profile_id
       and embedding.embedding_text_sha256 <> chunk.chunk_content_sha256;

    update orac_api.knowledge_reembedding_runs_v
       set expected_chunk_count = l_expected,
           completed_chunk_count = l_completed,
           stale_chunk_count = l_stale,
           failed_chunk_count = case when l_completed = l_expected and l_stale = 0 then 0 else l_expected - l_completed end,
           status_code = case when l_completed = l_expected and l_stale = 0 then 'VALIDATED' else 'FAILED' end,
           last_error_code = case when l_completed = l_expected and l_stale = 0 then null else 'KNOWLEDGE_REEMBEDDING_INCOMPLETE' end,
           completed_on = case when l_completed = l_expected and l_stale = 0 then systimestamp else null end,
           updated_on = systimestamp,
           row_version = row_version + 1
     where reembedding_run_id = p_reembedding_run_id;

    if l_completed <> l_expected or l_stale <> 0
    then
      raise_application_error(-20718, 'KNOWLEDGE_REEMBEDDING_INCOMPLETE');
    end if;
  exception
    when no_data_found then
      raise_application_error(-20715, 'KNOWLEDGE_REEMBEDDING_RUN_INVALID');
  end validate_reembedding_run;

  procedure activate_reembedding_run(
    p_reembedding_run_id in number
  )
  is
    l_profile_id number;
  begin
    select run.embedding_profile_id
      into l_profile_id
      from orac_api.knowledge_reembedding_runs_v run
      join orac_api.knowledge_embedding_profiles_v profile
        on profile.embedding_profile_id = run.embedding_profile_id
       and profile.purpose_code = c_purpose
       and profile.storage_layout_code = c_storage
       and profile.semantic_yn = 'Y'
       and profile.production_allowed_yn = 'Y'
     where run.reembedding_run_id = p_reembedding_run_id
       and run.status_code = 'VALIDATED'
       and run.completed_chunk_count = run.expected_chunk_count
       and run.stale_chunk_count = 0
       and run.failed_chunk_count = 0;

    merge into orac_api.knowledge_embedding_activations_v activation
    using (
      select c_purpose purpose_code,
             l_profile_id embedding_profile_id
        from dual
    ) source
       on (activation.purpose_code = source.purpose_code)
     when matched then update set
       activation.embedding_profile_id = source.embedding_profile_id,
       activation.activated_by = coalesce(
         sys_context('apex$session', 'app_user'),
         sys_context('userenv', 'proxy_user'),
         sys_context('userenv', 'session_user'),
         user
       ),
       activation.activated_on = systimestamp,
       activation.updated_on = systimestamp,
       activation.row_version = activation.row_version + 1
     when not matched then insert (
       purpose_code,
       embedding_profile_id
     ) values (
       source.purpose_code,
       source.embedding_profile_id
     );

    update orac_api.knowledge_reembedding_runs_v
       set status_code = 'ACTIVE',
           updated_on = systimestamp,
           row_version = row_version + 1
     where reembedding_run_id = p_reembedding_run_id;
  exception
    when no_data_found then
      raise_application_error(-20719, 'KNOWLEDGE_REEMBEDDING_NOT_VALIDATED');
  end activate_reembedding_run;

  procedure activate_profile(
    p_embedding_profile_id in number
  )
  is
    l_expected  number;
    l_completed number;
    l_stale     number;
  begin
    select count(*)
      into l_expected
      from orac_code.knowledge_searchable_chunk_content_v;
    select count(*)
      into l_completed
      from orac_code.knowledge_searchable_chunk_content_v chunk
      join orac_api.knowledge_chunk_vector_embeddings_v embedding
        on embedding.chunk_id = chunk.chunk_id
       and embedding.embedding_profile_id = p_embedding_profile_id
       and embedding.embedding_text_sha256 = chunk.chunk_content_sha256
      join orac_api.knowledge_embedding_profiles_v profile
        on profile.embedding_profile_id = embedding.embedding_profile_id
       and profile.purpose_code = c_purpose
       and profile.storage_layout_code = c_storage
       and profile.semantic_yn = 'Y'
       and profile.production_allowed_yn = 'Y';
    select count(*)
      into l_stale
      from orac_api.knowledge_chunk_vector_embeddings_v embedding
      join orac_code.knowledge_searchable_chunk_content_v chunk
        on chunk.chunk_id = embedding.chunk_id
     where embedding.embedding_profile_id = p_embedding_profile_id
       and embedding.embedding_text_sha256 <> chunk.chunk_content_sha256;
    if l_completed <> l_expected or l_stale <> 0
    then
      raise_application_error(-20719, 'KNOWLEDGE_EMBEDDING_PROFILE_NOT_CURRENT');
    end if;

    merge into orac_api.knowledge_embedding_activations_v activation
    using (
      select c_purpose purpose_code,
             p_embedding_profile_id embedding_profile_id
        from dual
    ) source
       on (activation.purpose_code = source.purpose_code)
     when matched then update set
       activation.embedding_profile_id = source.embedding_profile_id,
       activation.activated_by = coalesce(
         sys_context('apex$session', 'app_user'),
         sys_context('userenv', 'proxy_user'),
         sys_context('userenv', 'session_user'),
         user
       ),
       activation.activated_on = systimestamp,
       activation.updated_on = systimestamp,
       activation.row_version = activation.row_version + 1
     when not matched then insert (
       purpose_code,
       embedding_profile_id
     ) values (
       source.purpose_code,
       source.embedding_profile_id
     );
  end activate_profile;

  function reembedding_run_status_json(
    p_reembedding_run_id in number
  ) return clob
  is
    l_result clob;
  begin
    select json_object(
             'reembedding_run_id' value run.reembedding_run_id,
             'embedding_profile_id' value run.embedding_profile_id,
             'status_code' value run.status_code,
             'expected_chunk_count' value run.expected_chunk_count,
             'completed_chunk_count' value run.completed_chunk_count,
             'stale_chunk_count' value run.stale_chunk_count,
             'failed_chunk_count' value run.failed_chunk_count,
             'last_error_code' value run.last_error_code,
             'started_on' value run.started_on,
             'completed_on' value run.completed_on absent on null
             returning clob
           )
      into l_result
      from orac_api.knowledge_reembedding_runs_v run
     where run.reembedding_run_id = p_reembedding_run_id;
    return l_result;
  exception
    when no_data_found then
      raise_application_error(-20715, 'KNOWLEDGE_REEMBEDDING_RUN_INVALID');
  end reembedding_run_status_json;
end knowledge_embedding_api;
/

--rollback drop package body orac_code.knowledge_embedding_api;
