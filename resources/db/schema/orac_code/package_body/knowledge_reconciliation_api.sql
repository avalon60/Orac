--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-14
-- Description: Implements bounded read-only knowledge reconciliation inventories.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_body_orac_code_knowledge_reconciliation_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.knowledge_reconciliation_api
as
  c_max_inventory_rows constant pls_integer := 1000000;

  function bounded_limit(
    p_limit in number
  ) return pls_integer
  is
  begin
    if p_limit is null
       or p_limit < 1
       or p_limit > c_max_inventory_rows
       or p_limit <> trunc(p_limit)
    then
      raise_application_error(
        -20550,
        'Reconciliation row limit must be an integer between 1 and 1000000.'
      );
    end if;
    return trunc(p_limit);
  end bounded_limit;

  procedure open_registered_references(
    p_rows  out sys_refcursor,
    p_limit in number default 100001
  )
  is
    l_limit pls_integer := bounded_limit(p_limit);
  begin
    open p_rows for
      select reference_kind,
             reference_id,
             document_version_id,
             extraction_id,
             artefact_role_code,
             content_sha256,
             storage_key,
             byte_size,
             media_type,
             created_on
        from (
          select 'RAW' reference_kind,
                 ver.document_version_id reference_id,
                 ver.document_version_id,
                 cast(null as number) extraction_id,
                 cast(null as varchar2(50 char)) artefact_role_code,
                 ver.content_sha256,
                 ver.content_uri storage_key,
                 ver.byte_size,
                 ver.mime_type media_type,
                 ver.created_on
            from orac_api.knowledge_document_versions_v ver
          union all
          select 'ARTEFACT' reference_kind,
                 art.artefact_id reference_id,
                 ext.document_version_id,
                 art.extraction_id,
                 art.artefact_role_code,
                 art.content_sha256,
                 art.storage_key,
                 art.byte_size,
                 art.media_type,
                 art.created_on
            from orac_api.knowledge_artefacts_v art
            join orac_api.knowledge_extractions_v ext
              on ext.extraction_id = art.extraction_id
        )
       order by reference_kind, reference_id
       fetch first l_limit rows only;
  end open_registered_references;

  procedure open_lineage_inventory(
    p_rows  out sys_refcursor,
    p_limit in number default 100001
  )
  is
    l_limit pls_integer := bounded_limit(p_limit);
  begin
    open p_rows for
      select lineage_kind,
             lineage_id,
             document_version_id,
             extraction_id,
             source_artefact_id,
             source_artefact_extraction_id,
             member_count,
             primary_member_count,
             table_member_count,
             minimum_ordinal,
             maximum_ordinal,
             complete_yn,
             text_sha256,
             source_content_sha256,
             chunk_count
        from (
          select 'EXTRACTION' lineage_kind,
                 ext.extraction_id lineage_id,
                 ext.document_version_id,
                 ext.extraction_id,
                 cast(null as number) source_artefact_id,
                 cast(null as number) source_artefact_extraction_id,
                 artset.member_count,
                 artset.primary_member_count,
                 artset.table_member_count,
                 artset.minimum_ordinal,
                 artset.maximum_ordinal,
                 artset.complete_yn,
                 ext.text_sha256,
                 artset.source_content_sha256,
                 cast(null as number) chunk_count
            from orac_api.knowledge_extractions_v ext
            left join (
              select extset.extraction_id,
                     count(artset.artefact_id) member_count,
                     sum(
                       case
                         when artset.artefact_role_code in ('PRIMARY', 'MANIFEST')
                         then 1
                         else 0
                       end
                     ) primary_member_count,
                     sum(
                       case when artset.artefact_role_code = 'TABLE' then 1 else 0 end
                     ) table_member_count,
                     min(artset.member_ordinal) minimum_ordinal,
                     max(artset.member_ordinal) maximum_ordinal,
                     max(
                       case
                         when artset.artefact_role_code in ('PRIMARY', 'MANIFEST')
                         then artset.content_sha256
                       end
                     ) source_content_sha256,
                     case
                       when count(artset.artefact_id) > 0
                        and sum(
                              case
                                when artset.artefact_role_code in ('PRIMARY', 'MANIFEST')
                                then 1
                                else 0
                              end
                            ) = 1
                        and min(artset.member_ordinal) = 1
                        and max(artset.member_ordinal) = count(artset.artefact_id)
                        and max(
                              case
                                when artset.artefact_role_code in ('PRIMARY', 'MANIFEST')
                                then artset.content_sha256
                              end
                            ) = extset.text_sha256
                        and (
                          (
                            sum(
                              case
                                when artset.artefact_role_code = 'PRIMARY' then 1 else 0
                              end
                            ) = 1
                            and sum(
                                  case
                                    when artset.artefact_role_code = 'TABLE' then 1 else 0
                                  end
                                ) = 0
                          )
                          or
                          (
                            sum(
                              case
                                when artset.artefact_role_code = 'MANIFEST' then 1 else 0
                              end
                            ) = 1
                            and sum(
                                  case
                                    when artset.artefact_role_code = 'TABLE' then 1 else 0
                                  end
                                ) > 0
                          )
                        )
                       then 'Y'
                       else 'N'
                     end complete_yn
                from orac_api.knowledge_extractions_v extset
                left join orac_api.knowledge_artefacts_v artset
                  on artset.extraction_id = extset.extraction_id
               group by extset.extraction_id, extset.text_sha256
            ) artset
              on artset.extraction_id = ext.extraction_id
          union all
          select 'CHUNK_SET' lineage_kind,
                 chs.chunk_set_id lineage_id,
                 ext.document_version_id,
                 chs.extraction_id,
                 chs.source_artefact_id,
                 art.extraction_id source_artefact_extraction_id,
                 cast(null as number) member_count,
                 cast(null as number) primary_member_count,
                 cast(null as number) table_member_count,
                 cast(null as number) minimum_ordinal,
                 cast(null as number) maximum_ordinal,
                 cast(null as varchar2(1 char)) complete_yn,
                 cast(null as varchar2(64 char)) text_sha256,
                 art.content_sha256 source_content_sha256,
                 (
                   select count(*)
                     from orac_api.knowledge_chunks_v chn
                    where chn.chunk_set_id = chs.chunk_set_id
                 ) chunk_count
            from orac_api.knowledge_chunk_sets_v chs
            join orac_api.knowledge_extractions_v ext
              on ext.extraction_id = chs.extraction_id
            left join orac_api.knowledge_artefacts_v art
              on art.artefact_id = chs.source_artefact_id
        )
       order by lineage_kind, lineage_id
       fetch first l_limit rows only;
  end open_lineage_inventory;
end knowledge_reconciliation_api;
/
--rollback drop package body orac_code.knowledge_reconciliation_api;
