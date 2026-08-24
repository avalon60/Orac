--liquibase formatted sql

--changeset clive:comment_orac_core_domain_codes context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.domain_codes is
  'Defines Core-owned reference-data domains whose active values may be exposed through approved APIs and LOVs.';

comment on column orac_core.domain_codes.domain_code is
  'Stable uppercase identifier and primary key for the reference-data domain.';

comment on column orac_core.domain_codes.display_name is
  'Human-readable name used for administration of the domain.';

comment on column orac_core.domain_codes.description is
  'Optional explanation of the domain purpose and intended values.';

comment on column orac_core.domain_codes.active_yn is
  'Y when values from the domain may be offered for new selections.';

comment on column orac_core.domain_codes.system_required_yn is
  'Y when the domain is supplied by the hosting application and cannot be deleted.';

comment on column orac_core.domain_codes.created_by is
  'User or process that created the domain.';

comment on column orac_core.domain_codes.created_on is
  'Timestamp when the domain was created.';

comment on column orac_core.domain_codes.updated_by is
  'User or process that last updated the domain.';

comment on column orac_core.domain_codes.updated_on is
  'Timestamp when the domain was last updated.';

comment on column orac_core.domain_codes.row_version is
  'Optimistic-lock version incremented whenever the domain is updated.';

--rollback comment on column orac_core.domain_codes.row_version is null;
--rollback comment on column orac_core.domain_codes.updated_on is null;
--rollback comment on column orac_core.domain_codes.updated_by is null;
--rollback comment on column orac_core.domain_codes.created_on is null;
--rollback comment on column orac_core.domain_codes.created_by is null;
--rollback comment on column orac_core.domain_codes.system_required_yn is null;
--rollback comment on column orac_core.domain_codes.active_yn is null;
--rollback comment on column orac_core.domain_codes.description is null;
--rollback comment on column orac_core.domain_codes.display_name is null;
--rollback comment on column orac_core.domain_codes.domain_code is null;
--rollback comment on table orac_core.domain_codes is null;
