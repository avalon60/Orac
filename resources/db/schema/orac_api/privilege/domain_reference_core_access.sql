--liquibase formatted sql

--changeset clive:grant_orac_core_domain_codes_to_orac_api context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: allow the API layer to project reference-data domains

grant select on orac_core.domain_codes to orac_api with grant option;

--rollback revoke select on orac_core.domain_codes from orac_api;

--changeset clive:grant_orac_core_domain_ref_values_to_orac_api context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: allow the API layer to project reference-domain values

grant select on orac_core.domain_ref_values to orac_api with grant option;

--rollback revoke select on orac_core.domain_ref_values from orac_api;
