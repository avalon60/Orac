--liquibase formatted sql

--changeset clive:create_view_orac_code_vector_distance_metric_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.vector_distance_metric_v as
select ref.ref_value_code vector_distance_metric_code,
       ref.display_value,
       ref.description,
       ref.display_sequence,
       ref.icon,
       ref.color,
       dom.active_yn domain_active_yn,
       ref.active_yn,
       ref.system_required_yn
  from orac_api.domain_codes_v dom
  join orac_api.domain_ref_values_v ref
    on ref.domain_code = dom.domain_code
 where dom.domain_code = 'VECTOR_DISTANCE_METRIC';
--rollback drop view orac_code.vector_distance_metric_v;
