-- Author: Clive Bostock
-- Date: 15-Aug-2026
-- Purpose: Exercise Phase 1 artefact and chunk-set lineage in a rollback-only transaction.
-- Usage: sql -S -name orac-db @resources/db/acceptance/knowledge_materialisation_lifecycle.sql
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

whenever sqlerror exit failure rollback

set define off
set feedback on
set serveroutput on size unlimited

declare
  l_suffix                 varchar2(32) := lower(rawtohex(sys_guid()));
  l_request_id             number;
  l_document_version_id    number;
  l_legacy_extraction_id   number;
  l_single_extraction_id   number;
  l_other_extraction_id    number;
  l_sheet_extraction_id    number;
  l_primary_artefact_id    number;
  l_other_artefact_id      number;
  l_manifest_artefact_id   number;
  l_table_alpha_id         number;
  l_table_beta_id          number;
  l_metadata_artefact_id   number;
  l_first_chunk_set_id     number;
  l_second_chunk_set_id    number;
  l_manifest_chunk_set_id  number;
  l_alpha_chunk_set_id     number;
  l_beta_chunk_set_id      number;
  l_result                 clob;

  procedure assert_equal(
    p_actual   in number,
    p_expected in number,
    p_message  in varchar2
  )
  is
  begin
    if nvl(p_actual, -1) <> nvl(p_expected, -1)
    then
      raise_application_error(-20990, p_message);
    end if;
  end assert_equal;

  procedure assert_distinct(
    p_first   in number,
    p_second  in number,
    p_message in varchar2
  )
  is
  begin
    if p_first = p_second
    then
      raise_application_error(-20991, p_message);
    end if;
  end assert_distinct;

  function artefact_id(
    p_output_set_json in clob,
    p_role            in varchar2,
    p_ordinal         in number
  ) return number
  is
    l_root    json_object_t;
    l_members json_array_t;
    l_member  json_object_t;
  begin
    l_root := json_object_t.parse(p_output_set_json);
    l_members := l_root.get_array('members');
    for l_index in 0 .. l_members.get_size - 1
    loop
      l_member := treat(l_members.get(l_index) as json_object_t);
      if l_member.get_string('role') = p_role
         and l_member.get_number('ordinal') = p_ordinal
      then
        return l_member.get_number('artefact_id');
      end if;
    end loop;
    raise_application_error(-20992, 'Expected artefact member was not returned.');
  end artefact_id;
begin
  l_request_id := orac_code.knowledge_ingestion_api.submit_managed_file(
    p_source_type             => 'P1_10_TEST',
    p_source_reference        => 'p1-10:' || l_suffix,
    p_parent_source_reference => 'p1-10:' || l_suffix,
    p_content_sha256          => '7ce478cce767735522a8002c8900b3237cc273c1a79f3fc56fa65a93e5b5b1c5',
    p_content_uri             => 'sha256:7ce478cce767735522a8002c8900b3237cc273c1a79f3fc56fa65a93e5b5b1c5',
    p_mime_type               => 'text/markdown',
    p_original_filename       => 'p1-10-fixture.md',
    p_byte_size               => 18,
    p_target_scope_type       => 'PROJECT',
    p_target_scope_key        => 'ORAC_CORE',
    p_source_format_code      => 'markdown'
  );

  select document_version_id
    into l_document_version_id
    from orac_code.knowledge_ingestion_requests_v
   where ingestion_request_id = l_request_id;

  l_legacy_extraction_id := orac_code.knowledge_ingestion_api.create_extraction(
    p_document_version_id => l_document_version_id,
    p_extractor_code      => 'p1_10_legacy_fixture',
    p_extractor_version   => '1',
    p_extracted_text      => 'legacy P1-10' || chr(10),
    p_text_sha256         => 'c723dc797dbbab74a7448c921dc1502b77e17247e89d919e4bc586c13924f4a9',
    p_output_mime_type    => 'text/markdown; charset=utf-8'
  );
  l_first_chunk_set_id := orac_code.knowledge_ingestion_api.create_chunk_set(
    p_extraction_id     => l_legacy_extraction_id,
    p_chunker_code      => 'p1_10_legacy_chunks',
    p_chunker_version   => '1',
    p_chunk_size_tokens => 64,
    p_overlap_tokens    => 8
  );
  l_second_chunk_set_id := orac_code.knowledge_ingestion_api.create_chunk_set(
    p_extraction_id     => l_legacy_extraction_id,
    p_chunker_code      => 'p1_10_legacy_chunks',
    p_chunker_version   => '1',
    p_chunk_size_tokens => 64,
    p_overlap_tokens    => 8
  );
  assert_equal(
    l_second_chunk_set_id,
    l_first_chunk_set_id,
    'Legacy null-source chunk-set creation is not idempotent.'
  );

  l_single_extraction_id := orac_code.knowledge_ingestion_api.create_extraction(
    p_document_version_id => l_document_version_id,
    p_extractor_code      => 'p1_10_single_fixture',
    p_extractor_version   => '1',
    p_extracted_text      => '# P1-10 primary' || chr(10),
    p_text_sha256         => '4d0b0cdf2b35bcb8fb20a509eb73d36d9e748dffb3f471180d03d072fd908209',
    p_output_mime_type    => 'text/markdown; charset=utf-8'
  );
  l_result := orac_code.knowledge_artefact_api.register_output_set(
    p_extraction_id => l_single_extraction_id,
    p_output_set_json => q'~{
      "schema_version":1,
      "set_kind":"SINGLE",
      "members":[{
        "role":"PRIMARY",
        "media_type":"text/markdown; charset=utf-8",
        "content_sha256":"4d0b0cdf2b35bcb8fb20a509eb73d36d9e748dffb3f471180d03d072fd908209",
        "storage_key":"sha256:4d0b0cdf2b35bcb8fb20a509eb73d36d9e748dffb3f471180d03d072fd908209",
        "byte_size":16,
        "logical_name":"primary.md",
        "ordinal":1,
        "metadata":null
      }]
    }~'
  );
  l_primary_artefact_id := artefact_id(l_result, 'PRIMARY', 1);

  l_result := orac_code.knowledge_artefact_api.register_output_set(
    p_extraction_id => l_single_extraction_id,
    p_output_set_json => q'~{
      "schema_version":1,"set_kind":"SINGLE","members":[{
        "role":"PRIMARY","media_type":"text/markdown; charset=utf-8",
        "content_sha256":"4d0b0cdf2b35bcb8fb20a509eb73d36d9e748dffb3f471180d03d072fd908209",
        "storage_key":"sha256:4d0b0cdf2b35bcb8fb20a509eb73d36d9e748dffb3f471180d03d072fd908209",
        "byte_size":16,"logical_name":"primary.md","ordinal":1,"metadata":null
      }]
    }~'
  );
  assert_equal(
    artefact_id(l_result, 'PRIMARY', 1),
    l_primary_artefact_id,
    'Identical output-set registration did not reuse the artefact.'
  );

  begin
    l_result := orac_code.knowledge_artefact_api.register_output_set(
      p_extraction_id => l_single_extraction_id,
      p_output_set_json => q'~{
        "schema_version":1,"set_kind":"SINGLE","members":[{
          "role":"PRIMARY","media_type":"text/markdown; charset=utf-8",
          "content_sha256":"4d0b0cdf2b35bcb8fb20a509eb73d36d9e748dffb3f471180d03d072fd908209",
          "storage_key":"sha256:4d0b0cdf2b35bcb8fb20a509eb73d36d9e748dffb3f471180d03d072fd908209",
          "byte_size":16,"logical_name":"changed.md","ordinal":1,"metadata":null
        }]
      }~'
    );
    raise_application_error(-20993, 'Changed output-set registration was accepted.');
  exception
    when others then
      if sqlcode <> -20523
      then
        raise;
      end if;
  end;

  begin
    l_first_chunk_set_id := orac_code.knowledge_ingestion_api.create_chunk_set(
      p_extraction_id     => l_single_extraction_id,
      p_chunker_code      => 'p1_10_markdown_chunks',
      p_chunker_version   => '1',
      p_chunk_size_tokens => 64,
      p_overlap_tokens    => 8
    );
    raise_application_error(-20994, 'Artefact-backed null chunk source was accepted.');
  exception
    when others then
      if sqlcode <> -20432
      then
        raise;
      end if;
  end;

  l_first_chunk_set_id := orac_code.knowledge_ingestion_api.create_chunk_set(
    p_extraction_id      => l_single_extraction_id,
    p_chunker_code       => 'p1_10_markdown_chunks',
    p_chunker_version    => '1',
    p_chunk_size_tokens  => 64,
    p_overlap_tokens     => 8,
    p_source_artefact_id => l_primary_artefact_id
  );
  l_second_chunk_set_id := orac_code.knowledge_ingestion_api.create_chunk_set(
    p_extraction_id      => l_single_extraction_id,
    p_chunker_code       => 'p1_10_markdown_chunks',
    p_chunker_version    => '1',
    p_chunk_size_tokens  => 64,
    p_overlap_tokens     => 8,
    p_source_artefact_id => l_primary_artefact_id
  );
  assert_equal(
    l_second_chunk_set_id,
    l_first_chunk_set_id,
    'Artefact-backed chunk-set creation is not idempotent.'
  );

  l_other_extraction_id := orac_code.knowledge_ingestion_api.create_extraction(
    p_document_version_id => l_document_version_id,
    p_extractor_code      => 'p1_10_other_fixture',
    p_extractor_version   => '1',
    p_extracted_text      => '# P1-10 other' || chr(10),
    p_text_sha256         => 'd089a9e4493db52cdbfa9194b85c071751df587223646562b35212cc9a5ed5ce',
    p_output_mime_type    => 'text/markdown; charset=utf-8'
  );
  l_result := orac_code.knowledge_artefact_api.register_output_set(
    p_extraction_id => l_other_extraction_id,
    p_output_set_json => q'~{
      "schema_version":1,"set_kind":"SINGLE","members":[{
        "role":"PRIMARY","media_type":"text/markdown; charset=utf-8",
        "content_sha256":"d089a9e4493db52cdbfa9194b85c071751df587223646562b35212cc9a5ed5ce",
        "storage_key":"sha256:d089a9e4493db52cdbfa9194b85c071751df587223646562b35212cc9a5ed5ce",
        "byte_size":14,"logical_name":"other.md","ordinal":1,"metadata":null
      }]
    }~'
  );
  l_other_artefact_id := artefact_id(l_result, 'PRIMARY', 1);
  begin
    l_first_chunk_set_id := orac_code.knowledge_ingestion_api.create_chunk_set(
      p_extraction_id      => l_other_extraction_id,
      p_chunker_code       => 'p1_10_cross_extraction',
      p_chunker_version    => '1',
      p_chunk_size_tokens  => 64,
      p_overlap_tokens     => 8,
      p_source_artefact_id => l_primary_artefact_id
    );
    raise_application_error(-20995, 'Cross-extraction chunk source was accepted.');
  exception
    when others then
      if sqlcode <> -20433
      then
        raise;
      end if;
  end;
  if l_other_artefact_id is null
  then
    raise_application_error(-20996, 'Other extraction PRIMARY was not registered.');
  end if;

  l_sheet_extraction_id := orac_code.knowledge_ingestion_api.create_extraction(
    p_document_version_id => l_document_version_id,
    p_extractor_code      => 'p1_10_spreadsheet_fixture',
    p_extractor_version   => '1',
    p_extracted_text      => '# P1-10 manifest' || chr(10),
    p_text_sha256         => '2022a0ef9ff61947a4a9c396ee94c8dccdea0169a6b41571901f525a5bd2ba48',
    p_output_mime_type    => 'text/markdown; charset=utf-8'
  );
  begin
    l_result := orac_code.knowledge_artefact_api.register_output_set(
      p_extraction_id => l_sheet_extraction_id,
      p_output_set_json => q'~{
        "schema_version":1,"set_kind":"SPREADSHEET","members":[{
          "role":"MANIFEST","media_type":"text/markdown; charset=utf-8",
          "content_sha256":"2022a0ef9ff61947a4a9c396ee94c8dccdea0169a6b41571901f525a5bd2ba48",
          "storage_key":"sha256:2022a0ef9ff61947a4a9c396ee94c8dccdea0169a6b41571901f525a5bd2ba48",
          "byte_size":17,"logical_name":"manifest.md","ordinal":1,"metadata":null
        }]
      }~'
    );
    raise_application_error(-20997, 'Incomplete spreadsheet set was accepted.');
  exception
    when others then
      if sqlcode <> -20513
      then
        raise;
      end if;
  end;
  begin
    orac_code.knowledge_artefact_api.assert_complete_set(l_sheet_extraction_id);
    raise_application_error(-20998, 'Rejected partial output set left visible members.');
  exception
    when others then
      if sqlcode <> -20513
      then
        raise;
      end if;
  end;

  l_result := orac_code.knowledge_artefact_api.register_output_set(
    p_extraction_id => l_sheet_extraction_id,
    p_output_set_json => q'~{
      "schema_version":1,
      "set_kind":"SPREADSHEET",
      "members":[
        {
          "role":"MANIFEST","media_type":"text/markdown; charset=utf-8",
          "content_sha256":"2022a0ef9ff61947a4a9c396ee94c8dccdea0169a6b41571901f525a5bd2ba48",
          "storage_key":"sha256:2022a0ef9ff61947a4a9c396ee94c8dccdea0169a6b41571901f525a5bd2ba48",
          "byte_size":17,"logical_name":"manifest.md","ordinal":1,"metadata":null
        },
        {
          "role":"TABLE","media_type":"text/csv; charset=utf-8",
          "content_sha256":"d7bfe0ea50821ba6bf2ad343bd22af2533351d7efbd389ac4594203ee7082268",
          "storage_key":"sha256:d7bfe0ea50821ba6bf2ad343bd22af2533351d7efbd389ac4594203ee7082268",
          "byte_size":19,"logical_name":"alpha.csv","ordinal":2,
          "metadata":{"schema_version":1,"sheet_name":"Alpha","table_name":"AlphaTable","source_cell_range":"A4:B6","header_rows":[4],"hidden_sheet":false}
        },
        {
          "role":"TABLE","media_type":"text/csv; charset=utf-8",
          "content_sha256":"40e1f7871df239066f51723c789dbbe3dbdca52d3b149faaad8572a1d34c49e3",
          "storage_key":"sha256:40e1f7871df239066f51723c789dbbe3dbdca52d3b149faaad8572a1d34c49e3",
          "byte_size":18,"logical_name":"beta.csv","ordinal":3,
          "metadata":{"schema_version":1,"sheet_name":"Beta","table_name":null,"source_cell_range":"C2:D4","header_rows":[],"hidden_sheet":true}
        },
        {
          "role":"METADATA","media_type":"application/json",
          "content_sha256":"ef4ceaf07d27549ef7db143fa22aecc26b6e1f44485849c57f78cee2f59e76c3",
          "storage_key":"sha256:ef4ceaf07d27549ef7db143fa22aecc26b6e1f44485849c57f78cee2f59e76c3",
          "byte_size":20,"logical_name":"metadata.json","ordinal":4,"metadata":null
        }
      ]
    }~'
  );
  l_manifest_artefact_id := artefact_id(l_result, 'MANIFEST', 1);
  l_table_alpha_id := artefact_id(l_result, 'TABLE', 2);
  l_table_beta_id := artefact_id(l_result, 'TABLE', 3);
  l_metadata_artefact_id := artefact_id(l_result, 'METADATA', 4);

  l_manifest_chunk_set_id := orac_code.knowledge_ingestion_api.create_chunk_set(
    p_extraction_id      => l_sheet_extraction_id,
    p_chunker_code       => 'p1_10_markdown_chunks',
    p_chunker_version    => '1',
    p_chunk_size_tokens  => 64,
    p_overlap_tokens     => 8,
    p_source_artefact_id => l_manifest_artefact_id
  );
  l_alpha_chunk_set_id := orac_code.knowledge_ingestion_api.create_chunk_set(
    p_extraction_id      => l_sheet_extraction_id,
    p_chunker_code       => 'p1_10_csv_chunks',
    p_chunker_version    => '1',
    p_chunk_size_tokens  => 64,
    p_overlap_tokens     => 0,
    p_source_artefact_id => l_table_alpha_id
  );
  l_beta_chunk_set_id := orac_code.knowledge_ingestion_api.create_chunk_set(
    p_extraction_id      => l_sheet_extraction_id,
    p_chunker_code       => 'p1_10_csv_chunks',
    p_chunker_version    => '1',
    p_chunk_size_tokens  => 64,
    p_overlap_tokens     => 0,
    p_source_artefact_id => l_table_beta_id
  );
  assert_distinct(
    l_manifest_chunk_set_id,
    l_alpha_chunk_set_id,
    'MANIFEST and TABLE members shared a chunk set.'
  );
  assert_distinct(
    l_alpha_chunk_set_id,
    l_beta_chunk_set_id,
    'Distinct TABLE members shared a chunk set.'
  );
  assert_equal(
    orac_code.knowledge_ingestion_api.create_chunk_set(
      p_extraction_id      => l_sheet_extraction_id,
      p_chunker_code       => 'p1_10_csv_chunks',
      p_chunker_version    => '1',
      p_chunk_size_tokens  => 64,
      p_overlap_tokens     => 0,
      p_source_artefact_id => l_table_alpha_id
    ),
    l_alpha_chunk_set_id,
    'TABLE chunk-set retry did not reuse the existing set.'
  );
  begin
    l_first_chunk_set_id := orac_code.knowledge_ingestion_api.create_chunk_set(
      p_extraction_id      => l_sheet_extraction_id,
      p_chunker_code       => 'p1_10_metadata_chunks',
      p_chunker_version    => '1',
      p_chunk_size_tokens  => 64,
      p_overlap_tokens     => 0,
      p_source_artefact_id => l_metadata_artefact_id
    );
    raise_application_error(-20999, 'METADATA member was accepted as a chunk source.');
  exception
    when others then
      if sqlcode <> -20433
      then
        raise;
      end if;
  end;

  dbms_output.put_line('P1_10_KNOWLEDGE_LIFECYCLE_OK');
  rollback;
exception
  when others then
    rollback;
    raise;
end;
/

rollback;
