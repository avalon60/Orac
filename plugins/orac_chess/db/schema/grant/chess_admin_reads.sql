--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_grant_chess_commentary_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_commentary_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_commentary_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_concept_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_concept_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_concept_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_concept_gambit_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_concept_gambit_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_concept_gambit_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_concept_opening_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_concept_opening_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_concept_opening_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_concept_variation_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_concept_variation_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_concept_variation_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_gambit_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_gambit_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_gambit_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_game_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_game_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_game_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_image_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_image_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_image_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_image_gambit_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_image_gambit_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_image_gambit_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_image_opening_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_image_opening_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_image_opening_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_image_variation_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_image_variation_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_image_variation_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_opening_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_opening_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_opening_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_opening_alias_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_opening_alias_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_opening_alias_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_opening_eco_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_opening_eco_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_opening_eco_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_opening_gambit_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_opening_gambit_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_opening_gambit_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_variation_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_variation_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_variation_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_video_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_video_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_video_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_video_gambit_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_video_gambit_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_video_gambit_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_video_opening_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_video_opening_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_video_opening_v from orac_apx_pub;

--changeset clive:orac_chess_admin_grant_chess_video_variation_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_video_variation_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_video_variation_v from orac_apx_pub;
