--liquibase formatted sql

--changeset clive:create_package_body_orac_plugin_knowledge_tag_validation_api context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
create or replace package body orac_plugin.knowledge_tag_validation_api
as
  function canonical_active_tags(
    p_classification_tags_json in clob,
    p_require_non_empty_yn     in varchar2 default 'N'
  ) return clob
  is
    l_array             json_array_t;
    l_element           json_element_t;
    l_ref_value_code    varchar2(100 char);
    l_tag_count         number;
    l_active_count      number;
    l_canonical         clob;
    type tag_seen_type is table of boolean index by varchar2(100);
    l_seen_tags         tag_seen_type;
  begin
    if p_classification_tags_json is null
       or dbms_lob.getlength(p_classification_tags_json) > 4096
    then
      raise_application_error(-20200, 'Classification tag JSON is missing or oversized.');
    end if;
    if upper(coalesce(p_require_non_empty_yn, 'N')) not in ('Y', 'N')
    then
      raise_application_error(-20201, 'Require-non-empty flag must be Y or N.');
    end if;

    begin
      l_array := json_array_t.parse(p_classification_tags_json);
    exception
      when others then
        raise_application_error(-20202, 'Classification tags must be a JSON array.');
    end;
    l_tag_count := l_array.get_size;
    if (upper(coalesce(p_require_non_empty_yn, 'N')) = 'Y' and l_tag_count = 0)
       or l_tag_count > 10
    then
      raise_application_error(-20203, 'Choose one to ten classification tags.');
    end if;

    if l_tag_count > 0
    then
      for l_index in 0 .. l_tag_count - 1
      loop
        l_element := l_array.get(l_index);
        if l_element is null or not l_element.is_string
        then
          raise_application_error(-20204, 'Classification tag entries must be strings.');
        end if;
        l_ref_value_code := l_array.get_string(l_index);
        if l_seen_tags.exists(l_ref_value_code)
        then
          raise_application_error(-20205, 'Duplicate classification tags are not allowed.');
        end if;
        l_seen_tags(l_ref_value_code) := true;
      end loop;
    end if;

    select count(*),
           json_arrayagg(
             tag.return_value
             order by tag.sort_order, tag.return_value
             returning clob
           )
      into l_active_count, l_canonical
      from orac_code.knowledge_tag_lov_v tag
      join json_table(
             p_classification_tags_json,
             '$[*]' columns (
               ref_value_code varchar2(100 char) path '$'
             )
           ) selected
        on selected.ref_value_code = tag.return_value;

    if l_active_count <> l_tag_count
    then
      raise_application_error(-20206, 'Classification tag is unknown or inactive.');
    end if;
    return coalesce(l_canonical, to_clob('[]'));
  end canonical_active_tags;
end knowledge_tag_validation_api;
/
--rollback drop package body orac_plugin.knowledge_tag_validation_api;
