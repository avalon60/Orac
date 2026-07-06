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
    'Use the source as reference material. Preserve facts and provenance; do not summarise or rewrite unless a location-specific instruction says otherwise.',
    to_clob('Treat the source as reference material. Preserve the original meaning, important facts, terminology, and provenance. Do not summarise, rewrite, or infer new conclusions unless the location-specific instruction explicitly requests it.'),
    10
  );

  upsert_profile(
    'concise_knowledge_note',
    'Concise Knowledge Note',
    'Create a short reusable note containing durable facts, operational guidance, and key context.',
    to_clob('Create a concise knowledge note. Keep durable facts, operational guidance, important caveats, and reusable context. Remove incidental wording, repetition, and temporary details unless they are necessary to understand the source.'),
    20
  );

  upsert_profile(
    'implementation_decision_record',
    'Implementation Decision Record',
    'Extract the problem, decision, rationale, consequences, and follow-up work from the source.',
    to_clob('Create an implementation decision record. Identify the problem, the decision made or proposed, rationale, alternatives considered where present, consequences, risks, and concrete follow-up work. Do not invent decisions not supported by the source.'),
    30
  );

  upsert_profile(
    'technical_manual',
    'Technical Manual',
    'Turn the source into procedural or reference documentation suitable for engineers and operators.',
    to_clob('Create technical manual content. Organise concepts, prerequisites, procedures, configuration values, examples, warnings, and verification steps. Prefer precise, repeatable instructions over narrative summary.'),
    40
  );

  upsert_profile(
    'troubleshooting_note',
    'Troubleshooting Note',
    'Extract symptoms, likely causes, diagnostics, fixes, and verification steps.',
    to_clob('Create a troubleshooting note. Capture symptoms, affected components, likely causes, diagnostic checks, remediation steps, verification steps, and known limits. Keep commands and error text precise.'),
    50
  );

  upsert_profile(
    'automation_rule_note',
    'Automation Rule Note',
    'Extract trigger, conditions, actions, safety constraints, and expected outcomes for automation rules.',
    to_clob('Create an automation rule note. Identify trigger events, required conditions, actions, safety constraints, failure handling, and expected outcomes. Make assumptions explicit and do not expand authority beyond the source.'),
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
