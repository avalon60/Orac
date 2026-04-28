-- Author: Clive Bostock
--   Date: 15 Mar 2026
--
-- Orac script to add grants to ords_public_user. This was a workaround as we couldn't
-- get the ORDS installer to behave.
--
-- 024-ords-post-install.sql
alter session set container=FREEPDB1;

alter user apex_public_user grant connect through ords_public_user;
alter user apex_rest_public_user grant connect through ords_public_user;
alter user apex_listener grant connect through ords_public_user;

