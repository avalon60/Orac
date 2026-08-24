--liquibase formatted sql

--changeset clive:create_trigger_orac_core_dom_refval_bud context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: protect stable reference-value identity and maintain update audit columns

create or replace trigger orac_core.dom_refval_bud
before update or delete on orac_core.domain_ref_values
for each row
begin
  if deleting and :old.system_required_yn = 'Y'
  then
    raise_application_error(-20062, 'A system-required reference value cannot be deleted.');
  end if;

  if updating
  then
    if :old.system_required_yn = 'Y' and :new.system_required_yn <> 'Y'
    then
      raise_application_error(-20062, 'A system-required reference value cannot be unprotected.');
    end if;

    if nvl(:new.domain_code, chr(0)) <> nvl(:old.domain_code, chr(0))
       or nvl(:new.ref_value_code, chr(0)) <> nvl(:old.ref_value_code, chr(0))
    then
      raise_application_error(-20063, 'Reference value identifiers cannot be changed.');
    end if;

    :new.updated_on := systimestamp;
    :new.updated_by := coalesce(
                         sys_context('apex$session', 'app_user'),
                         sys_context('userenv', 'proxy_user'),
                         sys_context('userenv', 'session_user'),
                         user
                       );
    :new.row_version := nvl(:old.row_version, 1) + 1;
  end if;
end;
/

--rollback drop trigger orac_core.dom_refval_bud;
