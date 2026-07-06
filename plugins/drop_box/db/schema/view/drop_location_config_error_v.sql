--liquibase formatted sql

--changeset clive:create_view_orac_dropbox_view_drop_location_config_error_v context:plugin,prod labels:plugin,drop_box stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: exposes enabled drop locations omitted from runtime scanning because of profile configuration errors

create or replace view orac_dropbox.drop_location_config_error_v as
select loc.drop_location_id,
       loc.location_code,
       loc.display_name,
       loc.processing_profile,
       case
         when prf.profile_code is null then 'Processing profile is unknown.'
         when prf.active_yn <> 'Y' then 'Processing profile is inactive.'
       end as error_message
  from orac_dropbox.drop_location loc
  left join orac_dropbox.drop_processing_profile prf
    on prf.profile_code = loc.processing_profile
 where loc.enabled_yn = 'Y'
   and (prf.profile_code is null or prf.active_yn <> 'Y');
/

--rollback drop view orac_dropbox.drop_location_config_error_v;
