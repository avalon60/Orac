--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_api_view_relational_query_catalogue_v context:core labels:core,relational_query stripComments:false runOnChange:true
create or replace view orac_api.relational_query_catalogue_v as
select dataset_id, plugin_id, metadata_version, manifest_hash, declaration_json, verified_yn, evidence_json, verified_on
from orac_core.relational_query_catalogue;
--rollback drop view orac_api.relational_query_catalogue_v;
