--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_grant_chess_admin_api context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant execute on orac_chess.chess_admin_api to orac_apx_pub;
--rollback revoke execute on orac_chess.chess_admin_api from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_game_api context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant execute on orac_chess.chess_game_api to orac_apx_pub;
--rollback revoke execute on orac_chess.chess_game_api from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_variation_api context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant execute on orac_chess.chess_variation_api to orac_apx_pub;
--rollback revoke execute on orac_chess.chess_variation_api from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_image_api context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant execute on orac_chess.chess_image_api to orac_apx_pub;
--rollback revoke execute on orac_chess.chess_image_api from orac_apx_pub;
