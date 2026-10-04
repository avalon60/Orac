--liquibase formatted sql
--changeset clive:create_package_body_orac_api_conversation_title_requests_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.conversation_title_requests_tapi as
  procedure ins(p_row in out nocopy orac_api.conversation_title_requests_v%rowtype) is
  begin
    insert into orac_core.conversation_title_requests
      (conversation_id, status_code, attempts, max_attempts, next_attempt_on)
    values
      (p_row.conversation_id, coalesce(p_row.status_code, 'PENDING'),
       coalesce(p_row.attempts, 0), coalesce(p_row.max_attempts, 3),
       coalesce(p_row.next_attempt_on, systimestamp))
    returning title_request_id into p_row.title_request_id;
  end ins;

  procedure upd(p_title_request_id in number, p_row in orac_api.conversation_title_requests_v%rowtype) is
  begin
    update orac_core.conversation_title_requests
       set status_code = p_row.status_code,
           attempts = p_row.attempts,
           next_attempt_on = p_row.next_attempt_on,
           lease_owner = p_row.lease_owner,
           lease_token = p_row.lease_token,
           lease_expires_on = p_row.lease_expires_on,
           last_error_message = p_row.last_error_message,
           completed_on = p_row.completed_on,
           updated_on = systimestamp,
           updated_by = coalesce(sys_context('userenv', 'client_identifier'), user),
           row_version = row_version + 1
     where title_request_id = p_title_request_id;
  end upd;

  function enqueue_request(p_conversation_id in number) return number is
    l_request_id number;
  begin
    begin
      select title_request_id into l_request_id
        from orac_core.conversation_title_requests
       where conversation_id = p_conversation_id;
      return l_request_id;
    exception when no_data_found then null;
    end;
    insert into orac_core.conversation_title_requests (conversation_id)
    values (p_conversation_id)
    returning title_request_id into l_request_id;
    return l_request_id;
  exception
    when dup_val_on_index then
      select title_request_id into l_request_id
        from orac_core.conversation_title_requests
       where conversation_id = p_conversation_id;
      return l_request_id;
  end enqueue_request;

  function try_claim_next_request(p_owner_id in varchar2, p_lease_seconds in number) return number is
    l_request_id number;
    l_token varchar2(64 char) := lower(rawtohex(sys_guid()));
    cursor c_request is
      select title_request_id
        from orac_core.conversation_title_requests
       where attempts < max_attempts
         and next_attempt_on <= systimestamp
         and (status_code in ('PENDING', 'RETRY')
              or (status_code = 'PROCESSING' and lease_expires_on < systimestamp))
       order by created_on
       for update skip locked;
  begin
    update orac_core.conversation_title_requests
       set status_code = 'FAILED', lease_owner = null, lease_token = null,
           lease_expires_on = null, updated_on = systimestamp,
           updated_by = user, row_version = row_version + 1
     where status_code = 'PROCESSING'
       and lease_expires_on < systimestamp
       and attempts >= max_attempts;
    open c_request;
    fetch c_request into l_request_id;
    if c_request%notfound then
      close c_request;
      return null;
    end if;
    update orac_core.conversation_title_requests
       set status_code = 'PROCESSING', attempts = attempts + 1,
           lease_owner = substr(p_owner_id, 1, 500), lease_token = l_token,
           lease_expires_on = systimestamp + numtodsinterval(p_lease_seconds, 'SECOND'),
           updated_on = systimestamp, updated_by = user, row_version = row_version + 1
     where title_request_id = l_request_id;
    close c_request;
    return l_request_id;
  end try_claim_next_request;

  procedure complete_request(p_request_id in number, p_owner_id in varchar2, p_lease_token in varchar2, p_title in varchar2) is
    l_conversation_id number;
  begin
    update orac_core.conversation_title_requests
       set status_code = 'COMPLETED', completed_on = systimestamp,
           lease_owner = null, lease_token = null, lease_expires_on = null,
           last_error_message = null, updated_on = systimestamp,
           updated_by = user, row_version = row_version + 1
     where title_request_id = p_request_id
       and lease_owner = p_owner_id and lease_token = p_lease_token
    returning conversation_id into l_conversation_id;
    update orac_core.conversations
       set title = substr(p_title, 1, 120), updated_on = systimestamp,
           updated_by = user, row_version = row_version + 1
     where conversation_id = l_conversation_id
       and (title is null or lower(trim(title)) = 'brief exchange...');
  end complete_request;

  procedure fail_request(p_request_id in number, p_owner_id in varchar2, p_lease_token in varchar2, p_error_message in varchar2, p_retryable_yn in varchar2) is
  begin
    update orac_core.conversation_title_requests
       set status_code = case when upper(p_retryable_yn) = 'Y' and attempts < max_attempts then 'RETRY' else 'FAILED' end,
           next_attempt_on = systimestamp + numtodsinterval(least(300, 10 * power(2, greatest(0, attempts - 1))), 'SECOND'),
           lease_owner = null, lease_token = null, lease_expires_on = null,
           last_error_message = substr(p_error_message, 1, 1000),
           updated_on = systimestamp, updated_by = user, row_version = row_version + 1
     where title_request_id = p_request_id
       and lease_owner = p_owner_id and lease_token = p_lease_token;
  end fail_request;
end conversation_title_requests_tapi;
/
--rollback drop package body orac_api.conversation_title_requests_tapi;
