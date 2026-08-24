--liquibase formatted sql

--changeset clive:compile_view_orac_code_doc_class_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'DOC_CLASS_LOV_V';
alter view orac_code.doc_class_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_knowledge_tag_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'KNOWLEDGE_TAG_LOV_V';
alter view orac_code.knowledge_tag_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_timezone_group_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'TIMEZONE_GROUP_LOV_V';
alter view orac_code.timezone_group_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_timezone_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'TIMEZONE_LOV_V';
alter view orac_code.timezone_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_pref_value_type_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'PREF_VALUE_TYPE_LOV_V';
alter view orac_code.pref_value_type_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_pref_control_type_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'PREF_CONTROL_TYPE_LOV_V';
alter view orac_code.pref_control_type_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_pref_lov_type_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'PREF_LOV_TYPE_LOV_V';
alter view orac_code.pref_lov_type_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_llm_context_policy_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'LLM_CONTEXT_POLICY_LOV_V';
alter view orac_code.llm_context_policy_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_user_alias_type_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'USER_ALIAS_TYPE_LOV_V';
alter view orac_code.user_alias_type_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_vector_distance_metric_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'VECTOR_DISTANCE_METRIC_LOV_V';
alter view orac_code.vector_distance_metric_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_adapter_support_status_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'ADAPTER_SUPPORT_STATUS_LOV_V';
alter view orac_code.adapter_support_status_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_bound_operator_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'BOUND_OPERATOR_LOV_V';
alter view orac_code.bound_operator_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_capability_class_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'CAPABILITY_CLASS_LOV_V';
alter view orac_code.capability_class_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_capability_evidence_state_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'CAPABILITY_EVIDENCE_STATE_LOV_V';
alter view orac_code.capability_evidence_state_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_capability_lifecycle_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'CAPABILITY_LIFECYCLE_LOV_V';
alter view orac_code.capability_lifecycle_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_limit_dimension_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'LIMIT_DIMENSION_LOV_V';
alter view orac_code.limit_dimension_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_limit_unit_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'LIMIT_UNIT_LOV_V';
alter view orac_code.limit_unit_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_mime_match_kind_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'MIME_MATCH_KIND_LOV_V';
alter view orac_code.mime_match_kind_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_processing_locality_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'PROCESSING_LOCALITY_LOV_V';
alter view orac_code.processing_locality_lov_v compile;

--rollback select 1 from dual;

--changeset clive:compile_view_orac_code_provider_metadata_status_lov_v context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'PROVIDER_METADATA_STATUS_LOV_V';
alter view orac_code.provider_metadata_status_lov_v compile;

--rollback select 1 from dual;
