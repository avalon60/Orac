-- __author__: clive
-- __date__: 2026-04-24
-- __description__: generated/synchronised by split_ddl; one object per file


create or replace trigger orac.message_embeddings_bu
before update on orac.message_embeddings
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := sys_context('userenv', 'session_user');
  :new.row_version := nvl(:old.row_version, 1) + 1;
end;
/
