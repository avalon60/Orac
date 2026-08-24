--liquibase formatted sql
-- Author: clive
-- Date: 08-Aug-2026
-- Description: Seeds shared application reference-data domains and values.

--changeset clive:seed_orac_core_application_reference_domains context:core labels:core stripComments:false splitStatements:false endDelimiter:/
declare
  procedure seed_domain(
    p_domain_code in varchar2,
    p_display_name in varchar2,
    p_description in varchar2
  )
  is
  begin
    merge into orac_core.domain_codes dst
    using (
      select p_domain_code domain_code,
             p_display_name display_name,
             p_description description
        from dual
    ) src
       on (dst.domain_code = src.domain_code)
     when matched then update
          set dst.display_name = src.display_name,
              dst.description = src.description,
              dst.active_yn = 'Y',
              dst.system_required_yn = 'Y'
     when not matched then insert
          (domain_code, display_name, description, active_yn, system_required_yn)
     values
          (src.domain_code, src.display_name, src.description, 'Y', 'Y');
  end seed_domain;

  procedure seed_value(
    p_domain_code in varchar2,
    p_ref_value_code in varchar2,
    p_display_value in varchar2,
    p_description in varchar2,
    p_display_sequence in number
  )
  is
  begin
    merge into orac_core.domain_ref_values dst
    using (
      select p_domain_code domain_code,
             p_ref_value_code ref_value_code,
             p_display_value display_value,
             p_description description,
             p_display_sequence display_sequence
        from dual
    ) src
       on (    dst.domain_code = src.domain_code
           and dst.ref_value_code = src.ref_value_code)
     when matched then update
          set dst.display_value = src.display_value,
              dst.description = src.description,
              dst.display_sequence = src.display_sequence,
              dst.active_yn = 'Y',
              dst.system_required_yn = 'Y'
     when not matched then insert
          (domain_code, ref_value_code, display_value, description,
           display_sequence, active_yn, system_required_yn)
     values
          (src.domain_code, src.ref_value_code, src.display_value,
           src.description, src.display_sequence, 'Y', 'Y');
  end seed_value;
begin
  seed_domain(
    'PREF_VALUE_TYPE',
    'Preference Value Type',
    'Logical data types supported by stored user preferences.'
  );
  seed_value('PREF_VALUE_TYPE', 'string', 'String', 'Text value.', 10);
  seed_value('PREF_VALUE_TYPE', 'number', 'Number', 'Numeric value.', 20);
  seed_value('PREF_VALUE_TYPE', 'boolean', 'Boolean', 'True or false value.', 30);
  seed_value('PREF_VALUE_TYPE', 'json', 'JSON', 'Structured JSON value.', 40);

  seed_domain(
    'PREF_CONTROL_TYPE',
    'Preference Control Type',
    'User-interface control types supported by preference metadata.'
  );
  seed_value('PREF_CONTROL_TYPE', 'text', 'Text', 'Single-line text input.', 10);
  seed_value('PREF_CONTROL_TYPE', 'textarea', 'Textarea', 'Multi-line text input.', 20);
  seed_value('PREF_CONTROL_TYPE', 'number', 'Number', 'Numeric input.', 30);
  seed_value('PREF_CONTROL_TYPE', 'checkbox', 'Checkbox', 'Checkbox input.', 40);
  seed_value('PREF_CONTROL_TYPE', 'select_list', 'Select List', 'Select-list input.', 50);
  seed_value('PREF_CONTROL_TYPE', 'select_one', 'Select One', 'Single-value selector.', 60);
  seed_value('PREF_CONTROL_TYPE', 'popup_lov', 'Popup LOV', 'Popup list-of-values selector.', 70);
  seed_value('PREF_CONTROL_TYPE', 'radio_group', 'Radio Group', 'Radio-button group.', 80);
  seed_value('PREF_CONTROL_TYPE', 'switch', 'Switch', 'Switch input.', 90);
  seed_value('PREF_CONTROL_TYPE', 'slider', 'Slider', 'Bounded numeric slider.', 100);
  seed_value('PREF_CONTROL_TYPE', 'display_only', 'Display Only', 'Read-only display control.', 110);

  seed_domain(
    'PREF_LOV_TYPE',
    'Preference LOV Type',
    'Supported sources for preference list-of-values metadata.'
  );
  seed_value('PREF_LOV_TYPE', 'static', 'Static', 'Static list of values.', 10);
  seed_value('PREF_LOV_TYPE', 'sql', 'SQL', 'SQL-backed list of values.', 20);

  seed_domain(
    'LLM_CONTEXT_POLICY',
    'LLM Context Policy',
    'Policies that determine where conversation context is managed.'
  );
  seed_value('LLM_CONTEXT_POLICY', 'app', 'Client Application', 'Context is managed by the client application.', 10);
  seed_value('LLM_CONTEXT_POLICY', 'model', 'Model', 'Context is managed by the model service.', 20);
  seed_value('LLM_CONTEXT_POLICY', 'external', 'External', 'Context is managed by an external service.', 30);
  seed_value('LLM_CONTEXT_POLICY', 'hybrid', 'Hybrid', 'Context is shared across application and external services.', 40);
  seed_value('LLM_CONTEXT_POLICY', 'unresolved', 'Unresolved', 'The context policy has not yet been resolved.', 50);

  seed_domain(
    'USER_ALIAS_TYPE',
    'User Alias Type',
    'Identity alias types that may be associated with an Orac user.'
  );
  seed_value('USER_ALIAS_TYPE', 'apple', 'Apple ID', 'Apple identity alias.', 10);
  seed_value('USER_ALIAS_TYPE', 'email', 'Email', 'Email-address identity alias.', 20);
  seed_value('USER_ALIAS_TYPE', 'google', 'Google ID', 'Google identity alias.', 30);
  seed_value('USER_ALIAS_TYPE', 'microsoft', 'Microsoft ID', 'Microsoft identity alias.', 40);
  seed_value('USER_ALIAS_TYPE', 'oauth', 'OAuth/OpenID Connect', 'OAuth or OpenID Connect subject alias.', 50);
  seed_value('USER_ALIAS_TYPE', 'os', 'O/S Login', 'Operating-system login alias.', 60);
  seed_value('USER_ALIAS_TYPE', 'short', 'Short/Nickname', 'Short name or nickname alias.', 70);

  seed_domain(
    'VECTOR_DISTANCE_METRIC',
    'Vector Distance Metric',
    'Distance metrics supported for vector embedding comparison.'
  );
  seed_value('VECTOR_DISTANCE_METRIC', 'COSINE', 'Cosine', 'Cosine distance.', 10);
  seed_value('VECTOR_DISTANCE_METRIC', 'DOT', 'Dot Product', 'Dot-product distance.', 20);
  seed_value('VECTOR_DISTANCE_METRIC', 'HAMMING', 'Hamming', 'Hamming distance.', 30);
  seed_value('VECTOR_DISTANCE_METRIC', 'JACCARD', 'Jaccard', 'Jaccard distance.', 40);
  seed_value('VECTOR_DISTANCE_METRIC', 'L2', 'Euclidean (L2)', 'Euclidean distance.', 50);
  seed_value('VECTOR_DISTANCE_METRIC', 'L2_SQUARED', 'Squared Euclidean', 'Squared Euclidean distance.', 60);
  seed_value('VECTOR_DISTANCE_METRIC', 'MANHATTAN', 'Manhattan', 'Manhattan distance.', 70);
end;
/

--rollback select 1 from dual;
