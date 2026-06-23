set define off
-- Author: Clive Bostock
-- Date: 22-Jun-2026
-- Description: SQLcl entrypoint for core Orac Liquibase deployment.

set echo on
set sqlblanklines on
whenever sqlerror exit sql.sqlcode

prompt Installing production database changes through Liquibase
liquibase update -changelog-file productController.xml
prompt Completed production database Liquibase install
