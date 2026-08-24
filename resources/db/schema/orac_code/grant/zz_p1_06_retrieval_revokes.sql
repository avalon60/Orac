--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Removes retrieval and ingestion grants superseded by P1-06.

--changeset clive:revoke_orac_knowledge_searchable_chunks_v_p1_06 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_CODE' and table_name = 'KNOWLEDGE_SEARCHABLE_CHUNKS_V' and grantee = 'ORAC' and privilege in ('READ', 'SELECT');
revoke read on orac_code.knowledge_searchable_chunks_v from orac;
--rollback grant read on orac_code.knowledge_searchable_chunks_v to orac;

--changeset clive:revoke_orac_knowledge_artefact_api_p1_06 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_CODE' and table_name = 'KNOWLEDGE_ARTEFACT_API' and grantee = 'ORAC' and privilege = 'EXECUTE';
revoke execute on orac_code.knowledge_artefact_api from orac;
--rollback grant execute on orac_code.knowledge_artefact_api to orac;

--changeset clive:revoke_orac_plugin_knowledge_ingestion_api_p1_06 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_CODE' and table_name = 'KNOWLEDGE_INGESTION_API' and grantee = 'ORAC_PLUGIN' and privilege = 'EXECUTE';
revoke execute on orac_code.knowledge_ingestion_api from orac_plugin;
--rollback grant execute on orac_code.knowledge_ingestion_api to orac_plugin;
