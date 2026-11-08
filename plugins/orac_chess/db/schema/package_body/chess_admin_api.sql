--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_admin_api_body context:plugin,prod labels:plugin stripComments:false runOnChange:true endDelimiter:/
create or replace package body orac_chess.chess_admin_api as
  procedure save_opening(p_id in out number, p_expected_version in number, p_name in varchar2, p_opening_type in varchar2, p_description in clob, p_parent_opening_id in number, p_new_version out number) is
  begin
    chess_admin_tapi.save_opening(p_id, p_expected_version, p_name, p_opening_type, p_description, p_parent_opening_id, p_new_version);
  end;
  procedure save_opening_with_eco(p_id in out number, p_expected_version in number, p_name in varchar2, p_opening_type in varchar2, p_description in clob, p_parent_opening_id in number, p_eco_codes in varchar2, p_new_version out number) is
  begin
    chess_admin_tapi.save_opening_with_eco(p_id,p_expected_version,p_name,p_opening_type,p_description,p_parent_opening_id,p_eco_codes,p_new_version);
  end;
  procedure delete_opening(p_id number, p_expected_version number) is
  begin
    chess_admin_tapi.delete_opening(p_id,p_expected_version);
  end;
  procedure save_gambit(p_id in out number, p_expected_version in number, p_name in varchar2, p_description in clob, p_new_version out number) is
  begin
    chess_admin_tapi.save_gambit(p_id, p_expected_version, p_name, p_description, p_new_version);
  end;
  procedure delete_gambit(p_id number, p_expected_version number) is
  begin
    chess_admin_tapi.delete_gambit(p_id,p_expected_version);
  end;
  procedure save_concept(p_id in out number, p_expected_version in number, p_concept_code in varchar2, p_name in varchar2, p_category_code in varchar2, p_description in clob, p_new_version out number) is
  begin
    chess_admin_tapi.save_concept(p_id, p_expected_version, p_concept_code, p_name, p_category_code, p_description, p_new_version);
  end;
  procedure delete_concept(p_id number, p_expected_version number) is
  begin
    chess_admin_tapi.delete_concept(p_id,p_expected_version);
  end;
  procedure save_video(p_id in out number, p_expected_version in number, p_platform in varchar2, p_external_video_id in varchar2, p_video_url in varchar2, p_title in varchar2, p_creator in varchar2, p_description in clob, p_duration_seconds in number, p_published_on in date, p_new_version out number) is
  begin
    chess_admin_tapi.save_video(p_id, p_expected_version, p_platform, p_external_video_id, p_video_url, p_title, p_creator, p_description, p_duration_seconds, p_published_on, p_new_version);
  end;
  procedure delete_video(p_id number, p_expected_version number) is
  begin
    chess_admin_tapi.delete_video(p_id,p_expected_version);
  end;
  procedure save_commentary(p_id in out number, p_expected_version in number, p_opening_id in number, p_gambit_id in number, p_variation_id in number, p_commentary_kind in varchar2, p_title in varchar2, p_content in clob, p_new_version out number) is
  begin
    chess_admin_tapi.save_commentary(p_id, p_expected_version, p_opening_id, p_gambit_id, p_variation_id, p_commentary_kind, p_title, p_content, p_new_version);
  end;
  procedure delete_commentary(p_id number, p_expected_version number) is
  begin
    chess_admin_tapi.delete_commentary(p_id,p_expected_version);
  end;
  procedure link_opening_gambit(p_opening_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_opening_gambit(p_opening_id,p_gambit_id,p_expected_version,p_link,p_new_version);
  end;
  procedure link_concept_opening(p_concept_id number, p_opening_id number, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_concept_opening(p_concept_id,p_opening_id,p_expected_version,p_link,p_new_version);
  end;
  procedure link_concept_gambit(p_concept_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_concept_gambit(p_concept_id,p_gambit_id,p_expected_version,p_link,p_new_version);
  end;
  procedure link_concept_variation(p_concept_id number, p_variation_id number, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_concept_variation(p_concept_id,p_variation_id,p_expected_version,p_link,p_new_version);
  end;
  procedure link_video_opening(p_video_id number, p_opening_id number, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_video_opening(p_video_id,p_opening_id,p_expected_version,p_link,p_new_version);
  end;
  procedure link_video_gambit(p_video_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_video_gambit(p_video_id,p_gambit_id,p_expected_version,p_link,p_new_version);
  end;
  procedure link_video_variation(p_video_id number, p_variation_id number, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_video_variation(p_video_id,p_variation_id,p_expected_version,p_link,p_new_version);
  end;
  procedure link_image_opening(p_image_id number, p_opening_id number, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_image_opening(p_image_id,p_opening_id,p_expected_version,p_link,p_new_version);
  end;
  procedure link_image_gambit(p_image_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_image_gambit(p_image_id,p_gambit_id,p_expected_version,p_link,p_new_version);
  end;
  procedure link_image_variation(p_image_id number, p_variation_id number, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_image_variation(p_image_id,p_variation_id,p_expected_version,p_link,p_new_version);
  end;
  procedure link_opening_eco(p_opening_id number, p_eco_code varchar2, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_opening_eco(p_opening_id,p_eco_code,p_expected_version,p_link,p_new_version);
  end;
  procedure link_opening_alias(p_opening_id number, p_alias_name varchar2, p_expected_version number, p_link boolean, p_new_version out number) is
  begin
    chess_admin_tapi.link_opening_alias(p_opening_id,p_alias_name,p_expected_version,p_link,p_new_version);
  end;

  procedure link_gambit_opening(p_gambit_id number,p_opening_id number,p_expected_version number,p_link boolean,p_new_version out number) is
  begin
    chess_admin_tapi.link_gambit_opening(p_gambit_id,p_opening_id,p_expected_version,p_link,p_new_version);
  end;
  procedure save_content_source(
    p_original_creator in varchar2, p_expected_version in number,
    p_creator in varchar2, p_author in varchar2, p_notes in clob,
    p_new_version out number) is
  begin
    chess_admin_tapi.save_content_source(
      p_original_creator, p_expected_version, p_creator, p_author, p_notes,
      p_new_version);
  end save_content_source;

  procedure delete_content_source(p_creator in varchar2, p_expected_version in number) is
  begin
    chess_admin_tapi.delete_content_source(p_creator, p_expected_version);
  end delete_content_source;
  procedure set_subject_video_link(p_subject_type in varchar2, p_subject_id in number, p_expected_subject_version in number, p_video_id in number, p_expected_video_version in number, p_link in boolean, p_new_subject_version out number, p_new_video_version out number) is
  begin
    chess_admin_tapi.set_subject_video_link(p_subject_type => p_subject_type, p_subject_id => p_subject_id, p_expected_subject_version => p_expected_subject_version, p_video_id => p_video_id, p_expected_video_version => p_expected_video_version, p_link => p_link, p_new_subject_version => p_new_subject_version, p_new_video_version => p_new_video_version);
  end set_subject_video_link;
  procedure create_video_for_subject(p_platform in varchar2, p_external_video_id in varchar2, p_video_url in varchar2, p_title in varchar2, p_creator in varchar2, p_description in clob, p_duration_seconds in number, p_published_on in date, p_subject_type in varchar2, p_subject_id in number, p_expected_subject_version in number, p_video_id out number, p_new_subject_version out number, p_new_video_version out number) is
  begin
    chess_admin_tapi.create_video_for_subject(p_platform => p_platform, p_external_video_id => p_external_video_id, p_video_url => p_video_url, p_title => p_title, p_creator => p_creator, p_description => p_description, p_duration_seconds => p_duration_seconds, p_published_on => p_published_on, p_subject_type => p_subject_type, p_subject_id => p_subject_id, p_expected_subject_version => p_expected_subject_version, p_video_id => p_video_id, p_new_subject_version => p_new_subject_version, p_new_video_version => p_new_video_version);
  end create_video_for_subject;
end chess_admin_api;
/
--rollback drop package body orac_chess.chess_admin_api;
