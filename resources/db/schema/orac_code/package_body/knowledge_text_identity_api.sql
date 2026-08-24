--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Implements canonical UTF-8 identity validation for knowledge text.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_body_orac_code_knowledge_text_identity_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.knowledge_text_identity_api
as
  procedure calculate_canonical_markdown(
    p_text      in clob,
    p_sha256    out varchar2,
    p_byte_size out number
  )
  is
    l_blob               blob;
    l_destination_offset integer := 1;
    l_source_offset      integer := 1;
    l_language_context   integer := dbms_lob.default_lang_ctx;
    l_warning            integer;
    l_length             number;
  begin
    l_length := dbms_lob.getlength(p_text);
    if l_length = 0
       or dbms_lob.substr(p_text, 1, 1) = unistr('\feff')
       or dbms_lob.instr(p_text, chr(13)) > 0
       or dbms_lob.substr(p_text, 1, l_length) <> chr(10)
    then
      raise_application_error(
        -20500,
        'Canonical Markdown must be non-empty UTF-8 text without BOM or CR and with a terminal LF.'
      );
    end if;

    dbms_lob.createtemporary(l_blob, true);
    dbms_lob.converttoblob(
      dest_lob     => l_blob,
      src_clob     => p_text,
      amount       => dbms_lob.lobmaxsize,
      dest_offset  => l_destination_offset,
      src_offset   => l_source_offset,
      blob_csid    => nls_charset_id('AL32UTF8'),
      lang_context => l_language_context,
      warning      => l_warning
    );
    if l_warning <> dbms_lob.no_warning
    then
      raise_application_error(-20501, 'Canonical Markdown UTF-8 conversion failed.');
    end if;
    p_byte_size := dbms_lob.getlength(l_blob);
    p_sha256 := lower(rawtohex(dbms_crypto.hash(l_blob, dbms_crypto.hash_sh256)));
    dbms_lob.freetemporary(l_blob);
  exception
    when others then
      if dbms_lob.istemporary(l_blob) = 1
      then
        dbms_lob.freetemporary(l_blob);
      end if;
      raise;
  end calculate_canonical_markdown;
end knowledge_text_identity_api;
/
--rollback drop package body orac_code.knowledge_text_identity_api;
