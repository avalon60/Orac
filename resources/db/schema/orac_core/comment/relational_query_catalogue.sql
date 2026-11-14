--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_core_comment_relational_query_catalogue context:core labels:core,relational_query stripComments:false runOnChange:true
comment on table orac_core.relational_query_catalogue is 'Core relational query dataset lifecycle and live release evidence; no user permissions';
