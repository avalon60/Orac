--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Maintains Chess content source reference data.
-- Purpose: Provide creator identities without changing existing video identities.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_grant context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_content_source_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_content_source_v from orac_apx_pub;
