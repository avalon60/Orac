--liquibase formatted sql

--changeset clive:comment_orac_core_knowledge_document_version_tags context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.knowledge_document_version_tags is
  'Records the ordered, controlled classifications assigned to each immutable knowledge document version.';

--changeset clive:comment_orac_core_kn_docvtag_document_version_id context:core labels:core stripComments:false runOnChange:true
comment on column orac_core.knowledge_document_version_tags.document_version_id is
  'Knowledge document version to which the classification is assigned.';

--changeset clive:comment_orac_core_kn_docvtag_doc_class_domain_code context:core labels:core stripComments:false runOnChange:true
comment on column orac_core.knowledge_document_version_tags.doc_class_domain_code is
  'Fixed DOC_CLASS domain discriminator used with the classification reference-value code.';

--changeset clive:comment_orac_core_kn_docvtag_doc_class_ref_value_code context:core labels:core stripComments:false runOnChange:true
comment on column orac_core.knowledge_document_version_tags.doc_class_ref_value_code is
  'Stable DOC_CLASS reference value assigned to the document version.';

--changeset clive:comment_orac_core_kn_docvtag_tag_order context:core labels:core stripComments:false runOnChange:true
comment on column orac_core.knowledge_document_version_tags.tag_order is
  'One-based presentation order of the classification within the document version.';

--changeset clive:comment_orac_core_kn_docvtag_created_by context:core labels:core stripComments:false runOnChange:true
comment on column orac_core.knowledge_document_version_tags.created_by is
  'User or process that assigned the classification.';

--changeset clive:comment_orac_core_kn_docvtag_created_on context:core labels:core stripComments:false runOnChange:true
comment on column orac_core.knowledge_document_version_tags.created_on is
  'Timestamp when the classification was assigned.';
