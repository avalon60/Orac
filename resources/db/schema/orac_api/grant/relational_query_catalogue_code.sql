--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_api_grant_relational_query_catalogue_code context:core labels:core,relational_query stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.relational_query_catalogue_v to orac_code;
--rollback revoke select, insert, update, delete on orac_api.relational_query_catalogue_v from orac_code;
