--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_api_privilege_relational_query_catalogue_core context:core labels:core,relational_query stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.relational_query_catalogue to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.relational_query_catalogue from orac_api;
