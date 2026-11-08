--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_admin_api_spec context:plugin,prod labels:plugin stripComments:false runOnChange:true endDelimiter:/
create or replace package orac_chess.chess_admin_api authid definer as
  -- Insert when p_id is null; otherwise require the observed version. Return the new version.
  procedure save_opening(p_id in out number, p_expected_version in number, p_name in varchar2, p_opening_type in varchar2, p_description in clob, p_parent_opening_id in number, p_new_version out number);
  -- Require the observed version and reject referenced rows; caller owns commit/rollback.
  -- Save opening and complete colon-separated ECO set atomically; caller owns transaction.
  procedure save_opening_with_eco(p_id in out number, p_expected_version in number, p_name in varchar2, p_opening_type in varchar2, p_description in clob, p_parent_opening_id in number, p_eco_codes in varchar2, p_new_version out number);
  procedure delete_opening(p_id number, p_expected_version number);
  -- Insert when p_id is null; otherwise require the observed version. Return the new version.
  procedure save_gambit(p_id in out number, p_expected_version in number, p_name in varchar2, p_description in clob, p_new_version out number);
  -- Require the observed version and reject referenced rows; caller owns commit/rollback.
  procedure delete_gambit(p_id number, p_expected_version number);
  -- Insert when p_id is null; otherwise require the observed version. Return the new version.
  procedure save_concept(p_id in out number, p_expected_version in number, p_concept_code in varchar2, p_name in varchar2, p_category_code in varchar2, p_description in clob, p_new_version out number);
  -- Require the observed version and reject referenced rows; caller owns commit/rollback.
  procedure delete_concept(p_id number, p_expected_version number);
  -- Insert when p_id is null; otherwise require the observed version. Return the new version.
  procedure save_video(p_id in out number, p_expected_version in number, p_platform in varchar2, p_external_video_id in varchar2, p_video_url in varchar2, p_title in varchar2, p_creator in varchar2, p_description in clob, p_duration_seconds in number, p_published_on in date, p_new_version out number);
  -- Require the observed version and reject referenced rows; caller owns commit/rollback.
  procedure delete_video(p_id number, p_expected_version number);
  -- Insert when p_id is null; otherwise require the observed version. Return the new version.
  procedure save_commentary(p_id in out number, p_expected_version in number, p_opening_id in number, p_gambit_id in number, p_variation_id in number, p_commentary_kind in varchar2, p_title in varchar2, p_content in clob, p_new_version out number);
  -- Require the observed version and reject referenced rows; caller owns commit/rollback.
  procedure delete_commentary(p_id number, p_expected_version number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_opening_gambit(p_opening_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_concept_opening(p_concept_id number, p_opening_id number, p_expected_version number, p_link boolean, p_new_version out number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_concept_gambit(p_concept_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_concept_variation(p_concept_id number, p_variation_id number, p_expected_version number, p_link boolean, p_new_version out number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_video_opening(p_video_id number, p_opening_id number, p_expected_version number, p_link boolean, p_new_version out number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_video_gambit(p_video_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_video_variation(p_video_id number, p_variation_id number, p_expected_version number, p_link boolean, p_new_version out number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_image_opening(p_image_id number, p_opening_id number, p_expected_version number, p_link boolean, p_new_version out number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_image_gambit(p_image_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_image_variation(p_image_id number, p_variation_id number, p_expected_version number, p_link boolean, p_new_version out number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_opening_eco(p_opening_id number, p_eco_code varchar2, p_expected_version number, p_link boolean, p_new_version out number);
  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_opening_alias(p_opening_id number, p_alias_name varchar2, p_expected_version number, p_link boolean, p_new_version out number);

  -- Link or unlink explicit identities atomically; increment affected aggregate versions.
  procedure link_gambit_opening(p_gambit_id number,p_opening_id number,p_expected_version number,p_link boolean,p_new_version out number);
  -- Null original identity inserts; updates require the observed version.
  -- Renames and deletes reject creators referenced by videos; caller owns transaction.
  procedure save_content_source(
    p_original_creator in varchar2, p_expected_version in number,
    p_creator in varchar2, p_author in varchar2, p_notes in clob,
    p_new_version out number);
  procedure delete_content_source(p_creator in varchar2, p_expected_version in number);
  -- Atomically create/link videos; both observed aggregate versions are required. Caller owns transaction.
  procedure set_subject_video_link(p_subject_type in varchar2, p_subject_id in number, p_expected_subject_version in number, p_video_id in number, p_expected_video_version in number, p_link in boolean, p_new_subject_version out number, p_new_video_version out number);
  procedure create_video_for_subject(p_platform in varchar2, p_external_video_id in varchar2, p_video_url in varchar2, p_title in varchar2, p_creator in varchar2, p_description in clob, p_duration_seconds in number, p_published_on in date, p_subject_type in varchar2, p_subject_id in number, p_expected_subject_version in number, p_video_id out number, p_new_subject_version out number, p_new_video_version out number);
end chess_admin_api;
/
--rollback drop package orac_chess.chess_admin_api;
