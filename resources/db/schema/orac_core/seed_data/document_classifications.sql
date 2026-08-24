--liquibase formatted sql

--changeset clive:seed_orac_core_doc_class_domain context:core labels:core stripComments:false
merge into orac_core.domain_codes dst
using (
  select 'DOC_CLASS' domain_code
       , 'Document Classification' display_name
       , 'Controlled classifications assigned to knowledge document versions.' description
    from dual
) src
   on (dst.domain_code = src.domain_code)
 when matched then update
      set dst.display_name       = src.display_name
        , dst.description        = src.description
        , dst.active_yn          = 'Y'
        , dst.system_required_yn = 'Y'
 when not matched then insert
      ( domain_code
      , display_name
      , description
      , active_yn
      , system_required_yn
      )
 values
      ( src.domain_code
      , src.display_name
      , src.description
      , 'Y'
      , 'Y'
      );

--rollback select 1 from dual;

--changeset clive:seed_orac_core_doc_class_values context:core labels:core stripComments:false splitStatements:false endDelimiter:/
declare
  procedure seed_value(
    p_code         in varchar2,
    p_display      in varchar2,
    p_description  in varchar2,
    p_sequence     in number
  )
  is
  begin
    merge into orac_core.domain_ref_values dst
    using (
      select 'DOC_CLASS' domain_code
           , p_code ref_value_code
           , p_display display_value
           , p_description description
           , p_sequence display_sequence
        from dual
    ) src
       on (    dst.domain_code    = src.domain_code
           and dst.ref_value_code = src.ref_value_code)
     when matched then update
          set dst.display_value       = src.display_value
            , dst.description         = src.description
            , dst.display_sequence    = src.display_sequence
            , dst.active_yn           = 'Y'
            , dst.system_required_yn  = 'Y'
     when not matched then insert
          ( domain_code
          , ref_value_code
          , display_value
          , description
          , display_sequence
          , active_yn
          , system_required_yn
          )
     values
          ( src.domain_code
          , src.ref_value_code
          , src.display_value
          , src.description
          , src.display_sequence
          , 'Y'
          , 'Y'
          );
  end seed_value;

begin
  seed_value(
    'RAW_REFERENCE',
    'Raw Reference',
    'Untransformed reference material.',
    10
  );
  seed_value(
    'CONCISE_KNOWLEDGE_NOTE',
    'Concise Knowledge Note',
    'Classification for concise knowledge notes.',
    20
  );
  seed_value(
    'IMPLEMENTATION_DECISION_RECORD',
    'Implementation Decision Record',
    'Classification for implementation decisions.',
    30
  );
  seed_value(
    'TECHNICAL_MANUAL',
    'Technical Manual',
    'Classification for technical manuals.',
    40
  );
  seed_value(
    'TROUBLESHOOTING_NOTE',
    'Troubleshooting Note',
    'Classification for troubleshooting material.',
    50
  );
  seed_value(
    'AUTOMATION_RULE_NOTE',
    'Automation Rule Note',
    'Classification for automation-rule material.',
    60
  );
end;
/

--rollback select 1 from dual;
