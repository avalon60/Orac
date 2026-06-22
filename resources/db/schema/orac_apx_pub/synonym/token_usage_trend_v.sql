--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_synonym_token_usage_trend_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: public-facing token usage trend view synonym

create or replace synonym orac_apx_pub.token_usage_trend_v for orac_code.token_usage_trend_v;

--rollback drop synonym orac_apx_pub.token_usage_trend_v;
