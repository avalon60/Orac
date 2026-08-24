--liquibase formatted sql

--changeset clive:grant_read_doc_class_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: expose semantic document classifications to the APEX access schema

grant read on orac_code.doc_class_v to orac_apx_pub;

--rollback revoke read on orac_code.doc_class_v from orac_apx_pub;

--changeset clive:grant_read_doc_class_lov_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: expose active document classifications to APEX selectors

grant read on orac_code.doc_class_lov_v to orac_apx_pub;

--rollback revoke read on orac_code.doc_class_lov_v from orac_apx_pub;
