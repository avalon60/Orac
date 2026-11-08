-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Verify production facade with the complete corpus and Oracle boundaries.
-- Usage: Approved SQLcl owner/admin @plugins/orac_chess/db/acceptance/verify_mle_runtime.sql
-- This does not deploy objects or commit fixture data.
whenever sqlerror exit failure rollback
whenever oserror exit failure rollback
set define off
set sqlblanklines on
set serveroutput on
declare
  l_pgn clob;
  l_parent clob;
  l_depth clob;
  l_code number;
  l_count number := 0;
  procedure check_case(p_name varchar2,p_valid boolean,p_single boolean,p_fen varchar2 default null,p_ply number default null) is
  begin
    l_code:=0;
    begin
      if p_ply is null then
        orac_chess.chess_validation_api.validate_pgn(l_pgn,p_single,p_fen);
      else
        orac_chess.chess_validation_api.validate_branch(l_parent,l_pgn,p_ply,p_fen);
      end if;
    exception when others then
      l_code:=sqlcode;
      if l_code not in (-20021,-20025) then raise; end if;
    end;
    if (p_valid and l_code<>0) or (not p_valid and l_code=0) then
      raise_application_error(-20999,'Production corpus mismatch: '||p_name||' code='||l_code);
    end if;
    l_count:=l_count+1;
    if dbms_lob.istemporary(l_pgn)=1 then dbms_lob.freetemporary(l_pgn); end if;
    if dbms_lob.istemporary(l_parent)=1 then dbms_lob.freetemporary(l_parent); end if;
  end;
begin
  if sys_context('userenv','session_user') not in ('ORAC_CHESS','SYSTEM')
     or sys_context('userenv','con_name')<>'FREEPDB1' then
    raise_application_error(-20998,'Wrong production runtime verification target');
  end if;
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e20653420653520322e204e6633204e6336202a'), 'AL32UTF8'));
  check_case('java-01',true,true,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e6534207b636f6d6d656e747d20653520243120322e4e6633213f204e6336202a'), 'AL32UTF8'));
  check_case('java-02',true,true,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e65342028312e64342064352028312e2e2e4e66362929206535202a'), 'AL32UTF8'));
  check_case('java-03',true,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e65342028312e64342064352028312e2e2e4e66362929206535202a'), 'AL32UTF8'));
  check_case('java-04',false,true,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e65342028312e6434204b653729206535202a'), 'AL32UTF8'));
  check_case('java-05',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e6534206535202a20747261696c696e67'), 'AL32UTF8'));
  check_case('java-06',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e6534206535202a20312e6434'), 'AL32UTF8'));
  check_case('java-07',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e653423206535202a'), 'AL32UTF8'));
  check_case('java-08',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e653420653520322e4e6533202a'), 'AL32UTF8'));
  check_case('java-09',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e6534206535'), 'AL32UTF8'));
  check_case('java-10',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e6534207b756e7465726d696e61746564206535202a'), 'AL32UTF8'));
  check_case('java-11',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e65342028312e6434206535202a'), 'AL32UTF8'));
  check_case('java-12',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('5b526573756c742022312d30225d0a312e6534206535202a'), 'AL32UTF8'));
  check_case('java-13',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('5b46454e2022382f382f382f382f382f382f382f4b366b2077202d202d20302031225d0a312e4b6231202a'), 'AL32UTF8'));
  check_case('java-14',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('5b5365745570202231225d205b46454e2022382f382f382f382f382f382f382f4b366b2077202d202d20302031225d20312e4b6231202a'), 'AL32UTF8'));
  check_case('java-15',true,true,'8/8/8/8/8/8/8/K6k w - - 0 1',null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('5b5365745570202231225d205b46454e2022382f382f382f382f382f382f382f4b4b356b2077202d202d20302031225d20312e4b6231202a'), 'AL32UTF8'));
  check_case('java-16',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e65346535202a'), 'AL32UTF8'));
  check_case('java-17',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e6534202a2028312e643429'), 'AL32UTF8'));
  check_case('java-18',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e65342028312e64342028312e63342065352920643529206535202a'), 'AL32UTF8'));
  check_case('java-19',true,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e65342028312e64342028312e6334204b65372920643529206535202a'), 'AL32UTF8'));
  check_case('java-20',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e653420653520322e4e6633204e633620332e42623520613620342e426134204e663620352e4f2d4f202a'), 'AL32UTF8'));
  check_case('java-21',true,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e4f2d4f202a'), 'AL32UTF8'));
  check_case('java-22',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e653420653520322e516835204e633620332e426334204e663620342e517866372320312d30'), 'AL32UTF8'));
  check_case('java-23',true,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e653420653520322e516835204e633620332e426334204e663620342e517866372b20312d30'), 'AL32UTF8'));
  check_case('java-24',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('5b5365745570202231225d205b46454e2022382f382f382f382f382f382f382f4b366b2077204b202d20302031225d20312e4b6231202a'), 'AL32UTF8'));
  check_case('java-25',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('5b5365745570202231225d205b46454e2022382f382f382f382f382f382f382f4b366b2077202d20653620302031225d20312e4b6231202a'), 'AL32UTF8'));
  check_case('java-26',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('5b5365745570202231225d205b46454e2022382f382f382f382f382f382f382f4b6b362077202d202d20302031225d20312e4b6231202a'), 'AL32UTF8'));
  check_case('java-27',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e6534206335202a'), 'AL32UTF8'));
  l_parent := l_parent || to_clob(utl_i18n.raw_to_char(hextoraw('312e653420653520322e4e6633202a'), 'AL32UTF8'));
  check_case('java-28',true,false,null,1);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e653420653520322e4e6633202a'), 'AL32UTF8'));
  l_parent := l_parent || to_clob(utl_i18n.raw_to_char(hextoraw('312e6534206535202a'), 'AL32UTF8'));
  check_case('java-29',false,false,null,2);
  l_pgn:=null; l_parent:=null;
  check_case('empty',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('2a'), 'AL32UTF8'));
  check_case('only-result',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('5b4576656e74202261225d205b4576656e74202262225d20312e6534202a'), 'AL32UTF8'));
  check_case('duplicate-tag',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e6534202829202a'), 'AL32UTF8'));
  check_case('rav-empty',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e65342028312e2e2e643529202a'), 'AL32UTF8'));
  check_case('rav-number',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e65342028312e6434202a20643529202a'), 'AL32UTF8'));
  check_case('rav-trailing',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e6534207b61207b627d7d202a'), 'AL32UTF8'));
  check_case('nested-comment',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e653420653520322e4e6633204e633620332e426334204e663620342e64332042633520352e4e6432202a'), 'AL32UTF8'));
  check_case('under-specified-san',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('5b4576656e742022615c5c625c2263225d20312e6534202a'), 'AL32UTF8'));
  check_case('escaped-header',true,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('312e6534202a'), 'AL32UTF8'));
  check_case('zero-prefix',true,false,null,null);
  l_pgn:=null; l_parent:=null;
  check_case('null-input',false,false,null,null);
  l_pgn:=null; l_parent:=null;
  l_pgn := l_pgn || to_clob(utl_i18n.raw_to_char(hextoraw('5b4576656e742022e2999e20636166c3a9225d20312e6534202a'), 'AL32UTF8'));
  check_case('unicode-header',true,false,null,null);
  for depth in 64..65 loop
    l_pgn:=null;
    for n in 1..depth loop l_pgn:=l_pgn||to_clob('1.e4 ('); end loop;
    l_pgn:=l_pgn||'1.d4'||rpad(')',depth,')')||' *';
    check_case('depth-'||depth,depth=64,false);
  end loop;
  dbms_lob.createtemporary(l_depth,true);
  for n in 1..128 loop dbms_lob.writeappend(l_depth,32767,rpad('a',32767,'a')); end loop;
  dbms_lob.writeappend(l_depth,128,rpad('a',128,'a'));
  l_pgn:=to_clob('1.e4 {')||l_depth||'} *';
  dbms_lob.trim(l_pgn,4194304-3);
  l_pgn:=l_pgn||'} *';
  check_case('size-4Mi',true,false);
  l_pgn:=to_clob('1.e4 {')||l_depth||'aaaa} *';
  check_case('size-over-4Mi',false,false);
  dbms_lob.freetemporary(l_depth);
  if orac_chess.chess_game_api.pgn_header(to_clob('[Event "Unicode ♞"] 1.e4 *'),'Event')<>'Unicode ♞' then
    raise_application_error(-20999,'Unicode header changed at Oracle boundary');
  end if;
  dbms_output.put_line('CHESS_PRODUCTION_MLE_CORPUS_PASSED checks='||l_count);
end;
/
rollback;
exit
