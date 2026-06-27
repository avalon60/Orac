--liquibase formatted sql
-- Author: clive
-- Date: 26-Jun-2026
-- Description: Adds slider display metadata columns to preference definitions.

--changeset clive:add_slider_metadata_columns_to_preference_definitions context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_CORE' and table_name = 'PREFERENCE_DEFINITIONS' and column_name in ('STEP_NUMBER', 'UNIT_LABEL', 'DISPLAY_MIN_LABEL', 'DISPLAY_MAX_LABEL', 'DISPLAY_VALUE_FORMAT');
alter table orac_core.preference_definitions add
(
  step_number          number,
  unit_label           varchar2(50 byte),
  display_min_label    varchar2(100 byte),
  display_max_label    varchar2(100 byte),
  display_value_format varchar2(100 byte)
)
;

--rollback alter table orac_core.preference_definitions drop (step_number, unit_label, display_min_label, display_max_label, display_value_format);
