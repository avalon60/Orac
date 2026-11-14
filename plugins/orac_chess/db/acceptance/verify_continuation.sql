-- Author: Clive Bostock
-- Date: 10-Nov-2026
-- Purpose: Verify continuation writes and retained descendant protection through public APIs.
-- Usage: Run as ORAC_CHESS only in an authorised isolated installed database.
-- Fixture writes roll back; this script performs no deployment or permanent data changes.
whenever sqlerror exit failure rollback
set serveroutput on
declare
  l_owner number;
  l_other_owner number;
  l_root number;
  l_child number;
  l_grandchild number;
  l_alternative number;
  l_attempt number;
  l_version number;
  l_next number;
  l_count number;
  l_before number;
  l_code number;
  procedure reject_child(p_name varchar2,p_pgn varchar2,p_ply number,p_owner number,p_fen varchar2 default null) is
  begin
    l_attempt := null;
    l_code := 0;
    begin
      orac_chess.chess_variation_api.save_variation(l_attempt,null,p_owner,null,l_root,
        p_ply,p_name,'CONTINUATION',to_clob(p_pgn),p_fen,null,l_next);
    exception
      when others then
        l_code := sqlcode;
        if l_code not in (-20008,-20023,-20025) then raise; end if;
    end;
    if l_code = 0 then raise_application_error(-20999,'Invalid continuation accepted: ' || p_name); end if;
  end;
begin
  savepoint continuation_acceptance;
  orac_chess.chess_admin_api.save_opening(l_owner,null,'Continuation acceptance owner','OPENING',null,null,l_next);
  orac_chess.chess_admin_api.save_opening(l_other_owner,null,'Continuation acceptance other owner','OPENING',null,null,l_next);
  orac_chess.chess_variation_api.save_variation(l_root,null,l_owner,null,null,null,'Root','MAIN',to_clob('1.e4 e5 *'),null,null,l_version);
  orac_chess.chess_variation_api.save_variation(l_child,null,l_owner,null,l_root,2,'Continuation','CONTINUATION',to_clob('1.e4 e5 2.Nf3 *'),null,null,l_next);
  orac_chess.chess_variation_api.save_variation(l_grandchild,null,l_owner,null,l_child,3,'Grandchild','CONTINUATION',to_clob('1.e4 e5 2.Nf3 Nc6 *'),null,null,l_next);
  orac_chess.chess_variation_api.save_variation(l_alternative,null,l_owner,null,l_root,1,'Alternative','ALTERNATIVE',to_clob('1.e4 c5 *'),null,null,l_next);
  select count(*) into l_before from orac_chess.chess_variation_v where opening_id=l_owner;
  reject_child('Wrong prefix','1.e4 c5 2.Nf3 *',2,l_owner);
  reject_child('Equal','1.e4 e5 *',2,l_owner);
  reject_child('Shorter','1.e4 *',2,l_owner);
  reject_child('Wrong ply','1.e4 e5 2.Nf3 *',1,l_owner);
  reject_child('Wrong owner','1.e4 e5 2.Nf3 *',2,l_other_owner);
  reject_child('Own FEN','1.e4 e5 2.Nf3 *',2,l_owner,'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
  l_code := 0;
  begin
    -- The immediate root is valid; retained continuations make this update invalid.
    orac_chess.chess_variation_api.save_variation(l_root,l_version,l_owner,null,null,null,
      'Root','MAIN',to_clob('1.d4 d5 *'),null,null,l_next);
  exception
    when others then
      l_code := sqlcode;
      if l_code != -20025 then raise; end if;
  end;
  if l_code = 0 then raise_application_error(-20999,'Parent edit stranded continuations'); end if;
  select count(*) into l_count from orac_chess.chess_variation_v where opening_id=l_owner;
  if l_count != l_before then raise_application_error(-20999,'Rejected writes left partial rows'); end if;
  select count(*) into l_count from orac_chess.chess_variation_v
  where variation_id=l_root and row_version=l_version and dbms_lob.compare(pgn,to_clob('1.e4 e5 *'))=0;
  if l_count != 1 then raise_application_error(-20999,'Rejected ancestor edit was not atomic'); end if;
  rollback to continuation_acceptance;
  dbms_output.put_line('PASS: continuation, grandchild, alternative, rejection, subtree and atomic rollback');
exception
  when others then
    rollback to continuation_acceptance;
    raise;
end;
/
