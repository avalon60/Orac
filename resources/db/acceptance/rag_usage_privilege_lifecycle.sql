-- Author: Clive Bostock
-- Date: 24-Aug-2026
-- Purpose: Exercise ID-based RAG grants and exact-row soft revocation in a rollback-only transaction.
-- Usage: sql -S -name orac-db @resources/db/acceptance/rag_usage_privilege_lifecycle.sql
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

whenever sqlerror exit failure rollback

set define off
set feedback on
set serveroutput on size unlimited

declare
  l_username varchar2(4000 char);

  procedure assert_result(
    p_actual   in varchar2,
    p_expected in varchar2,
    p_message  in varchar2
  )
  is
  begin
    if p_actual <> p_expected
    then
      raise_application_error(
        -20980,
        p_message || ' Expected ' || p_expected || ', received ' || p_actual || '.'
      );
    end if;
  end assert_result;

  procedure exercise_scope(p_scope_type in varchar2)
  is
    l_scope_id          number;
    l_existing_id       number;
    l_existing_version  number;
    l_first_id          number;
    l_first_version     number;
    l_granted_version   number;
    l_second_id         number;
    l_second_version    number;
    l_expired_id        number;
    l_current_id        number;
    l_current_version   number;
    l_result            varchar2(100 char);
    l_active_count      number;
    l_history_count     number;
    l_before_count      number;
    l_after_count       number;
    l_revoked_by        varchar2(4000 char);
    l_revoke_reason     varchar2(4000 char);
    l_revoked_on        timestamp with time zone;
    l_stored_active_yn  varchar2(1 char);
    l_privilege_state   varchar2(30 char);
  begin
    select return_value
      into l_scope_id
      from (
        select return_value
          from orac_code.rag_usage_scope_lov_v
         where scope_type = p_scope_type
         order by return_value
      )
     where rownum = 1;

    begin
      select rag_usage_privilege_id, row_version
        into l_existing_id, l_existing_version
        from orac_code.rag_usage_privileges_v
       where username = l_username
         and knowledge_scope_id = l_scope_id
         and stored_active_yn = 'Y';

      l_result := orac_code.rag_usage_privilege_api.revoke_scope_usage_by_id(
        p_rag_usage_privilege_id => l_existing_id,
        p_row_version            => l_existing_version,
        p_revoked_by             => 'RAG_USAGE_ACCEPTANCE',
        p_revoke_reason_code     => 'TEST_SETUP'
      );
      assert_result(l_result, 'RAG_USAGE_REVOKED', 'Test setup revoke failed.');
    exception
      when no_data_found then
        null;
    end;

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_status_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id
    );
    assert_result(
      l_result,
      'RAG_USAGE_GRANT_AVAILABLE',
      'New grant was not reported as available.'
    );

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id,
      p_granted_by         => 'RAG_USAGE_ACCEPTANCE',
      p_grant_reason_code  => 'ACCEPTANCE_GRANT'
    );
    assert_result(l_result, 'RAG_USAGE_GRANTED', 'ID-based grant failed.');

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_status_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id
    );
    assert_result(
      l_result,
      'RAG_USAGE_ALREADY_GRANTED',
      'Current grant was not reported as redundant.'
    );

    select count(*)
      into l_before_count
      from orac_code.rag_usage_privileges_v
     where username = l_username
       and knowledge_scope_id = l_scope_id;

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id,
      p_granted_by         => 'RAG_USAGE_ACCEPTANCE',
      p_grant_reason_code  => 'DUPLICATE_ACTIVE'
    );
    assert_result(
      l_result,
      'RAG_USAGE_ALREADY_GRANTED',
      'Duplicate current grant was not rejected.'
    );

    select count(*)
      into l_after_count
      from orac_code.rag_usage_privileges_v
     where username = l_username
       and knowledge_scope_id = l_scope_id;

    if l_after_count <> l_before_count
    then
      raise_application_error(
        -20983,
        'Duplicate current grant changed privilege history.'
      );
    end if;

    select rag_usage_privilege_id, row_version
      into l_first_id, l_first_version
      from orac_code.rag_usage_privileges_v
     where username = l_username
       and knowledge_scope_id = l_scope_id
       and stored_active_yn = 'Y';

    l_granted_version := l_first_version;

    l_result := orac_code.rag_usage_privilege_api.revoke_scope_usage_by_id(
      p_rag_usage_privilege_id => l_first_id,
      p_row_version            => l_first_version + 1,
      p_revoked_by             => 'RAG_USAGE_ACCEPTANCE',
      p_revoke_reason_code     => 'TAMPERED_VERSION'
    );
    assert_result(
      l_result,
      'RAG_USAGE_PRIVILEGE_CHANGED',
      'Tampered row version was accepted.'
    );

    l_result := orac_code.rag_usage_privilege_api.revoke_scope_usage_by_id(
      p_rag_usage_privilege_id => -999999999,
      p_row_version            => 1,
      p_revoked_by             => 'RAG_USAGE_ACCEPTANCE',
      p_revoke_reason_code     => 'UNKNOWN_ROW'
    );
    assert_result(
      l_result,
      'RAG_USAGE_PRIVILEGE_UNKNOWN',
      'Unknown privilege row was not rejected.'
    );

    l_result := orac_code.rag_usage_privilege_api.revoke_scope_usage_by_id(
      p_rag_usage_privilege_id => l_first_id,
      p_row_version            => l_first_version,
      p_revoked_by             => 'RAG_USAGE_ACCEPTANCE',
      p_revoke_reason_code     => 'ACCEPTANCE_REVOKE'
    );
    assert_result(l_result, 'RAG_USAGE_REVOKED', 'Exact-row revoke failed.');

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_status_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id
    );
    assert_result(
      l_result,
      'RAG_USAGE_GRANT_AVAILABLE',
      'Revoked grant prevented a re-grant.'
    );

    select stored_active_yn,
           privilege_state,
           revoked_on,
           revoked_by,
           revoke_reason_code,
           row_version
      into l_stored_active_yn,
           l_privilege_state,
           l_revoked_on,
           l_revoked_by,
           l_revoke_reason,
           l_first_version
      from orac_code.rag_usage_privileges_v
     where rag_usage_privilege_id = l_first_id;

    if l_stored_active_yn <> 'N'
       or l_privilege_state <> 'REVOKED'
       or l_revoked_on is null
       or l_revoked_by <> 'RAG_USAGE_ACCEPTANCE'
       or l_revoke_reason <> 'ACCEPTANCE_REVOKE'
       or l_first_version <= l_granted_version
    then
      raise_application_error(
        -20981,
        'Stored-active privilege was not versioned and soft-revoked with its audit metadata.'
      );
    end if;

    l_result := orac_code.rag_usage_privilege_api.revoke_scope_usage_by_id(
      p_rag_usage_privilege_id => l_first_id,
      p_row_version            => l_first_version,
      p_revoked_by             => 'RAG_USAGE_ACCEPTANCE',
      p_revoke_reason_code     => 'SECOND_REVOKE'
    );
    assert_result(
      l_result,
      'RAG_USAGE_ALREADY_REVOKED',
      'Already-revoked row was not rejected.'
    );

    l_result := orac_code.rag_usage_privilege_api.revoke_scope_usage_by_id(
      p_rag_usage_privilege_id => l_first_id,
      p_row_version            => l_first_version - 1,
      p_revoked_by             => 'RAG_USAGE_ACCEPTANCE',
      p_revoke_reason_code     => 'STALE_VERSION'
    );
    assert_result(
      l_result,
      'RAG_USAGE_PRIVILEGE_CHANGED',
      'Stale row version was not rejected.'
    );

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id,
      p_granted_by         => 'RAG_USAGE_ACCEPTANCE',
      p_grant_reason_code  => 'ACCEPTANCE_REGRANT'
    );
    assert_result(l_result, 'RAG_USAGE_GRANTED', 'Re-grant failed.');

    select rag_usage_privilege_id, row_version
      into l_second_id, l_second_version
      from orac_code.rag_usage_privileges_v
     where username = l_username
       and knowledge_scope_id = l_scope_id
       and stored_active_yn = 'Y';

    select count(*),
           sum(case when stored_active_yn = 'Y' then 1 else 0 end)
      into l_history_count, l_active_count
      from orac_code.rag_usage_privileges_v
     where username = l_username
       and knowledge_scope_id = l_scope_id
       and rag_usage_privilege_id in (l_first_id, l_second_id);

    if l_second_id = l_first_id
       or l_history_count <> 2
       or l_active_count <> 1
    then
      raise_application_error(
        -20982,
        'Re-grant did not create a new history row with one stored-active grant.'
      );
    end if;

    l_result := orac_code.rag_usage_privilege_api.revoke_scope_usage_by_id(
      p_rag_usage_privilege_id => l_second_id,
      p_row_version            => l_second_version,
      p_revoked_by             => 'RAG_USAGE_ACCEPTANCE',
      p_revoke_reason_code     => 'EXPIRED_CASE_SETUP'
    );
    assert_result(
      l_result,
      'RAG_USAGE_REVOKED',
      'Expired-grant setup revoke failed.'
    );

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id,
      p_effective_on       => systimestamp - interval '2' day,
      p_expires_on         => systimestamp - interval '1' day,
      p_granted_by         => 'RAG_USAGE_ACCEPTANCE',
      p_grant_reason_code  => 'EXPIRED_GRANT'
    );
    assert_result(l_result, 'RAG_USAGE_GRANTED', 'Expired grant setup failed.');

    select rag_usage_privilege_id
      into l_expired_id
      from orac_code.rag_usage_privileges_v
     where username = l_username
       and knowledge_scope_id = l_scope_id
       and stored_active_yn = 'Y';

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_status_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id
    );
    assert_result(
      l_result,
      'RAG_USAGE_GRANT_AVAILABLE',
      'Expired grant prevented a re-grant.'
    );

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id,
      p_granted_by         => 'RAG_USAGE_ACCEPTANCE',
      p_grant_reason_code  => 'AFTER_EXPIRY'
    );
    assert_result(l_result, 'RAG_USAGE_GRANTED', 'Re-grant after expiry failed.');

    select stored_active_yn, revoke_reason_code
      into l_stored_active_yn, l_revoke_reason
      from orac_code.rag_usage_privileges_v
     where rag_usage_privilege_id = l_expired_id;

    if l_stored_active_yn <> 'N' or l_revoke_reason <> 'EXPIRED'
    then
      raise_application_error(
        -20984,
        'Re-grant did not soft-close the expired historical row.'
      );
    end if;

    select rag_usage_privilege_id, row_version
      into l_current_id, l_current_version
      from orac_code.rag_usage_privileges_v
     where username = l_username
       and knowledge_scope_id = l_scope_id
       and stored_active_yn = 'Y';

    l_result := orac_code.rag_usage_privilege_api.revoke_scope_usage_by_id(
      p_rag_usage_privilege_id => l_current_id,
      p_row_version            => l_current_version,
      p_revoked_by             => 'RAG_USAGE_ACCEPTANCE',
      p_revoke_reason_code     => 'SCHEDULED_CASE_SETUP'
    );
    assert_result(
      l_result,
      'RAG_USAGE_REVOKED',
      'Scheduled-grant setup revoke failed.'
    );

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id,
      p_effective_on       => systimestamp + interval '1' day,
      p_expires_on         => systimestamp + interval '2' day,
      p_granted_by         => 'RAG_USAGE_ACCEPTANCE',
      p_grant_reason_code  => 'SCHEDULED_GRANT'
    );
    assert_result(l_result, 'RAG_USAGE_GRANTED', 'Scheduled grant setup failed.');

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_status_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id
    );
    assert_result(
      l_result,
      'RAG_USAGE_ALREADY_GRANTED',
      'Scheduled stored-active grant was not reported as redundant.'
    );

    select count(*)
      into l_before_count
      from orac_code.rag_usage_privileges_v
     where username = l_username
       and knowledge_scope_id = l_scope_id;

    l_result := orac_code.rag_usage_privilege_api.grant_scope_usage_by_id(
      p_username           => l_username,
      p_knowledge_scope_id => l_scope_id,
      p_effective_on       => systimestamp + interval '3' day,
      p_expires_on         => systimestamp + interval '4' day,
      p_granted_by         => 'RAG_USAGE_ACCEPTANCE',
      p_grant_reason_code  => 'OVERLAPPING_SCHEDULED'
    );
    assert_result(
      l_result,
      'RAG_USAGE_ALREADY_GRANTED',
      'Conflicting scheduled grant was not rejected.'
    );

    select count(*),
           sum(case when stored_active_yn = 'Y' then 1 else 0 end)
      into l_after_count, l_active_count
      from orac_code.rag_usage_privileges_v
     where username = l_username
       and knowledge_scope_id = l_scope_id;

    if l_after_count <> l_before_count or l_active_count <> 1
    then
      raise_application_error(
        -20985,
        'Scheduled duplicate changed history or created another stored-active grant.'
      );
    end if;
  end exercise_scope;
begin
  select username
    into l_username
    from (
      select username
        from orac_api.users_v
       where is_active = 'Y'
       order by user_id
    )
   where rownum = 1;

  exercise_scope('PROJECT');
  exercise_scope('PLUGIN');

  dbms_output.put_line('RAG_USAGE_PRIVILEGE_LIFECYCLE_OK');
  rollback;
exception
  when others then
    rollback;
    raise;
end;
/

rollback;
