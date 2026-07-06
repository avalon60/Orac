--liquibase formatted sql

--changeset cbostock:home_assistant_package_body_ha_sync_api context:plugin,prod labels:plugin,home_assistant stripComments:false runOnChange:true
create or replace package body orac_ha.ha_sync_api as

  function safe_ts(
    p_value in varchar2
  ) return timestamp with time zone
  is
  begin
    if p_value is null
    then
      return null;
    end if;

    return to_timestamp_tz(
      replace(p_value, 'Z', '+00:00'),
      'yyyy-mm-dd"T"hh24:mi:ss.ff tzh:tzm'
    );
  exception
    when others then
      return null;
  end safe_ts;

  procedure reset_shadow_tables(
    p_sync_type in orac_ha.ha_sync_runs.sync_type%type
  )
  is
  begin
    if p_sync_type = 'structural'
    then
      delete from orac_ha.ha_states_current;
      delete from orac_ha.ha_entities;
      delete from orac_ha.ha_devices;
      delete from orac_ha.ha_areas;
    elsif p_sync_type = 'state'
    then
      delete from orac_ha.ha_states_current;
    else
      raise_application_error(
        -20001,
        'Unsupported Home Assistant sync type: ' || p_sync_type
      );
    end if;
  end reset_shadow_tables;

  procedure begin_sync_run(
    p_sync_run_id in orac_ha.ha_sync_runs.sync_run_id%type,
    p_sync_type   in orac_ha.ha_sync_runs.sync_type%type
  )
  is
  begin
    reset_shadow_tables(p_sync_type => p_sync_type);

    insert into orac_ha.ha_sync_runs
    (
      sync_run_id,
      sync_type,
      status,
      rows_processed,
      started_on
    )
    values
    (
      p_sync_run_id,
      p_sync_type,
      'running',
      0,
      systimestamp
    );
  end begin_sync_run;

  procedure complete_sync_run(
    p_sync_run_id    in orac_ha.ha_sync_runs.sync_run_id%type,
    p_rows_processed in orac_ha.ha_sync_runs.rows_processed%type,
    p_message        in orac_ha.ha_sync_runs.message%type default null
  )
  is
  begin
    update orac_ha.ha_sync_runs
       set status         = 'complete',
           rows_processed = nvl(p_rows_processed, 0),
           message        = substr(p_message, 1, 4000),
           completed_on   = systimestamp
     where sync_run_id    = p_sync_run_id;

    if sql%rowcount = 0
    then
      raise_application_error(-20002, 'Unknown Home Assistant sync run.');
    end if;
  end complete_sync_run;

  procedure fail_sync_run(
    p_sync_run_id   in orac_ha.ha_sync_runs.sync_run_id%type,
    p_error_message in orac_ha.ha_sync_runs.error_message%type
  )
  is
  begin
    update orac_ha.ha_sync_runs
       set status        = 'failed',
           error_message = substr(p_error_message, 1, 4000),
           completed_on  = systimestamp
     where sync_run_id   = p_sync_run_id;

    if sql%rowcount = 0
    then
      raise_application_error(-20003, 'Unknown Home Assistant sync run.');
    end if;
  end fail_sync_run;

  procedure merge_area(
    p_payload in clob
  )
  is
  begin
    merge into orac_ha.ha_areas dst
    using (
      select substr(json_value(p_payload, '$.area_id'), 1, 64) area_id,
             substr(json_value(p_payload, '$.name'), 1, 255) name,
             substr(json_value(p_payload, '$.floor_id'), 1, 64) floor_id,
             substr(json_value(p_payload, '$.icon'), 1, 255) icon,
             substr(json_value(p_payload, '$.picture'), 1, 255) picture,
             substr(json_value(p_payload, '$.humidity_entity_id'), 1, 255) humidity_entity_id,
             substr(json_value(p_payload, '$.temperature_entity_id'), 1, 255) temperature_entity_id,
             json_query(p_payload, '$.aliases' returning clob null on error) aliases,
             json_query(p_payload, '$.labels' returning clob null on error) labels,
             orac_ha.ha_sync_api.safe_ts(json_value(p_payload, '$.created_at')) ha_created_at,
             orac_ha.ha_sync_api.safe_ts(json_value(p_payload, '$.modified_at')) ha_modified_at
        from dual
    ) src
       on (dst.area_id = src.area_id)
    when matched then update
       set dst.name                  = src.name,
           dst.floor_id              = src.floor_id,
           dst.icon                  = src.icon,
           dst.picture               = src.picture,
           dst.humidity_entity_id    = src.humidity_entity_id,
           dst.temperature_entity_id = src.temperature_entity_id,
           dst.aliases               = src.aliases,
           dst.labels                = src.labels,
           dst.ha_created_at         = src.ha_created_at,
           dst.ha_modified_at        = src.ha_modified_at
    when not matched then insert
    (
      area_id,
      name,
      floor_id,
      icon,
      picture,
      humidity_entity_id,
      temperature_entity_id,
      aliases,
      labels,
      ha_created_at,
      ha_modified_at
    )
    values
    (
      src.area_id,
      src.name,
      src.floor_id,
      src.icon,
      src.picture,
      src.humidity_entity_id,
      src.temperature_entity_id,
      src.aliases,
      src.labels,
      src.ha_created_at,
      src.ha_modified_at
    );
  end merge_area;

  procedure merge_device(
    p_payload in clob
  )
  is
  begin
    merge into orac_ha.ha_devices dst
    using (
      select substr(json_value(p_payload, '$.id'), 1, 64) device_id,
             substr(json_value(p_payload, '$.name'), 1, 255) name,
             substr(json_value(p_payload, '$.name_by_user'), 1, 255) name_by_user,
             substr(json_value(p_payload, '$.manufacturer'), 1, 255) manufacturer,
             substr(json_value(p_payload, '$.model'), 1, 255) model,
             substr(json_value(p_payload, '$.model_id'), 1, 255) model_id,
             substr(json_value(p_payload, '$.area_id'), 1, 64) area_id,
             substr(json_value(p_payload, '$.via_device_id'), 1, 64) via_device_id,
             substr(json_value(p_payload, '$.hw_version'), 1, 255) hw_version,
             substr(json_value(p_payload, '$.sw_version'), 1, 255) sw_version,
             substr(json_value(p_payload, '$.serial_number'), 1, 255) serial_number,
             substr(json_value(p_payload, '$.entry_type'), 1, 64) entry_type,
             substr(json_value(p_payload, '$.disabled_by'), 1, 64) disabled_by,
             substr(json_value(p_payload, '$.primary_config_entry'), 1, 64) primary_config_entry,
             substr(json_value(p_payload, '$.configuration_url'), 1, 1024) configuration_url,
             json_query(p_payload, '$.connections' returning clob null on error) connections,
             json_query(p_payload, '$.identifiers' returning clob null on error) identifiers,
             json_query(p_payload, '$.config_entries' returning clob null on error) config_entries,
             json_query(p_payload, '$.config_entries_subentries' returning clob null on error) config_entries_subentries,
             json_query(p_payload, '$.labels' returning clob null on error) labels,
             orac_ha.ha_sync_api.safe_ts(json_value(p_payload, '$.created_at')) ha_created_at,
             orac_ha.ha_sync_api.safe_ts(json_value(p_payload, '$.modified_at')) ha_modified_at
        from dual
    ) src
       on (dst.device_id = src.device_id)
    when matched then update
       set dst.name                       = src.name,
           dst.name_by_user               = src.name_by_user,
           dst.manufacturer               = src.manufacturer,
           dst.model                      = src.model,
           dst.model_id                   = src.model_id,
           dst.area_id                    = src.area_id,
           dst.via_device_id              = src.via_device_id,
           dst.hw_version                 = src.hw_version,
           dst.sw_version                 = src.sw_version,
           dst.serial_number              = src.serial_number,
           dst.entry_type                 = src.entry_type,
           dst.disabled_by                = src.disabled_by,
           dst.primary_config_entry       = src.primary_config_entry,
           dst.configuration_url          = src.configuration_url,
           dst.connections                = src.connections,
           dst.identifiers                = src.identifiers,
           dst.config_entries             = src.config_entries,
           dst.config_entries_subentries  = src.config_entries_subentries,
           dst.labels                     = src.labels,
           dst.ha_created_at             = src.ha_created_at,
           dst.ha_modified_at            = src.ha_modified_at
    when not matched then insert
    (
      device_id,
      name,
      name_by_user,
      manufacturer,
      model,
      model_id,
      area_id,
      via_device_id,
      hw_version,
      sw_version,
      serial_number,
      entry_type,
      disabled_by,
      primary_config_entry,
      configuration_url,
      connections,
      identifiers,
      config_entries,
      config_entries_subentries,
      labels,
      ha_created_at,
      ha_modified_at
    )
    values
    (
      src.device_id,
      src.name,
      src.name_by_user,
      src.manufacturer,
      src.model,
      src.model_id,
      src.area_id,
      src.via_device_id,
      src.hw_version,
      src.sw_version,
      src.serial_number,
      src.entry_type,
      src.disabled_by,
      src.primary_config_entry,
      src.configuration_url,
      src.connections,
      src.identifiers,
      src.config_entries,
      src.config_entries_subentries,
      src.labels,
      src.ha_created_at,
      src.ha_modified_at
    );
  end merge_device;

  procedure merge_entity(
    p_payload in clob
  )
  is
  begin
    merge into orac_ha.ha_entities dst
    using (
      select substr(json_value(p_payload, '$.entity_id'), 1, 255) entity_id,
             substr(coalesce(json_value(p_payload, '$.id'), json_value(p_payload, '$.entity_id')), 1, 64) ha_entity_id,
             substr(json_value(p_payload, '$.unique_id'), 1, 255) unique_id,
             substr(json_value(p_payload, '$.platform'), 1, 64) platform,
             substr(json_value(p_payload, '$.device_id'), 1, 64) device_id,
             substr(json_value(p_payload, '$.area_id'), 1, 64) area_id,
             substr(json_value(p_payload, '$.config_entry_id'), 1, 64) config_entry_id,
             substr(json_value(p_payload, '$.config_subentry_id'), 1, 64) config_subentry_id,
             substr(json_value(p_payload, '$.entity_category'), 1, 32) entity_category,
             substr(json_value(p_payload, '$.disabled_by'), 1, 32) disabled_by,
             substr(json_value(p_payload, '$.hidden_by'), 1, 32) hidden_by,
             case json_value(p_payload, '$.has_entity_name')
               when 'true' then 'Y'
               when 'false' then 'N'
             end has_entity_name,
             substr(json_value(p_payload, '$.name'), 1, 255) name,
             substr(json_value(p_payload, '$.original_name'), 1, 255) original_name,
             substr(json_value(p_payload, '$.translation_key'), 1, 255) translation_key,
             substr(json_value(p_payload, '$.icon'), 1, 255) icon,
             orac_ha.ha_sync_api.safe_ts(json_value(p_payload, '$.created_at')) ha_created_at,
             orac_ha.ha_sync_api.safe_ts(json_value(p_payload, '$.modified_at')) ha_modified_at,
             json_query(p_payload, '$.options' returning clob null on error) options,
             json_query(p_payload, '$.categories' returning clob null on error) categories,
             json_query(p_payload, '$.labels' returning clob null on error) labels
        from dual
    ) src
       on (dst.entity_id = src.entity_id)
    when matched then update
       set dst.ha_entity_id       = src.ha_entity_id,
           dst.unique_id          = src.unique_id,
           dst.platform           = src.platform,
           dst.device_id          = src.device_id,
           dst.area_id            = src.area_id,
           dst.config_entry_id    = src.config_entry_id,
           dst.config_subentry_id = src.config_subentry_id,
           dst.entity_category    = src.entity_category,
           dst.disabled_by        = src.disabled_by,
           dst.hidden_by          = src.hidden_by,
           dst.has_entity_name    = src.has_entity_name,
           dst.name               = src.name,
           dst.original_name      = src.original_name,
           dst.translation_key    = src.translation_key,
           dst.icon               = src.icon,
           dst.ha_created_at      = src.ha_created_at,
           dst.ha_modified_at     = src.ha_modified_at,
           dst.options            = src.options,
           dst.categories         = src.categories,
           dst.labels             = src.labels
    when not matched then insert
    (
      entity_id,
      ha_entity_id,
      unique_id,
      platform,
      device_id,
      area_id,
      config_entry_id,
      config_subentry_id,
      entity_category,
      disabled_by,
      hidden_by,
      has_entity_name,
      name,
      original_name,
      translation_key,
      icon,
      ha_created_at,
      ha_modified_at,
      options,
      categories,
      labels
    )
    values
    (
      src.entity_id,
      src.ha_entity_id,
      src.unique_id,
      src.platform,
      src.device_id,
      src.area_id,
      src.config_entry_id,
      src.config_subentry_id,
      src.entity_category,
      src.disabled_by,
      src.hidden_by,
      src.has_entity_name,
      src.name,
      src.original_name,
      src.translation_key,
      src.icon,
      src.ha_created_at,
      src.ha_modified_at,
      src.options,
      src.categories,
      src.labels
    );
  end merge_entity;

  procedure merge_state(
    p_payload in clob
  )
  is
  begin
    merge into orac_ha.ha_entities dst
    using (
      select substr(json_value(p_payload, '$.entity_id'), 1, 255) entity_id,
             substr(json_value(p_payload, '$.entity_id'), 1, 64) ha_entity_id,
             substr(
               regexp_substr(json_value(p_payload, '$.entity_id'), '^[^.]+'),
               1,
               64
             ) platform,
             substr(json_value(p_payload, '$.attributes.friendly_name'), 1, 255) name
        from dual
    ) src
       on (dst.entity_id = src.entity_id)
    when not matched then insert
    (
      entity_id,
      ha_entity_id,
      platform,
      name
    )
    values
    (
      src.entity_id,
      src.ha_entity_id,
      src.platform,
      src.name
    );

    merge into orac_ha.ha_states_current dst
    using (
      select substr(json_value(p_payload, '$.entity_id'), 1, 255) entity_id,
             substr(json_value(p_payload, '$.state'), 1, 255) state,
             json_query(p_payload, '$.attributes' returning clob null on error) attributes,
             orac_ha.ha_sync_api.safe_ts(json_value(p_payload, '$.last_changed')) last_changed,
             orac_ha.ha_sync_api.safe_ts(json_value(p_payload, '$.last_updated')) last_updated,
             orac_ha.ha_sync_api.safe_ts(json_value(p_payload, '$.last_reported')) last_reported,
             substr(json_value(p_payload, '$.context.id'), 1, 64) context_id,
             substr(json_value(p_payload, '$.context.parent_id'), 1, 64) context_parent_id,
             substr(json_value(p_payload, '$.context.user_id'), 1, 64) context_user_id
        from dual
    ) src
       on (dst.entity_id = src.entity_id)
    when matched then update
       set dst.state             = src.state,
           dst.attributes        = src.attributes,
           dst.last_changed      = src.last_changed,
           dst.last_updated      = src.last_updated,
           dst.last_reported     = src.last_reported,
           dst.context_id        = src.context_id,
           dst.context_parent_id = src.context_parent_id,
           dst.context_user_id   = src.context_user_id
    when not matched then insert
    (
      entity_id,
      state,
      attributes,
      last_changed,
      last_updated,
      last_reported,
      context_id,
      context_parent_id,
      context_user_id
    )
    values
    (
      src.entity_id,
      src.state,
      src.attributes,
      src.last_changed,
      src.last_updated,
      src.last_reported,
      src.context_id,
      src.context_parent_id,
      src.context_user_id
    );
  end merge_state;

end ha_sync_api;
/
