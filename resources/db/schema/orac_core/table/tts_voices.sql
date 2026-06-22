--liquibase formatted sql

--changeset clive:create_table_orac_core_table_tts_voices context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'TTS_VOICES';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: startup-refreshed runtime catalogue of available TTS voices


create table orac_core.tts_voices
(
  tts_voice_key    varchar2(300 char) not null,
  provider_code    varchar2(30 char) not null,
  provider_voice_id varchar2(240 char) not null,
  display_name     varchar2(240 char) not null,
  language_code    varchar2(20 char),
  locale_code      varchar2(20 char),
  voice_quality    varchar2(40 char),
  model_path       varchar2(1000 char),
  config_path      varchar2(1000 char),
  metadata_json    clob,
  default_yn       varchar2(1 char) default 'N' not null,
  enabled_yn       varchar2(1 char) default 'Y' not null,
  sort_order       number,
  loaded_on        timestamp default systimestamp not null
)
;

--rollback drop table orac_core.tts_voices purge;
