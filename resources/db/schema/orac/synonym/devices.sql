--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_devices context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: compatibility synonym for legacy devices access

create or replace synonym orac.devices for orac_api.devices_v;

--rollback drop synonym orac.devices;
