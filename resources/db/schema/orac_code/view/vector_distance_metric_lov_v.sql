--liquibase formatted sql

--changeset clive:create_view_orac_code_vector_distance_metric_lov_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.vector_distance_metric_lov_v as
select vector_distance_metric_code return_value,
       display_value,
       description,
       display_sequence,
       icon,
       color
  from orac_code.vector_distance_metric_v
 where domain_active_yn = 'Y'
   and active_yn = 'Y';
--rollback drop view orac_code.vector_distance_metric_lov_v;
