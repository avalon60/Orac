--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Grants CODE the controlled native knowledge embedding views.

--changeset clive:grant_orac_api_kn_embprf_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_embedding_profiles_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_embedding_profiles_v from orac_code;

--changeset clive:grant_orac_api_kn_embact_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_embedding_activations_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_embedding_activations_v from orac_code;

--changeset clive:grant_orac_api_kn_reembr_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_reembedding_runs_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_reembedding_runs_v from orac_code;

--changeset clive:grant_orac_api_kn_chnkve_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_chunk_vector_embeddings_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_chunk_vector_embeddings_v from orac_code;
