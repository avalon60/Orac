--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Documents llm_input_representations.

--changeset clive:comment_orac_core_llm_input_representations context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.llm_input_representations is
  'Controlled source and derivative evidence forms independent of MIME and routing.';

comment on column orac_core.llm_input_representations.representation_code is
  'Representation code.';

comment on column orac_core.llm_input_representations.display_name is
  'Human-readable representation name.';

comment on column orac_core.llm_input_representations.description is
  'Meaning of the controlled source or derivative evidence form.';

comment on column orac_core.llm_input_representations.created_by is
  'Principal that created the row.';

comment on column orac_core.llm_input_representations.created_on is
  'Timestamp when the row was created.';

comment on column orac_core.llm_input_representations.updated_by is
  'Principal that most recently updated the row.';

comment on column orac_core.llm_input_representations.updated_on is
  'Timestamp when the row was most recently updated.';

comment on column orac_core.llm_input_representations.row_version is
  'Optimistic-locking value incremented for each update.';
