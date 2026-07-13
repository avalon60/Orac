--liquibase formatted sql

--changeset clive:drop_box_package_body_drop_box_api context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
create or replace package body orac_dropbox.drop_box_api as

  function observation_exists(
    p_drop_location_id  in orac_dropbox.drop_job.drop_location_id%type,
    p_source_path       in orac_dropbox.drop_job.source_path%type,
    p_source_size_bytes in orac_dropbox.drop_job.source_size_bytes%type,
    p_source_mtime      in orac_dropbox.drop_job.source_mtime%type
  ) return number
  is
    l_count number;
  begin
    select count(*)
      into l_count
      from orac_dropbox.drop_job
     where drop_location_id  = p_drop_location_id
       and source_path       = p_source_path
       and source_size_bytes = p_source_size_bytes
       and source_mtime      = p_source_mtime;

    if l_count > 0
    then
      return 1;
    end if;
    return 0;
  end observation_exists;

  procedure enqueue_job(
    p_drop_location_id  in orac_dropbox.drop_job.drop_location_id%type,
    p_source_path       in orac_dropbox.drop_job.source_path%type,
    p_source_filename   in orac_dropbox.drop_job.source_filename%type,
    p_source_size_bytes in orac_dropbox.drop_job.source_size_bytes%type,
    p_source_mtime      in orac_dropbox.drop_job.source_mtime%type,
    p_stable_on         in orac_dropbox.drop_job.stable_on%type,
    p_source_hash       in orac_dropbox.drop_job.source_hash%type
  )
  is
    l_job_id             orac_dropbox.drop_job.drop_job_id%type;
    l_scope_type         orac_dropbox.drop_location.target_scope_type%type;
    l_scope_key          orac_dropbox.drop_location.target_scope_key%type;
    l_processing_profile orac_dropbox.drop_location.processing_profile%type;
    l_profile_instruction clob;
    l_instruction        orac_dropbox.drop_location.processing_instruction%type;
  begin
    if observation_exists(
         p_drop_location_id,
         p_source_path,
         p_source_size_bytes,
         p_source_mtime
       ) = 1
    then
      return;
    end if;

    select loc.target_scope_type,
           loc.target_scope_key,
           loc.processing_profile,
           prf.default_instruction,
           loc.processing_instruction
      into l_scope_type,
           l_scope_key,
           l_processing_profile,
           l_profile_instruction,
           l_instruction
      from orac_dropbox.drop_location loc
      join orac_dropbox.drop_processing_profile prf
        on prf.profile_code = loc.processing_profile
       and prf.active_yn = 'Y'
     where loc.drop_location_id = p_drop_location_id;

    insert into orac_dropbox.drop_job (
      drop_location_id,
      source_path,
      source_filename,
      source_hash,
      source_size_bytes,
      source_mtime,
      stable_on,
      status_code,
      effective_scope_type,
      effective_scope_key,
      effective_processing_profile,
      effective_profile_instruction,
      effective_instruction
    )
    values (
      p_drop_location_id,
      p_source_path,
      p_source_filename,
      p_source_hash,
      p_source_size_bytes,
      p_source_mtime,
      p_stable_on,
      'queued',
      l_scope_type,
      l_scope_key,
      l_processing_profile,
      l_profile_instruction,
      l_instruction
    )
    returning drop_job_id into l_job_id;

    insert into orac_dropbox.drop_job_event (
      drop_job_id,
      event_type,
      event_message
    )
    values (
      l_job_id,
      'queued',
      'Drop-box source file queued for future ingestion handoff.'
    );
  exception
    when dup_val_on_index then
      null;
    when no_data_found then
      raise_application_error(
        -20020,
        'Drop location is missing an active processing profile.'
      );
  end enqueue_job;

  procedure update_status(
    p_drop_job_id   in orac_dropbox.drop_job.drop_job_id%type,
    p_status_code   in orac_dropbox.drop_job.status_code%type,
    p_error_message in orac_dropbox.drop_job.error_message%type default null,
    p_document_id   in orac_dropbox.drop_job.document_id%type default null
  )
  is
  begin
    update orac_dropbox.drop_job
       set status_code   = p_status_code,
           error_message = p_error_message,
           document_id   = coalesce(p_document_id, document_id),
           started_on    = case when p_status_code = 'processing' then systimestamp else started_on end,
           completed_on  = case
                             when p_status_code in ('completed', 'failed', 'quarantined') then systimestamp
                             else completed_on
                           end
     where drop_job_id = p_drop_job_id;

    insert into orac_dropbox.drop_job_event (
      drop_job_id,
      event_type,
      event_message
    )
    values (
      p_drop_job_id,
      p_status_code,
      p_error_message
    );
  end update_status;

  procedure record_core_acceptance(
    p_drop_job_id                    in orac_dropbox.drop_job.drop_job_id%type,
    p_knowledge_ingestion_request_id in orac_dropbox.drop_job.knowledge_ingestion_request_id%type
  )
  is
    l_existing_request_id orac_dropbox.drop_job.knowledge_ingestion_request_id%type;
    l_existing_status     orac_dropbox.drop_job.status_code%type;
  begin
    if p_knowledge_ingestion_request_id is null
    then
      raise_application_error(-20021, 'Knowledge ingestion request id is required.');
    end if;

    select knowledge_ingestion_request_id,
           status_code
      into l_existing_request_id,
           l_existing_status
      from orac_dropbox.drop_job
     where drop_job_id = p_drop_job_id
       for update;

    if l_existing_status = 'handed_off'
       and l_existing_request_id = p_knowledge_ingestion_request_id
    then
      return;
    end if;

    update orac_dropbox.drop_job
       set status_code = 'handed_off',
           knowledge_ingestion_request_id = p_knowledge_ingestion_request_id,
           error_message = null,
           started_on = coalesce(started_on, systimestamp),
           completed_on = null
     where drop_job_id = p_drop_job_id;

    insert into orac_dropbox.drop_job_event (
      drop_job_id,
      event_type,
      event_message
    )
    values (
      p_drop_job_id,
      'handed_off',
      'Core accepted managed-file ingestion request '
      || to_char(p_knowledge_ingestion_request_id)
      || '.'
    );
  exception
    when no_data_found then
      raise_application_error(-20022, 'Drop Box job not found.');
  end record_core_acceptance;

  function repair_missing_core_failures
    return number
  is
    l_repaired_count number := 0;
    l_event_count    number;
  begin
    for job in (
      select drop_job_id
        from orac_dropbox.drop_job
       where status_code = 'failed'
         and dbms_lob.instr(error_message, 'KNOWLEDGE_INGESTION_API') > 0
         and dbms_lob.instr(error_message, 'must be declared') > 0
       order by drop_job_id
       for update
    )
    loop
      select count(*)
        into l_event_count
        from orac_dropbox.drop_job_event evt
       where evt.drop_job_id = job.drop_job_id
         and evt.event_type = 'repair_requeued_core_handoff';

      update orac_dropbox.drop_job
         set status_code = 'queued',
             error_message = null,
             completed_on = null,
             knowledge_ingestion_request_id = null
       where drop_job_id = job.drop_job_id;

      if l_event_count = 0
      then
        insert into orac_dropbox.drop_job_event (
          drop_job_id,
          event_type,
          event_message
        )
        values (
          job.drop_job_id,
          'repair_requeued_core_handoff',
          'Requeued after Core knowledge ingestion API became available; previous failed event retained as audit history.'
        );
      end if;
      l_repaired_count := l_repaired_count + 1;
    end loop;
    return l_repaired_count;
  end repair_missing_core_failures;

end drop_box_api;
/
