--liquibase formatted sql
-- Author: clive
-- Date: 28-Aug-2026
-- Description: Implements principal-scoped conversation memory and durable checkpoint work.

--changeset clive:create_package_body_orac_code_conversation_memory_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.conversation_memory_api
as
  c_status_pending    constant varchar2(20) := 'PENDING';
  c_status_retry_wait constant varchar2(20) := 'RETRY_WAIT';
  c_status_completed  constant varchar2(20) := 'COMPLETED';
  c_status_failed     constant varchar2(20) := 'FAILED';

  function required_text(
    p_value in varchar2,
    p_name  in varchar2
  ) return varchar2
  is
    l_value varchar2(4000);
  begin
    l_value := trim(p_value);
    if l_value is null
    then
      raise_application_error(-20073, p_name || ' is required.');
    end if;
    return l_value;
  end required_text;

  function active_user_id(
    p_principal_username in varchar2
  ) return number
  is
    l_user_id number;
    l_principal_username varchar2(4000);
  begin
    l_principal_username := required_text(
      p_principal_username,
      'Principal username'
    );
    select user_id
      into l_user_id
      from orac_api.users_v
     where lower(username) = lower(l_principal_username)
       and is_active = 'Y';
    return l_user_id;
  exception
    when no_data_found then
      return null;
  end active_user_id;

  function reconcile_eligible_ranges(
    p_checkpoint_exchange_count in number,
    p_materialisation_profile   in varchar2,
    p_prompt_version            in varchar2,
    p_max_attempts              in number
  ) return number
  is
    l_profile varchar2(100);
    l_prompt  varchar2(64);
    l_created number := 0;
    l_row     orac_api.conversation_memory_requests_v%rowtype;
  begin
    if p_checkpoint_exchange_count <= 0 or p_max_attempts <= 0
    then
      raise_application_error(-20074, 'Checkpoint and retry limits must be positive.');
    end if;
    l_profile := required_text(p_materialisation_profile, 'Materialisation profile');
    l_prompt := required_text(p_prompt_version, 'Prompt version');

    for rec_range in (
      with eligible_messages as (
        select c.conversation_id,
               c.state,
               m.turn_index,
               row_number() over (
                 partition by c.conversation_id order by m.turn_index
               ) message_sequence,
               count(*) over (
                 partition by c.conversation_id
               ) message_count
          from orac_api.conversations_v c
          join orac_api.messages_v m
            on m.conversation_id = c.conversation_id
         where m.role in ('user', 'assistant')
           and coalesce(m.message_type, 'dialogue') not in (
                 'tool_result', 'context_injection', 'operational_error'
               )
      ), bounded_ranges as (
        select conversation_id,
               state,
               ceil(message_sequence / (2 * p_checkpoint_exchange_count)) range_no,
               min(turn_index) first_turn_index,
               max(turn_index) last_turn_index,
               count(*) range_message_count,
               max(message_count) conversation_message_count
          from eligible_messages
         group by conversation_id,
                  state,
                  ceil(message_sequence / (2 * p_checkpoint_exchange_count))
      )
      select conversation_id,
             first_turn_index,
             last_turn_index
        from bounded_ranges
       where range_message_count = 2 * p_checkpoint_exchange_count
          or (
               state in ('closed', 'archived')
           and range_message_count >= 2
           and mod(range_message_count, 2) = 0
          )
       order by conversation_id, first_turn_index
    )
    loop
      begin
        l_row := null;
        l_row.conversation_id := rec_range.conversation_id;
        l_row.first_turn_index := rec_range.first_turn_index;
        l_row.last_turn_index := rec_range.last_turn_index;
        l_row.materialisation_profile := l_profile;
        l_row.prompt_version := l_prompt;
        l_row.status_code := c_status_pending;
        l_row.attempt_count := 0;
        l_row.max_attempts := p_max_attempts;
        l_row.next_attempt_on := systimestamp;
        orac_api.conversation_memory_requests_tapi.ins(l_row);
        l_created := l_created + 1;
      exception
        when dup_val_on_index then
          null;
      end;
    end loop;
    return l_created;
  end reconcile_eligible_ranges;

  function next_request_id return number
  is
    l_memory_request_id number;
  begin
    select memory_request_id
      into l_memory_request_id
      from orac_api.conversation_memory_requests_v
     where status_code in (c_status_pending, c_status_retry_wait)
       and attempt_count < max_attempts
       and next_attempt_on <= systimestamp
     order by next_attempt_on, memory_request_id
     fetch first 1 row only;
    return l_memory_request_id;
  exception
    when no_data_found then
      return null;
  end next_request_id;

  procedure open_request_sources(
    p_memory_request_id in number,
    p_sources              out sys_refcursor
  )
  is
  begin
    open p_sources for
      select req.memory_request_id,
             req.conversation_id,
             req.first_turn_index,
             req.last_turn_index,
             req.materialisation_profile,
             req.prompt_version,
             m.message_id,
             m.turn_index,
             m.role,
             json_value(m.content, '$.text' returning clob) content_text,
             m.row_version,
             m.created_on
        from orac_api.conversation_memory_requests_v req
        join orac_api.messages_v m
          on m.conversation_id = req.conversation_id
         and m.turn_index between req.first_turn_index and req.last_turn_index
       where req.memory_request_id = p_memory_request_id
         and req.status_code in (c_status_pending, c_status_retry_wait)
         and m.role in ('user', 'assistant')
         and coalesce(m.message_type, 'dialogue') not in (
               'tool_result', 'context_injection', 'operational_error'
             )
       order by m.turn_index;
  end open_request_sources;

  procedure ensure_message_embedding(
    p_memory_request_id     in number,
    p_message_id            in number,
    p_source_row_version    in number,
    p_source_content_sha256 in varchar2,
    p_source_text           in clob,
    p_embedding_json        in clob,
    p_embedding_model       in varchar2,
    p_embedding_provider    in varchar2,
    p_token_count           in number
  )
  is
    l_count           number;
    l_embedding_model varchar2(4000);
    l_source_row_version number;
    l_source_text     clob;
    l_row             orac_api.message_embeddings_v%rowtype;
  begin
    l_embedding_model := required_text(p_embedding_model, 'Embedding model');
    select m.row_version,
           json_value(m.content, '$.text' returning clob)
      into l_source_row_version,
           l_source_text
      from orac_api.conversation_memory_requests_v req
      join orac_api.messages_v m
        on m.conversation_id = req.conversation_id
       and m.message_id = p_message_id
       and m.turn_index between req.first_turn_index and req.last_turn_index
     where req.memory_request_id = p_memory_request_id
       and req.status_code in (c_status_pending, c_status_retry_wait)
       and m.message_id = p_message_id;
    if l_source_row_version <> p_source_row_version
       or l_source_text is null
       or p_source_text is null
       or dbms_lob.compare(l_source_text, p_source_text) <> 0
       or length(required_text(
             p_source_content_sha256,
             'Source content SHA-256'
           )) <> 64
    then
      raise_application_error(-20075, 'Conversation source message changed during materialisation.');
    end if;

    select count(*)
      into l_count
      from orac_api.message_embeddings_v
     where message_id = p_message_id
       and chunk_index = 1
       and embedding_model = l_embedding_model;
    if l_count > 0
    then
      select count(*)
        into l_count
        from orac_api.message_embeddings_v
       where message_id = p_message_id
         and chunk_index = 1
         and embedding_model = l_embedding_model
         and json_value(content_snapshot, '$.source_content_sha256') = lower(p_source_content_sha256)
         and json_value(content_snapshot, '$.source_row_version' returning number) = p_source_row_version;
      if l_count <> 1
      then
        raise_application_error(-20076, 'Existing message embedding is incompatible with the pinned profile.');
      end if;
      return;
    end if;

    l_row.message_id := p_message_id;
    l_row.chunk_index := 1;
    l_row.span_start := 0;
    l_row.span_end := dbms_lob.getlength(p_source_text);
    l_row.lossless_text := p_source_text;
    l_row.content_snapshot := json_object(
      'source_row_version' value p_source_row_version,
      'source_content_sha256' value lower(p_source_content_sha256)
      returning json
    );
    l_row.embedding := to_vector(p_embedding_json);
    l_row.embedding_model := l_embedding_model;
    l_row.embedding_provider := required_text(p_embedding_provider, 'Embedding provider');
    l_row.distance_metric := 'COSINE';
    l_row.tokens_used := p_token_count;
    orac_api.message_embeddings_tapi.ins(l_row);
  end ensure_message_embedding;

  procedure complete_request(
    p_memory_request_id      in number,
    p_source_digest          in varchar2,
    p_summary_text           in clob,
    p_summarisation_provider in varchar2,
    p_summarisation_model    in varchar2,
    p_summary_embedding_json in clob,
    p_embedding_model        in varchar2,
    p_embedding_provider     in varchar2,
    p_embedding_dimensions   in number,
    p_source_lineage_json    in clob,
    p_checkpoint_id             out number
  )
  is
    l_request    orac_api.conversation_memory_requests_v%rowtype;
    l_checkpoint orac_api.conversation_summary_checkpoints_v%rowtype;
    l_source     orac_api.conversation_summary_sources_v%rowtype;
    l_source_count number;
  begin
    select *
      into l_request
      from orac_api.conversation_memory_requests_v
     where memory_request_id = p_memory_request_id;
    if l_request.status_code = c_status_completed
    then
      p_checkpoint_id := l_request.checkpoint_id;
      return;
    elsif l_request.status_code not in (c_status_pending, c_status_retry_wait)
    then
      raise_application_error(-20077, 'Conversation memory request is not completable.');
    end if;
    if p_summary_text is null
       or dbms_lob.getlength(p_summary_text) = 0
       or p_embedding_dimensions <= 0
    then
      raise_application_error(-20078, 'Summary text and embedding dimensions are required.');
    end if;

    select count(*)
      into l_source_count
      from json_table(
        p_source_lineage_json,
        '$[*]' columns (
          message_id number path '$.message_id',
          source_position number path '$.source_position',
          turn_index number path '$.turn_index',
          message_row_version number path '$.message_row_version',
          source_content_sha256 varchar2(64) path '$.source_content_sha256'
        )
      );
    if l_source_count = 0
    then
      raise_application_error(-20079, 'Checkpoint lineage is required.');
    end if;

    l_checkpoint.conversation_id := l_request.conversation_id;
    l_checkpoint.first_turn_index := l_request.first_turn_index;
    l_checkpoint.last_turn_index := l_request.last_turn_index;
    l_checkpoint.materialisation_profile := l_request.materialisation_profile;
    l_checkpoint.source_digest := lower(required_text(p_source_digest, 'Source digest'));
    l_checkpoint.summary_text := p_summary_text;
    l_checkpoint.summarisation_provider := required_text(p_summarisation_provider, 'Summarisation provider');
    l_checkpoint.summarisation_model := required_text(p_summarisation_model, 'Summarisation model');
    l_checkpoint.prompt_version := l_request.prompt_version;
    l_checkpoint.summary_embedding := to_vector(p_summary_embedding_json);
    l_checkpoint.embedding_model := required_text(p_embedding_model, 'Embedding model');
    l_checkpoint.embedding_provider := required_text(p_embedding_provider, 'Embedding provider');
    l_checkpoint.embedding_dimensions := p_embedding_dimensions;
    l_checkpoint.distance_metric := 'COSINE';
    orac_api.conversation_summary_checkpoints_tapi.ins(l_checkpoint);

    for rec_source in (
      select message_id,
             source_position,
             turn_index,
             message_row_version,
             lower(source_content_sha256) source_content_sha256
        from json_table(
          p_source_lineage_json,
          '$[*]' columns (
            message_id number path '$.message_id',
            source_position number path '$.source_position',
            turn_index number path '$.turn_index',
            message_row_version number path '$.message_row_version',
            source_content_sha256 varchar2(64) path '$.source_content_sha256'
          )
        )
       order by source_position
    )
    loop
      select count(*)
        into l_source_count
        from orac_api.messages_v m
        join orac_api.message_embeddings_v embedding
          on embedding.message_id = m.message_id
         and embedding.chunk_index = 1
         and embedding.embedding_model = p_embedding_model
       where m.message_id = rec_source.message_id
         and m.conversation_id = l_request.conversation_id
         and m.turn_index = rec_source.turn_index
         and m.row_version = rec_source.message_row_version
         and json_value(
               embedding.content_snapshot,
               '$.source_row_version' returning number
             ) = rec_source.message_row_version
         and json_value(
               embedding.content_snapshot,
               '$.source_content_sha256'
             ) = rec_source.source_content_sha256;
      if l_source_count <> 1
      then
        raise_application_error(-20080, 'Checkpoint source lineage no longer matches its message.');
      end if;
      l_source := null;
      l_source.checkpoint_id := l_checkpoint.checkpoint_id;
      l_source.message_id := rec_source.message_id;
      l_source.source_position := rec_source.source_position;
      l_source.turn_index := rec_source.turn_index;
      l_source.message_row_version := rec_source.message_row_version;
      l_source.source_content_sha256 := rec_source.source_content_sha256;
      orac_api.conversation_summary_sources_tapi.ins(l_source);
    end loop;

    l_request.status_code := c_status_completed;
    l_request.checkpoint_id := l_checkpoint.checkpoint_id;
    l_request.last_error_code := null;
    l_request.last_error_message := null;
    l_request.next_attempt_on := systimestamp;
    orac_api.conversation_memory_requests_tapi.upd(l_request);
    p_checkpoint_id := l_checkpoint.checkpoint_id;
  exception
    when dup_val_on_index then
      rollback;
      select checkpoint_id
        into p_checkpoint_id
        from orac_api.conversation_summary_checkpoints_v
       where conversation_id = l_request.conversation_id
         and first_turn_index = l_request.first_turn_index
         and last_turn_index = l_request.last_turn_index
         and materialisation_profile = l_request.materialisation_profile
         and prompt_version = l_request.prompt_version;
      select *
        into l_request
        from orac_api.conversation_memory_requests_v
       where memory_request_id = p_memory_request_id;
      l_request.status_code := c_status_completed;
      l_request.checkpoint_id := p_checkpoint_id;
      l_request.last_error_code := null;
      l_request.last_error_message := null;
      l_request.next_attempt_on := systimestamp;
      orac_api.conversation_memory_requests_tapi.upd(l_request);
  end complete_request;

  procedure record_failure(
    p_memory_request_id in number,
    p_error_code        in varchar2,
    p_error_message     in varchar2,
    p_retryable         in char
  )
  is
    l_request orac_api.conversation_memory_requests_v%rowtype;
  begin
    select *
      into l_request
      from orac_api.conversation_memory_requests_v
     where memory_request_id = p_memory_request_id;
    if l_request.status_code = c_status_completed
    then
      return;
    end if;
    l_request.attempt_count := l_request.attempt_count + 1;
    l_request.last_error_code := substr(required_text(p_error_code, 'Error code'), 1, 100);
    l_request.last_error_message := substr(p_error_message, 1, 1000);
    if upper(trim(p_retryable)) = 'Y'
       and l_request.attempt_count < l_request.max_attempts
    then
      l_request.status_code := c_status_retry_wait;
      l_request.next_attempt_on := systimestamp
        + numtodsinterval(power(2, least(l_request.attempt_count, 8)), 'MINUTE');
    else
      l_request.status_code := c_status_failed;
      l_request.next_attempt_on := systimestamp;
    end if;
    orac_api.conversation_memory_requests_tapi.upd(l_request);
  end record_failure;

  procedure open_summary_candidates(
    p_principal_username   in varchar2,
    p_embedding_model      in varchar2,
    p_embedding_dimensions in number,
    p_candidate_limit      in number,
    p_candidates              out sys_refcursor
  )
  is
    l_user_id number;
  begin
    l_user_id := active_user_id(p_principal_username);
    if l_user_id is null or p_candidate_limit <= 0 or p_embedding_dimensions <= 0
    then
      open p_candidates for select 1 checkpoint_id from dual where 1 = 0;
      return;
    end if;
    open p_candidates for
      select checkpoint_id,
             checkpoint.conversation_id,
             first_turn_index,
             last_turn_index,
             summary_text,
             summary_embedding,
             embedding_model,
             prompt_version,
             source_digest,
             checkpoint.created_on
        from orac_api.conversation_summary_checkpoints_v checkpoint
        join orac_api.conversations_v conversation
          on conversation.conversation_id = checkpoint.conversation_id
       where conversation.user_id = l_user_id
         and checkpoint.embedding_model = p_embedding_model
         and checkpoint.embedding_dimensions = p_embedding_dimensions
       order by checkpoint.created_on desc, checkpoint.checkpoint_id desc
       fetch first p_candidate_limit rows only;
  end open_summary_candidates;

  procedure open_source_candidates(
    p_principal_username    in varchar2,
    p_checkpoint_ids_json  in clob,
    p_embedding_model       in varchar2,
    p_embedding_dimensions in number,
    p_candidate_limit       in number,
    p_candidates               out sys_refcursor
  )
  is
    l_user_id number;
  begin
    l_user_id := active_user_id(p_principal_username);
    if l_user_id is null or p_candidate_limit <= 0 or p_embedding_dimensions <= 0
    then
      open p_candidates for select 1 checkpoint_id from dual where 1 = 0;
      return;
    end if;
    open p_candidates for
      select source.checkpoint_id,
             checkpoint.conversation_id,
             source.message_id,
             source.source_position,
             source.turn_index,
             message.role,
             json_value(message.content, '$.text' returning clob) source_text,
             source.message_row_version,
             source.source_content_sha256,
             embedding.embedding,
             message.created_on
        from json_table(
               p_checkpoint_ids_json,
               '$[*]' columns (checkpoint_id number path '$')
             ) requested
        join orac_api.conversation_summary_checkpoints_v checkpoint
          on checkpoint.checkpoint_id = requested.checkpoint_id
        join orac_api.conversations_v conversation
          on conversation.conversation_id = checkpoint.conversation_id
         and conversation.user_id = l_user_id
        join orac_api.conversation_summary_sources_v source
          on source.checkpoint_id = checkpoint.checkpoint_id
        join orac_api.messages_v message
          on message.message_id = source.message_id
         and message.conversation_id = checkpoint.conversation_id
         and message.turn_index = source.turn_index
         and message.row_version = source.message_row_version
        join orac_api.message_embeddings_v embedding
          on embedding.message_id = message.message_id
         and embedding.chunk_index = 1
         and embedding.embedding_model = p_embedding_model
       where json_value(
               embedding.content_snapshot,
               '$.source_content_sha256'
             ) = source.source_content_sha256
         and json_value(embedding.content_snapshot, '$.source_row_version' returning number)
               = source.message_row_version
       order by requested.checkpoint_id, source.source_position
       fetch first p_candidate_limit rows only;
  end open_source_candidates;
end conversation_memory_api;
/
--rollback drop package body orac_code.conversation_memory_api;
