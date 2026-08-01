--liquibase formatted sql

--changeset clive:seed_orac_dropbox_seed_data_drop_processing_profiles context:plugin,prod labels:plugin,drop_box stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: seed named drop-box processing profiles before location FK enforcement

declare
  l_invalid_profiles varchar2(4000 char);

  procedure upsert_profile(
    p_profile_code         in orac_dropbox.drop_processing_profile.profile_code%type,
    p_display_name         in orac_dropbox.drop_processing_profile.display_name%type,
    p_description          in orac_dropbox.drop_processing_profile.description%type,
    p_default_instruction  in clob,
    p_sort_order           in orac_dropbox.drop_processing_profile.sort_order%type
  )
  is
  begin
    merge into orac_dropbox.drop_processing_profile dst
    using (
      select p_profile_code profile_code,
             p_display_name display_name,
             p_description description,
             p_default_instruction default_instruction,
             p_sort_order sort_order
        from dual
    ) src
    on (dst.profile_code = src.profile_code)
    when matched then
      update set
        dst.display_name        = src.display_name,
        dst.description         = src.description,
        dst.default_instruction = src.default_instruction,
        dst.active_yn           = 'Y',
        dst.system_yn           = 'Y',
        dst.sort_order          = src.sort_order
    when not matched then
      insert (
        profile_code,
        display_name,
        description,
        default_instruction,
        active_yn,
        system_yn,
        sort_order
      ) values (
        src.profile_code,
        src.display_name,
        src.description,
        src.default_instruction,
        'Y',
        'Y',
        src.sort_order
      );
  end upsert_profile;
begin
  select listagg(processing_profile, ', ') within group (order by processing_profile)
    into l_invalid_profiles
    from (
      select distinct processing_profile
        from orac_dropbox.drop_location
       where processing_profile is not null
         and not regexp_like(processing_profile, '^[a-z][a-z0-9_]{1,99}$')
    );

  if l_invalid_profiles is not null
  then
    raise_application_error(
      -20030,
      'Invalid ORAC_DROPBOX.DROP_LOCATION.PROCESSING_PROFILE values block profile FK creation: '
      || l_invalid_profiles
    );
  end if;

  upsert_profile(
    'raw_reference',
    'Raw Reference',
    'Non-transforming compatibility classification for raw reference material.',
    null,
    10
  );

  upsert_profile(
    'concise_knowledge_note',
    'Concise Knowledge Note',
    'Non-transforming compatibility classification for concise knowledge notes.',
    null,
    20
  );

  upsert_profile(
    'implementation_decision_record',
    'Implementation Decision Record',
    'Non-transforming compatibility classification for implementation decisions.',
    null,
    30
  );

  upsert_profile(
    'technical_manual',
    'Technical Manual',
    'Non-transforming compatibility classification for technical manuals.',
    null,
    40
  );

  upsert_profile(
    'troubleshooting_note',
    'Troubleshooting Note',
    'Non-transforming compatibility classification for troubleshooting material.',
    null,
    50
  );

  upsert_profile(
    'automation_rule_note',
    'Automation Rule Note',
    'Non-transforming compatibility classification for automation rule notes.',
    null,
    60
  );

  insert into orac_dropbox.drop_processing_profile (
    profile_code,
    display_name,
    description,
    default_instruction,
    active_yn,
    system_yn,
    sort_order
  )
  select legacy.processing_profile,
         'Legacy Profile: ' || legacy.processing_profile,
         'Inactive compatibility profile created from existing drop location data during migration.',
         to_clob('Legacy compatibility profile. This profile is inactive and must be replaced with an active system profile before the location can be scanned.'),
         'N',
         'N',
         1000
    from (
      select distinct loc.processing_profile
        from orac_dropbox.drop_location loc
       where loc.processing_profile is not null
         and regexp_like(loc.processing_profile, '^[a-z][a-z0-9_]{1,99}$')
    ) legacy
   where not exists (
         select 1
           from orac_dropbox.drop_processing_profile prf
          where prf.profile_code = legacy.processing_profile
         );
end;
/

--rollback delete from orac_dropbox.drop_processing_profile where system_yn = 'Y' and profile_code in ('raw_reference', 'concise_knowledge_note', 'implementation_decision_record', 'technical_manual', 'troubleshooting_note', 'automation_rule_note');
