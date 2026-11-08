-- Author: Clive Bostock
-- Date: 02-Nov-2026
-- Purpose: Verify public administration behavior with isolated, rolled-back fixtures.
-- Usage: sql -name orac_apx_pub @plugins/orac_chess/db/acceptance/verify_admin_api.sql
-- Requires explicit task-scoped approval of this saved DEV consumer connection.
-- This is a rollback acceptance harness, not a substitute for pending utPLSQL suites.
whenever sqlerror exit sql.sqlcode rollback
set define off
set serveroutput on
set feedback on
select user,sys_context('userenv','db_name') database_name,sys_context('userenv','con_name') container_name from dual;
declare
  l_opening number;
  l_child number;
  l_gambit number;
  l_concept number;
  l_video number;
  l_video_stamp timestamp with time zone;
  l_commentary number;
  l_image number;
  l_version number;
  l_old number;
  l_child_version number;
  l_count number;
  l_blob blob;
  l_fetched blob;
  l_bad blob;
  l_jpeg_id number;
  l_game number;
  l_root number;
  l_branch number;
  l_root_version number;
  l_branch_version number;
  l_saved_pgn clob;
  l_extra_id number;
  l_extra_version number;
  l_mime varchar2(255);
  l_filename varchar2(500);
  l_raw raw(32767);
  l_prefix varchar2(80) := '__ADMIN_ACCEPTANCE_'||sys_context('userenv','sessionid');
  l_checks number := 0;
  procedure assert_true(p_ok boolean,p_message varchar2) is
  begin
    if p_ok is null or not p_ok then raise_application_error(-20999,p_message); end if;
    l_checks:=l_checks+1;
  end;
  procedure expected(p_code number,p_actual number,p_message varchar2) is
  begin
    assert_true(p_code=p_actual,p_message||': expected '||p_code||', received '||p_actual);
  end;
begin
  if user not in ('ORAC_APX_PUB','SYSTEM') or sys_context('userenv','con_name')!='FREEPDB1' then
    raise_application_error(-20998,'This harness requires the verified DEV database and approved principal.');
  end if;
  savepoint chess_acceptance;
  -- The popup search examines the CLOB beyond its 1,000-character display prefix.
  select dbms_lob.instr(lower(to_clob(rpad('x',1100,'x')) || 'Schiller Defense'), lower('SCHILLER DEFENSE'))
    into l_count from dual;
  assert_true(l_count=1101,'ECO search finds case-insensitive text beyond displayed prefix');
  orac_chess.chess_admin_api.save_opening(l_opening,null,l_prefix,'OPENING',to_clob(rpad('X',30000,'X'))||rpad('Y',30000,'Y'),null,l_version);
  assert_true(l_version=1,'Insert initializes row version');
  select dbms_lob.getlength(description) into l_count from orac_chess.chess_opening_v where opening_id=l_opening;
  assert_true(l_count=60000,'Public API preserves long CLOB content');
  orac_chess.chess_admin_api.save_opening_with_eco(l_child,null,l_prefix||'_eco_new','SYSTEM',null,null,'B00:C00',l_child_version);
  select count(*) into l_count from orac_chess.chess_opening_eco_v where opening_id=l_child and eco_code in ('B00','C00');
  assert_true(l_child_version=1 and l_count=2,'New opening and ECO set saved together');
  orac_chess.chess_admin_api.save_opening_with_eco(l_child,l_child_version,l_prefix||'_eco_new','SYSTEM',null,null,null,l_child_version);
  orac_chess.chess_admin_api.delete_opening(l_child,l_child_version);
  l_child:=null;
  orac_chess.chess_admin_api.save_opening_with_eco(l_opening,l_version,l_prefix,'OPENING',null,null,'A00:A01',l_version);
  select count(*) into l_count from orac_chess.chess_opening_eco_v where opening_id=l_opening and eco_code in ('A00','A01');
  assert_true(l_count=2,'Complete ECO set saved through public API');
  orac_chess.chess_admin_api.save_opening_with_eco(l_opening,l_version,l_prefix,'OPENING',null,null,'A01:A02',l_version);
  select count(*) into l_count from orac_chess.chess_opening_eco_v where opening_id=l_opening and eco_code in ('A01','A02');
  assert_true(l_count=2,'Complete ECO set adds and retains codes');
  select count(*) into l_count from orac_chess.chess_opening_eco_v where opening_id=l_opening and eco_code='A00';
  assert_true(l_count=0,'Complete ECO set removes omitted code');
  orac_chess.chess_admin_api.save_opening_with_eco(l_opening,l_version,l_prefix,'OPENING',null,null,'A01:A02',l_version);
  select count(*) into l_count from orac_chess.chess_opening_eco_v where opening_id=l_opening;
  assert_true(l_count=2,'Unchanged ECO set does not create duplicates');
  l_old:=l_version;
  begin
    orac_chess.chess_admin_api.save_opening_with_eco(l_opening,l_version,l_prefix||'_changed','OPENING',null,null,'A01:A01',l_version);
    raise_application_error(-20999,'Duplicate ECO set accepted');
  exception when others then expected(-20009,sqlcode,'Duplicate ECO set rejected'); end;
  select row_version into l_version from orac_chess.chess_opening_v where opening_id=l_opening;
  begin
    orac_chess.chess_admin_api.save_opening_with_eco(l_opening,l_version,l_prefix||'_changed','OPENING',null,null,'A01:Z99',l_version);
    raise_application_error(-20999,'Invalid ECO set accepted');
  exception when others then expected(-20014,sqlcode,'Invalid ECO set rejected'); end;
  select count(*) into l_count from orac_chess.chess_opening_v where opening_id=l_opening and name=l_prefix and row_version=l_old;
  assert_true(l_count=1,'Invalid ECO set preserves opening and version');
  select row_version into l_version from orac_chess.chess_opening_v where opening_id=l_opening;
  begin
    orac_chess.chess_admin_api.save_opening_with_eco(l_opening,l_version-1,l_prefix||'_changed','OPENING',null,null,null,l_version);
    raise_application_error(-20999,'Stale complete ECO set accepted');
  exception when others then expected(-20001,sqlcode,'Stale complete ECO set rejected'); end;
  select count(*) into l_count from orac_chess.chess_opening_eco_v where opening_id=l_opening;
  assert_true(l_count=2,'Stale save preserves links');
  select row_version into l_version from orac_chess.chess_opening_v where opening_id=l_opening;
  orac_chess.chess_admin_api.save_opening_with_eco(l_opening,l_version,l_prefix,'OPENING',null,null,null,l_version);
  select count(*) into l_count from orac_chess.chess_opening_eco_v where opening_id=l_opening;
  assert_true(l_count=0,'Empty complete ECO set removes all links');
  l_old:=l_version;
  orac_chess.chess_admin_api.link_opening_eco(l_opening,'A00',l_version,true,l_version);
  assert_true(l_version=l_old+1,'ECO edit bumps aggregate version');
  begin
    orac_chess.chess_admin_api.link_opening_eco(l_opening,'A00',l_version,true,l_version);
    raise_application_error(-20999,'Duplicate ECO accepted');
  exception when others then expected(-20009,sqlcode,'Duplicate ECO rejected'); end;
  select row_version into l_version from orac_chess.chess_opening_v where opening_id=l_opening;
  begin
    orac_chess.chess_admin_api.save_opening(l_opening,l_old,l_prefix,'OPENING',null,null,l_version);
    raise_application_error(-20999,'Stale opening accepted');
  exception when others then expected(-20001,sqlcode,'Stale opening rejected'); end;
  select row_version into l_version from orac_chess.chess_opening_v where opening_id=l_opening;
  orac_chess.chess_admin_api.link_opening_alias(l_opening,'Alternate name',l_version,true,l_version);
  begin
    orac_chess.chess_admin_api.link_opening_alias(l_opening,'Alternate name',l_version,true,l_version);
    raise_application_error(-20999,'Exact alias duplicate accepted');
  exception when others then expected(-20009,sqlcode,'Exact alias duplicate rejected'); end;
  select row_version into l_version from orac_chess.chess_opening_v where opening_id=l_opening;
  begin
    orac_chess.chess_admin_api.link_opening_eco(l_opening,'Z99',l_version,true,l_version);
    raise_application_error(-20999,'Invalid ECO accepted');
  exception when others then expected(-20014,sqlcode,'ECO format enforced'); end;
  orac_chess.chess_admin_api.save_opening(l_child,null,l_prefix||'_child','SYSTEM',null,l_opening,l_child_version);
  begin
    orac_chess.chess_admin_api.save_opening(l_opening,l_version,l_prefix,'OPENING',null,l_child,l_version);
    raise_application_error(-20999,'Hierarchy cycle accepted');
  exception when others then expected(-20004,sqlcode,'Indirect opening cycle rejected'); end;
  select count(*) into l_count from orac_chess.chess_opening_v where opening_id in (l_opening,l_child);
  assert_true(l_count=2,'Failed operation preserves caller fixtures');
  begin
    orac_chess.chess_admin_api.save_opening(l_opening,l_version,l_prefix,'INVALID',null,null,l_version);
    raise_application_error(-20999,'Invalid opening type accepted');
  exception when others then expected(-20014,sqlcode,'Opening classification enforced'); end;
  orac_chess.chess_admin_api.save_gambit(l_gambit,null,l_prefix||'_gambit',null,l_old);
  orac_chess.chess_admin_api.link_gambit_opening(l_gambit,l_opening,l_old,true,l_old);
  select row_version into l_version from orac_chess.chess_opening_v where opening_id=l_opening;
  assert_true(l_version>l_old-1,'Link bumps subject aggregate');
  orac_chess.chess_admin_api.link_gambit_opening(l_gambit,l_opening,l_old,false,l_old);
  select count(*) into l_count from orac_chess.chess_gambit_v where gambit_id=l_gambit;
  assert_true(l_count=1,'Unlink preserves shared gambit');
  orac_chess.chess_admin_api.save_concept(l_concept,null,l_prefix,l_prefix,'TACTIC',null,l_old);
  begin
    orac_chess.chess_admin_api.save_concept(l_concept,l_old,l_prefix,l_prefix,'INVALID',null,l_version);
    raise_application_error(-20999,'Invalid concept category accepted');
  exception when others then expected(-20014,sqlcode,'Concept categories enforced'); end;
  begin
    orac_chess.chess_admin_api.save_video(l_video,null,'WEB',l_prefix,'javascript:alert(1)','Unsafe',null,null,null,null,l_version);
    raise_application_error(-20999,'Unsafe URL accepted');
  exception when others then expected(-20002,sqlcode,'Unsafe URL denied'); end;
  orac_chess.chess_admin_api.save_video(l_video,null,'WEB',l_prefix,'https://example.com/watch?v=1','Safe',null,null,60,null,l_version);
  select updated_on into l_video_stamp from orac_chess.chess_video_v where video_id=l_video;
  orac_chess.chess_admin_api.link_video_opening(l_video,l_opening,l_version,true,l_version);
  select case when updated_on!=l_video_stamp then 1 else 0 end into l_count from orac_chess.chess_video_v where video_id=l_video;
  assert_true(l_count=1,'Video association edits maintain UPDATED_ON');
  orac_chess.chess_admin_api.link_video_gambit(l_video,l_gambit,l_version,true,l_version);
  select (select count(*) from orac_chess.chess_video_opening_v where video_id=l_video)
       + (select count(*) from orac_chess.chess_video_gambit_v where video_id=l_video) into l_count from dual;
  assert_true(l_count=2,'Video can link simultaneous subjects');
  orac_chess.chess_admin_api.link_video_opening(l_video,l_opening,l_version,false,l_version);
  select count(*) into l_count from orac_chess.chess_video_gambit_v where video_id=l_video and gambit_id=l_gambit;
  assert_true(l_count=1,'Video supports multiple subject types');
  select count(*) into l_count from orac_chess.chess_video_v where video_id=l_video;
  assert_true(l_count=1,'Unlink preserves shared video');
  orac_chess.chess_admin_api.save_commentary(l_commentary,null,l_opening,null,null,'HISTORY','Title',to_clob('Content'),l_version);
  begin
    orac_chess.chess_admin_api.save_commentary(l_commentary,l_version,l_opening,l_gambit,null,'HISTORY','Title',to_clob('Content'),l_version);
    raise_application_error(-20999,'Multiple commentary subjects accepted');
  exception when others then expected(-20014,sqlcode,'Exactly one commentary subject enforced'); end;
  for r in (select column_value category from table(sys.odcivarchar2list('TACTIC','STRATEGY','STRUCTURE','MATE_PATTERN','OTHER'))) loop
    l_extra_id:=null;
    orac_chess.chess_admin_api.save_concept(l_extra_id,null,l_prefix||r.category,l_prefix||r.category,r.category,null,l_extra_version);
    assert_true(l_extra_id is not null,'Allowed concept category '||r.category);
  end loop;
  for r in (select column_value kind from table(sys.odcivarchar2list('HISTORY','STRATEGY','PRACTITIONER','MISTAKE','FACT','INSTRUCTION'))) loop
    l_extra_id:=null;
    orac_chess.chess_admin_api.save_commentary(l_extra_id,null,l_opening,null,null,r.kind,r.kind,to_clob('Test content'),l_extra_version);
    assert_true(l_extra_id is not null,'Allowed commentary kind '||r.kind);
  end loop;
  l_extra_id:=null;
  begin
    orac_chess.chess_admin_api.save_commentary(l_extra_id,null,-999999999,null,null,'FACT','Invalid subject',to_clob('Text'),l_extra_version);
    raise_application_error(-20999,'Unknown subject identity accepted');
  exception when others then expected(-20013,sqlcode,'Foreign-key identity rejected'); end;
  begin
    orac_chess.chess_admin_api.save_commentary(l_extra_id,null,l_opening,null,null,'FACT','Required content',null,l_extra_version);
    raise_application_error(-20999,'Missing required content accepted');
  exception when others then expected(-20015,sqlcode,'Required content error is meaningful'); end;
  begin
    orac_chess.chess_admin_api.delete_gambit(-999999999,1);
    raise_application_error(-20999,'Unknown record delete accepted');
  exception when others then expected(-20008,sqlcode,'Unknown record identity rejected'); end;
  -- Minimal deterministic 1x1 RGBA PNG, including full chunk CRCs.
  l_raw:=hextoraw('89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000D49444154789C63606060F80F00010401005FE5C34B0000000049454E44AE426082');
  dbms_lob.createtemporary(l_blob,true);
  dbms_lob.writeappend(l_blob,utl_raw.length(l_raw),l_raw);
  orac_chess.chess_image_api.save_image(l_image,null,'pixel.png','image/png','Description','A single test pixel',l_blob,l_version);
  l_old:=l_version;
  orac_chess.chess_image_api.save_image(l_image,l_version,'renamed.png','image/jpeg','Metadata only','A single test pixel',null,l_version);
  orac_chess.chess_image_api.fetch_content(l_image,l_fetched,l_mime,l_filename);
  assert_true(dbms_lob.compare(l_blob,l_fetched)=0 and l_mime='image/png' and l_filename='renamed.png','Metadata-only save retains bytes and MIME');
  begin
    orac_chess.chess_image_api.save_image(l_image,l_version,'pixel.png','image/png',null,null,l_blob,l_version);
    raise_application_error(-20999,'Missing alt accepted');
  exception when others then expected(-20005,sqlcode,'Required alt text enforced'); end;
  begin
    orac_chess.chess_image_api.save_image(l_image,l_version,'pixel.jpg','image/jpeg',null,'Pixel',l_blob,l_version);
    raise_application_error(-20999,'MIME spoof accepted');
  exception when others then expected(-20007,sqlcode,'MIME and content consistency enforced'); end;
  dbms_lob.createtemporary(l_bad,true);
  dbms_lob.copy(l_bad,l_blob,dbms_lob.getlength(l_blob));
  dbms_lob.write(l_bad,1,dbms_lob.getlength(l_bad),hextoraw('00'));
  begin
    orac_chess.chess_image_api.save_image(l_image,l_version,'bad.png','image/png',null,'Pixel',l_bad,l_version);
    raise_application_error(-20999,'Bad PNG checksum accepted');
  exception when others then expected(-20007,sqlcode,'PNG CRC and actual structure enforced'); end;
  dbms_lob.freetemporary(l_bad);
  orac_chess.chess_image_api.fetch_content(l_image,l_fetched,l_mime,l_filename);
  assert_true(dbms_lob.compare(l_blob,l_fetched)=0,'Failed image replacement preserves existing bytes');

  orac_chess.chess_admin_api.link_image_opening(l_image,l_opening,l_version,true,l_version);
  orac_chess.chess_image_api.delete_image(l_image,l_version);
  select count(*) into l_count from orac_chess.chess_image_opening_v where image_id=l_image;
  assert_true(l_count=0,'Controlled image deletion removes associations atomically');
  -- Deterministic 1x1 RGB JPEG encoded once with Pillow; no runtime Pillow dependency.
  dbms_lob.createtemporary(l_bad,true);
  l_raw:=hextoraw('FFD8FFE000104A46494600010100000100010000FFDB00430006040506050406060506070706080A100A0A09090A140E0F0C1017141818171416161A1D251F1A1B231C1616202C20232627292A29191F2D302D283025282928FFDB0043010707070A080A130A0A13281A161A2828282828282828282828282828282828282828282828282828282828282828282828282828282828282828282828282828FFC00011080001000103012200021101031101FFC4001F0000010501010101010100000000000000000102030405060708090A0BFFC400B5100002010303020403050504040000017D01020300041105122131410613516107227114328191A1082342B1C11552D1F02433627282090A161718191A25262728292A3435363738393A434445464748494A535455565758595A636465666768696A737475767778797A838485868788898A92939495969798999AA2A3A4A5A6A7A8A9AAB2B3B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE1E2E3E4E5E6E7E8E9EAF1F2F3F4F5F6F7F8F9FAFFC4001F0100030101010101010101010000000000000102030405060708090A0BFFC400B51100020102040403040705040400010277000102031104052131061241510761711322328108144291A1B1C109233352F0156272D10A162434E125F11718191A262728292A35363738393A434445464748494A535455565758595A636465666768696A737475767778797A82838485868788898A92939495969798999AA2A3A4A5A6A7A8A9AAB2B3B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE2E3E4E5E6E7E8E9EAF2F3F4F5F6F7F8F9FAFFDA000C03010002110311003F00CFA28A2BEC4F953FFFD9');
  dbms_lob.writeappend(l_bad,utl_raw.length(l_raw),l_raw);
  orac_chess.chess_image_api.save_image(l_jpeg_id,null,'pixel.jpg','image/jpeg',null,'A JPEG pixel',l_bad,l_old);
  orac_chess.chess_image_api.fetch_content(l_jpeg_id,l_fetched,l_mime,l_filename);
  assert_true(l_mime='image/jpeg' and dbms_lob.compare(l_bad,l_fetched)=0,'Valid JPEG structure and bytes accepted');
  orac_chess.chess_image_api.delete_image(l_jpeg_id,l_old);
  dbms_lob.freetemporary(l_bad);
  dbms_lob.createtemporary(l_bad,true);
  l_raw:=hextoraw('FFD8FFE000104A46494600010100000100010000FFDB00430006040506050406060506070706080A100A0A09090A140E0F0C1017141818171416161A1D251F1A1B231C1616202C20232627292A29191F2D302D283025282928FFDB0043010707070A080A130A0A13281A161A2828282828282828282828282828282828282828282828282828282828282828282828282828282828282828282828282828FFC20011080001000103012200021101031101FFC4001500010100000000000000000000000000000004FFC40014010100000000000000000000000000000005FFDA000C030100021003100000019C3057FFC40014100100000000000000000000000000000000FFDA00080101000105027FFFC40014110100000000000000000000000000000000FFDA0008010301013F017FFFC40014110100000000000000000000000000000000FFDA0008010201013F017FFFC40014100100000000000000000000000000000000FFDA0008010100063F027FFFC40014100100000000000000000000000000000000FFDA0008010100013F217FFFDA000C030100020003000000100BFFC40014110100000000000000000000000000000000FFDA0008010301013F107FFFC40014110100000000000000000000000000000000FFDA0008010201013F107FFFC40014100100000000000000000000000000000000FFDA0008010100013F107FFFD9');
  dbms_lob.writeappend(l_bad,utl_raw.length(l_raw),l_raw);
  l_jpeg_id:=null;
  orac_chess.chess_image_api.save_image(l_jpeg_id,null,'progressive.jpg','image/jpeg',null,'Progressive JPEG pixel',l_bad,l_old);
  assert_true(l_jpeg_id is not null,'Valid progressive JPEG structure accepted');
  orac_chess.chess_image_api.delete_image(l_jpeg_id,l_old);
  dbms_lob.freetemporary(l_bad);
  dbms_lob.createtemporary(l_bad,true);
  -- Fake SOI/SOF/SOS/EOI with entropy byte but no required DQT/DHT tables.
  l_raw:=hextoraw('FFD8FFC0000B080001000101011100FFDA0008010100003F0000FFD9');
  dbms_lob.writeappend(l_bad,utl_raw.length(l_raw),l_raw);
  l_jpeg_id:=null;
  begin
    orac_chess.chess_image_api.save_image(l_jpeg_id,null,'fake.jpg','image/jpeg',null,'Invalid JPEG',l_bad,l_old);
    raise_application_error(-20999,'JPEG missing coding tables accepted');
  exception when others then expected(-20007,sqlcode,'JPEG requires actual coding tables'); end;
  dbms_lob.freetemporary(l_bad);
  select row_version into l_version from orac_chess.chess_opening_v where opening_id=l_opening;
  begin
    orac_chess.chess_admin_api.delete_opening(l_opening,l_version);
    raise_application_error(-20999,'Referenced opening deleted');
  exception when others then expected(-20010,sqlcode,'Restrictive delete enforced'); end;
  -- Exercise authoritative legal-move validation through the consumer API.
  orac_chess.chess_game_api.save_game(l_game,null,'Manual white','Manual black','Manual event',null,null,'*',null,null,to_clob('[White "Header white"] 1.e4 {Unicode: ♞} e5 (1...c5) *'),null,null,l_version);
  assert_true(l_version=1,'Legal game PGN insert accepted');
  select pgn into l_saved_pgn from orac_chess.chess_game_v where game_id=l_game;
  assert_true(orac_chess.chess_game_api.pgn_header(l_saved_pgn,'White')='Header white','Validated header extraction');
  select count(*) into l_count from orac_chess.chess_game_v where game_id=l_game and white_player='Manual white' and event_name='Manual event';
  assert_true(l_count=1,'Header extraction does not overwrite searchable metadata');
  begin
    orac_chess.chess_game_api.save_game(l_game,0,'Changed','Black',null,null,null,'*',null,null,to_clob('1.d4 *'),null,null,l_old);
    raise_application_error(-20999,'Stale PGN save accepted');
  exception when others then expected(-20001,sqlcode,'Stale game version rejected'); end;
  begin
    orac_chess.chess_game_api.save_game(l_game,l_version,'Changed','Black',null,null,null,'*',null,null,to_clob('1.e5 *'),null,null,l_old);
    raise_application_error(-20999,'Illegal move accepted');
  exception when others then expected(-20021,sqlcode,'Illegal SAN rejected'); end;
  select pgn into l_saved_pgn from orac_chess.chess_game_v where game_id=l_game;
  assert_true(orac_chess.chess_game_api.pgn_header(l_saved_pgn,'White')='Header white','Invalid save preserves game');
  orac_chess.chess_game_api.delete_game(l_game,l_version);

  select row_version into l_root_version from orac_chess.chess_opening_v where opening_id=l_opening;
  orac_chess.chess_variation_api.save_variation(l_root,null,l_opening,null,null,null,l_prefix||' root','MAIN',to_clob('1.e4 e5 2.Nf3 *'),null,null,l_root_version);
  orac_chess.chess_variation_api.save_variation(l_branch,null,l_opening,null,l_root,1,l_prefix||' branch','ALTERNATIVE',to_clob('1.e4 c5 2.Nf3 *'),null,null,l_branch_version);
  begin
    orac_chess.chess_variation_api.save_variation(l_root,l_root_version,l_opening,null,null,null,l_prefix||' root','MAIN',to_clob('1.d4 d5 2.Nf3 *'),null,null,l_old);
    raise_application_error(-20999,'Parent mutation invalidating branch accepted');
  exception when others then expected(-20025,sqlcode,'Whole subtree validation rejects changed prefix'); end;
  select pgn,row_version into l_saved_pgn,l_old from orac_chess.chess_variation_v where variation_id=l_root;
  assert_true(dbms_lob.compare(l_saved_pgn,to_clob('1.e4 e5 2.Nf3 *'))=0 and l_old=l_root_version,'Failed subtree mutation rolls back PGN and version');
  begin
    orac_chess.chess_variation_api.save_variation(l_root,l_root_version,l_opening,null,l_branch,1,l_prefix||' root','ALTERNATIVE',to_clob('1.e4 e5 2.Nf3 *'),null,null,l_old);
    raise_application_error(-20999,'Indirect variation cycle accepted');
  exception when others then expected(-20024,sqlcode,'Indirect variation cycle rejected'); end;
  begin
    orac_chess.chess_variation_api.delete_variation(l_root,l_root_version);
    raise_application_error(-20999,'Referenced variation deleted');
  exception when others then expected(-20010,sqlcode,'Variation delete is restrictive'); end;
  orac_chess.chess_variation_api.delete_variation(l_branch,l_branch_version);
  orac_chess.chess_variation_api.delete_variation(l_root,l_root_version);
  if user='ORAC_APX_PUB' then
    begin
      execute immediate 'select count(*) from orac_chess.chess_opening' into l_count;
      raise_application_error(-20999,'Base table SELECT granted');
    exception when others then expected(-942,sqlcode,'Base table read denied'); end;
    begin
      execute immediate 'update orac_chess.chess_opening set name=name where 1=0';
      raise_application_error(-20999,'Base DML granted');
    exception when others then expected(-942,sqlcode,'Base table DML denied'); end;
    begin
      execute immediate 'begin orac_chess.chess_validation_api.lock_control; end;';
      raise_application_error(-20999,'Private API granted');
    exception when others then assert_true(sqlcode in (-6550,-1031),'Private validation API denied'); end;
    begin
      execute immediate 'begin :result := orac_chess.chess_mle_validate(to_clob(''1.e4 *''),0,null); end;' using out l_filename;
      raise_application_error(-20999,'Private MLE call granted');
    exception when others then assert_true(sqlcode in (-6550,-1031),'Private MLE call denied'); end;
    begin
      execute immediate 'begin orac_chess.chess_admin_tapi.delete_opening(-1,1); end;';
      raise_application_error(-20999,'Private TAPI granted');
    exception when others then assert_true(sqlcode in (-6550,-1031),'Private TAPI denied'); end;
  end if;
  select count(*) into l_count from all_tab_privs where table_schema='ORAC_CHESS' and grantee='PUBLIC' and privilege!='INHERIT PRIVILEGES';
  assert_true(l_count=0,'No PUBLIC object grants');
  assert_true(orac_code.plugin_apex_app_auth_api.has_required_role('ORAC_ADMIN','__CHESS_NO_SUCH_ACCOUNT__')=0,'Unassigned role denied');

  dbms_lob.freetemporary(l_blob);
  rollback to chess_acceptance;
  dbms_output.put_line('CHESS_ADMIN_ACCEPTANCE_PASSED checks='||l_checks||' principal='||user);
exception when others then
  rollback;
  raise;
end;
/
rollback;
exit
