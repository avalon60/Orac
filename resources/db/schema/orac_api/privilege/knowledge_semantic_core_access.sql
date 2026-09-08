--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Allows ORAC_API to expose native knowledge embedding tables.

--changeset clive:grant_orac_core_kn_embprf_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_embedding_profiles to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_embedding_profiles from orac_api;

--changeset clive:grant_orac_core_kn_embact_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_embedding_activations to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_embedding_activations from orac_api;

--changeset clive:grant_orac_core_kn_reembr_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_reembedding_runs to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_reembedding_runs from orac_api;

--changeset clive:grant_orac_core_kn_chnkve_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_chunk_vector_embeddings to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_chunk_vector_embeddings from orac_api;
