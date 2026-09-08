--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Sep-2026
-- Description: Rejects installed states that retain legacy knowledge dependencies.

--changeset clive:validate_legacy_knowledge_embedding_purge context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runAlways:true
declare
  l_violation_count number;
begin
  select sum(violation_count)
    into l_violation_count
    from (
      select count(*) violation_count
        from dba_objects
       where owner like 'ORAC%'
         and object_name in (
           'KNOWLEDGE_CHUNK_EMBEDDINGS',
           'KNOWLEDGE_CHUNK_EMBEDDINGS_V',
           'KNOWLEDGE_SEARCHABLE_CHUNKS_V'
         )
      union all
      select count(*)
        from dba_dependencies
       where owner like 'ORAC%'
         and referenced_name in (
           'KNOWLEDGE_CHUNK_EMBEDDINGS',
           'KNOWLEDGE_CHUNK_EMBEDDINGS_V',
           'KNOWLEDGE_SEARCHABLE_CHUNKS_V'
         )
      union all
      select count(*)
        from dba_source
       where owner like 'ORAC%'
         and (
           upper(text) like '%KNOWLEDGE_CHUNK_EMBEDDINGS%'
           or upper(text) like '%KNOWLEDGE_SEARCHABLE_CHUNKS_V%'
         )
      union all
      select count(*)
        from dba_views
       where owner like 'ORAC%'
         and (
           upper(text_vc) like '%KNOWLEDGE_CHUNK_EMBEDDINGS%'
           or upper(text_vc) like '%KNOWLEDGE_SEARCHABLE_CHUNKS_V%'
         )
      union all
      select count(*)
        from dba_synonyms
       where owner like 'ORAC%'
         and table_name in (
           'KNOWLEDGE_CHUNK_EMBEDDINGS',
           'KNOWLEDGE_CHUNK_EMBEDDINGS_V',
           'KNOWLEDGE_SEARCHABLE_CHUNKS_V'
         )
      union all
      select count(*)
        from dba_tab_privs
       where owner like 'ORAC%'
         and table_name in (
           'KNOWLEDGE_CHUNK_EMBEDDINGS',
           'KNOWLEDGE_CHUNK_EMBEDDINGS_V',
           'KNOWLEDGE_SEARCHABLE_CHUNKS_V'
         )
    );

  if l_violation_count <> 0
  then
    raise_application_error(
      -20991,
      'LEGACY_KNOWLEDGE_EMBEDDING_OBJECT_OR_DEPENDENCY_PRESENT'
    );
  end if;
end;
/
