--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Recompiles retrieval PL/SQL after dependent business views exist.

--changeset clive:recompile_orac_code_knowledge_retrieval_api context:core labels:core stripComments:false runOnChange:true
alter package orac_code.knowledge_retrieval_api compile specification;
alter package orac_code.knowledge_retrieval_api compile body;
--rollback alter package orac_code.knowledge_retrieval_api compile body;

--changeset clive:recompile_orac_code_knowledge_retrieval_api_p1_07 context:core labels:core stripComments:false
alter package orac_code.knowledge_retrieval_api compile specification;
alter package orac_code.knowledge_retrieval_api compile body;
--rollback alter package orac_code.knowledge_retrieval_api compile body;
