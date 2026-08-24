--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Implements atomic normalised artefact output-set registration.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_body_orac_code_knowledge_artefact_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.knowledge_artefact_api
as
  c_max_members       constant pls_integer := 256;
  c_max_envelope_size constant pls_integer := 1048576;
  c_max_metadata_size constant pls_integer := 16384;
  c_markdown_media    constant varchar2(255) := 'text/markdown; charset=utf-8';

  procedure validate_table_metadata(
    p_metadata_json in clob
  )
  is
    l_object      json_object_t;
    l_keys        json_key_list;
    l_header_rows json_array_t;
    l_sheet_name  varchar2(4000);
    l_range       varchar2(4000);
    l_row         number;
    l_seen        varchar2(32767) := ':';
  begin
    if p_metadata_json is null
       or dbms_lob.getlength(p_metadata_json) > c_max_metadata_size
    then
      raise_application_error(-20510, 'TABLE artefact metadata is required and bounded to 16 KiB.');
    end if;
    l_object := json_object_t.parse(p_metadata_json);
    l_keys := l_object.get_keys;
    for l_index in 1 .. l_keys.count
    loop
      if l_keys(l_index) not in (
           'schema_version', 'sheet_name', 'table_name',
           'source_cell_range', 'header_rows', 'hidden_sheet'
         )
      then
        raise_application_error(-20511, 'TABLE artefact metadata contains unsupported fields.');
      end if;
    end loop;
    l_sheet_name := l_object.get_string('sheet_name');
    l_range := l_object.get_string('source_cell_range');
    if l_object.get_number('schema_version') <> 1
       or l_sheet_name is null
       or length(l_sheet_name) > 255
       or l_range is null
       or lengthb(l_range) > 100
       or not regexp_like(l_range, '^[A-Z]+[1-9][0-9]*:[A-Z]+[1-9][0-9]*$')
       or not l_object.has('hidden_sheet')
       or not l_object.get('hidden_sheet').is_boolean
    then
      raise_application_error(-20512, 'TABLE artefact metadata is invalid.');
    end if;
    if l_object.has('table_name')
       and not l_object.get('table_name').is_null
       and length(l_object.get_string('table_name')) > 255
    then
      raise_application_error(-20512, 'TABLE artefact metadata is invalid.');
    end if;
    l_header_rows := l_object.get_array('header_rows');
    if l_header_rows is null or l_header_rows.get_size > 32
    then
      raise_application_error(-20512, 'TABLE artefact metadata is invalid.');
    end if;
    if l_header_rows.get_size > 0
    then
      for l_index in 0 .. l_header_rows.get_size - 1
      loop
        l_row := l_header_rows.get_number(l_index);
        if l_row is null or l_row <= 0 or instr(l_seen, ':' || to_char(l_row) || ':') > 0
        then
          raise_application_error(-20512, 'TABLE artefact header rows are invalid.');
        end if;
        l_seen := l_seen || to_char(l_row) || ':';
      end loop;
    end if;
  exception
    when others then
      if sqlcode between -20512 and -20510
      then
        raise;
      end if;
      raise_application_error(-20512, 'TABLE artefact metadata is invalid.');
  end validate_table_metadata;

  procedure assert_complete_set(
    p_extraction_id in number
  )
  is
    l_member_count  number;
    l_primary_count number;
    l_min_ordinal   number;
    l_max_ordinal   number;
    l_text_sha256   varchar2(64);
    l_primary_hash  varchar2(64);
    l_set_kind      varchar2(20);
    l_table_count   number;
  begin
    select count(*),
           sum(case when artefact_role_code in ('PRIMARY', 'MANIFEST') then 1 else 0 end),
           min(member_ordinal),
           max(member_ordinal),
           min(case when artefact_role_code in ('PRIMARY', 'MANIFEST') then content_sha256 end),
           min(case when artefact_role_code = 'PRIMARY' then 'SINGLE' else 'SPREADSHEET' end),
           sum(case when artefact_role_code = 'TABLE' then 1 else 0 end)
      into l_member_count,
           l_primary_count,
           l_min_ordinal,
           l_max_ordinal,
           l_primary_hash,
           l_set_kind,
           l_table_count
      from orac_api.knowledge_artefacts_v
     where extraction_id = p_extraction_id;

    select text_sha256
      into l_text_sha256
      from orac_api.knowledge_extractions_v
     where extraction_id = p_extraction_id;

    if l_member_count = 0
       or l_primary_count <> 1
       or l_min_ordinal <> 1
       or l_max_ordinal <> l_member_count
       or l_primary_hash <> l_text_sha256
       or (l_set_kind = 'SINGLE' and l_table_count <> 0)
       or (l_set_kind = 'SPREADSHEET' and l_table_count = 0)
    then
      raise_application_error(-20513, 'Knowledge artefact output set is incomplete or inconsistent.');
    end if;
  exception
    when no_data_found then
      raise_application_error(-20514, 'Knowledge extraction does not exist.');
  end assert_complete_set;

  function output_set_json(
    p_extraction_id in number
  ) return clob
  is
    l_result clob;
  begin
    assert_complete_set(p_extraction_id);
    select json_object(
             'schema_version' value 1,
             'set_kind' value case
               when max(case when artefact_role_code = 'MANIFEST' then 1 else 0 end) = 1
               then 'SPREADSHEET'
               else 'SINGLE'
             end,
             'members' value json_arrayagg(
               json_object(
                 'artefact_id' value artefact_id,
                 'role' value artefact_role_code,
                 'media_type' value media_type,
                 'content_sha256' value content_sha256,
                 'storage_key' value storage_key,
                 'byte_size' value byte_size,
                 'logical_name' value logical_name,
                 'ordinal' value member_ordinal,
                 'metadata' value metadata_json format json
                 returning clob
               ) order by member_ordinal
               returning clob
             ) format json
             returning clob
           )
      into l_result
      from orac_api.knowledge_artefacts_v
     where extraction_id = p_extraction_id;
    return l_result;
  end output_set_json;

  function register_output_set(
    p_extraction_id   in number,
    p_output_set_json in clob
  ) return clob
  is
    l_root               json_object_t;
    l_members            json_array_t;
    l_set_kind           varchar2(20);
    l_existing_count     number;
    l_existing_match     number;
    l_expected_text_hash varchar2(64);
    l_expected_byte_size number;
    l_registered_text_hash varchar2(64);
    l_extracted_text     clob;
    l_result             clob;
    l_row                orac_api.knowledge_artefacts_v%rowtype;
    type seen_member_type is table of boolean index by varchar2(4000);
    l_seen_ordinals      seen_member_type;
    l_seen_names         seen_member_type;
  begin
    savepoint knowledge_artefact_set_registration;
    if p_output_set_json is null
       or dbms_lob.getlength(p_output_set_json) > c_max_envelope_size
    then
      raise_application_error(-20515, 'Output-set JSON is required and bounded to 1 MiB.');
    end if;
    l_root := json_object_t.parse(p_output_set_json);
    if l_root.get_number('schema_version') <> 1
    then
      raise_application_error(-20516, 'Unsupported output-set schema version.');
    end if;
    l_set_kind := l_root.get_string('set_kind');
    if l_set_kind not in ('SINGLE', 'SPREADSHEET')
    then
      raise_application_error(-20517, 'Output-set kind must be SINGLE or SPREADSHEET.');
    end if;
    l_members := l_root.get_array('members');
    if l_members is null or l_members.get_size not between 1 and c_max_members
    then
      raise_application_error(-20518, 'Output set must contain between 1 and 256 members.');
    end if;

    select text_sha256, extracted_text
      into l_registered_text_hash, l_extracted_text
      from orac_api.knowledge_extractions_v
     where extraction_id = p_extraction_id
       for update;
    orac_code.knowledge_text_identity_api.calculate_canonical_markdown(
      p_text      => l_extracted_text,
      p_sha256    => l_expected_text_hash,
      p_byte_size => l_expected_byte_size
    );
    if l_registered_text_hash <> l_expected_text_hash
    then
      raise_application_error(-20520, 'Extraction text identity is inconsistent.');
    end if;

    select count(*)
      into l_existing_count
      from orac_api.knowledge_artefacts_v
     where extraction_id = p_extraction_id;

    for member in (
      select role_code,
             media_type,
             content_sha256,
             storage_key,
             byte_size,
             logical_name,
             member_ordinal,
             metadata_json
        from json_table(
               p_output_set_json,
               '$.members[*]' columns (
                 role_code varchar2(50) path '$.role',
                 media_type varchar2(255) path '$.media_type',
                 content_sha256 varchar2(64) path '$.content_sha256',
                 storage_key varchar2(71) path '$.storage_key',
                 byte_size number path '$.byte_size',
                 logical_name varchar2(200) path '$.logical_name',
                 member_ordinal number path '$.ordinal',
                 metadata_json clob format json path '$.metadata'
               )
             )
       order by member_ordinal
    )
    loop
      if member.member_ordinal is null
         or member.member_ordinal < 1
         or member.member_ordinal > l_members.get_size
         or member.role_code not in ('PRIMARY', 'MANIFEST', 'TABLE', 'METADATA')
         or not regexp_like(member.content_sha256, '^[0-9a-f]{64}$')
         or member.storage_key <> 'sha256:' || member.content_sha256
         or member.byte_size < 0
         or not regexp_like(member.logical_name, '^[a-z0-9][a-z0-9._-]{0,199}$')
      then
        raise_application_error(-20519, 'Output-set member descriptor is invalid.');
      end if;
      if l_seen_ordinals.exists(to_char(member.member_ordinal))
         or l_seen_names.exists(member.logical_name)
      then
        raise_application_error(-20519, 'Output-set member identity is duplicated.');
      end if;
      l_seen_ordinals(to_char(member.member_ordinal)) := true;
      l_seen_names(member.logical_name) := true;
      if member.role_code in ('PRIMARY', 'MANIFEST')
      then
        if member.media_type <> c_markdown_media
           or member.content_sha256 <> l_expected_text_hash
           or member.byte_size <> l_expected_byte_size
           or (l_set_kind = 'SINGLE' and member.role_code <> 'PRIMARY')
           or (l_set_kind = 'SPREADSHEET' and member.role_code <> 'MANIFEST')
        then
          raise_application_error(-20520, 'Primary output member is inconsistent with the extraction.');
        end if;
      elsif member.role_code = 'TABLE'
      then
        if l_set_kind <> 'SPREADSHEET' or member.media_type <> 'text/csv; charset=utf-8'
        then
          raise_application_error(-20521, 'TABLE members require a spreadsheet CSV output set.');
        end if;
        validate_table_metadata(member.metadata_json);
      elsif member.role_code = 'METADATA' and member.media_type <> 'application/json'
      then
        raise_application_error(-20522, 'METADATA members require application/json.');
      end if;

      if l_existing_count = 0
      then
        l_row.extraction_id := p_extraction_id;
        l_row.artefact_role_code := member.role_code;
        l_row.media_type := member.media_type;
        l_row.content_sha256 := member.content_sha256;
        l_row.storage_key := member.storage_key;
        l_row.byte_size := member.byte_size;
        l_row.logical_name := member.logical_name;
        l_row.member_ordinal := member.member_ordinal;
        if member.metadata_json is null
        then
          l_row.metadata_json := null;
        else
          select json(member.metadata_json)
            into l_row.metadata_json;
        end if;
        orac_api.knowledge_artefacts_tapi.ins(l_row);
      else
        select count(*)
          into l_existing_match
          from orac_api.knowledge_artefacts_v art
         where art.extraction_id = p_extraction_id
           and art.artefact_role_code = member.role_code
           and art.media_type = member.media_type
           and art.content_sha256 = member.content_sha256
           and art.storage_key = member.storage_key
           and art.byte_size = member.byte_size
           and art.logical_name = member.logical_name
           and art.member_ordinal = member.member_ordinal
           and coalesce(json_serialize(art.metadata_json returning varchar2), '~') =
               coalesce(json_serialize(json(member.metadata_json) returning varchar2), '~');
        if l_existing_match <> 1
        then
          raise_application_error(-20523, 'Idempotency conflict: output-set member differs.');
        end if;
      end if;
    end loop;

    if l_existing_count not in (0, l_members.get_size)
    then
      raise_application_error(-20523, 'Idempotency conflict: output-set member count differs.');
    end if;
    assert_complete_set(p_extraction_id);
    l_result := output_set_json(p_extraction_id);
    return l_result;
  exception
    when no_data_found then
      rollback to knowledge_artefact_set_registration;
      raise_application_error(-20514, 'Knowledge extraction does not exist.');
    when others then
      rollback to knowledge_artefact_set_registration;
      if sqlcode between -20523 and -20510
      then
        raise;
      end if;
      raise_application_error(-20524, 'Output-set JSON is malformed or inconsistent.');
  end register_output_set;
end knowledge_artefact_api;
/
--rollback drop package body orac_code.knowledge_artefact_api;
