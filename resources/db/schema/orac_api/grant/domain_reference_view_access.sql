--liquibase formatted sql

--changeset clive:grant_read_domain_codes_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: allow the business layer to read reference-data domains

grant read on orac_api.domain_codes_v to orac_code with grant option;

--rollback revoke read on orac_api.domain_codes_v from orac_code;

--changeset clive:grant_read_domain_ref_values_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: allow the business layer to read reference-domain values

grant read on orac_api.domain_ref_values_v to orac_code with grant option;

--rollback revoke read on orac_api.domain_ref_values_v from orac_code;
