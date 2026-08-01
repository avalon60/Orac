--liquibase formatted sql

--changeset clive:create_package_body_orac_api_knowledge_tags_tapi context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
create or replace package body orac_api.knowledge_tags_tapi
as
  procedure ins(
    p_row in out orac_api.knowledge_tags_v%rowtype
  )
  is
  begin
    insert into orac_api.knowledge_tags_v (
      tag_code, display_name, description, active_yn, system_yn, sort_order
    ) values (
      p_row.tag_code, p_row.display_name, p_row.description,
      p_row.active_yn, p_row.system_yn, p_row.sort_order
    )
    returning knowledge_tag_id, row_version
         into p_row.knowledge_tag_id, p_row.row_version;
  end ins;

  procedure upd(
    p_knowledge_tag_id in     orac_api.knowledge_tags_v.knowledge_tag_id%type,
    p_row              in out orac_api.knowledge_tags_v%rowtype
  )
  is
  begin
    update orac_api.knowledge_tags_v
       set display_name = p_row.display_name,
           description  = p_row.description,
           active_yn    = p_row.active_yn,
           system_yn    = p_row.system_yn,
           sort_order   = p_row.sort_order,
           updated_by   = coalesce(
                            sys_context('apex$session', 'app_user'),
                            sys_context('userenv', 'proxy_user'),
                            sys_context('userenv', 'session_user'),
                            user
                          ),
           updated_on   = systimestamp,
           row_version  = row_version + 1
     where knowledge_tag_id = p_knowledge_tag_id
       and row_version = p_row.row_version
    returning row_version into p_row.row_version;
    if sql%rowcount = 0
    then
      raise_application_error(-20100, 'Knowledge tag was changed by another session.');
    end if;
  end upd;
end knowledge_tags_tapi;
/
--rollback drop package body orac_api.knowledge_tags_tapi;
