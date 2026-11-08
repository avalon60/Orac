-- Author: Clive Bostock
-- Date: 01-Nov-2026
-- Purpose: Verify fresh-baseline ownership, uniqueness, ECO and inbound reference behaviour.
-- Usage: In an explicitly authorised disposable FREEPDB1 owner-capable SQLcl session, run @plugins/orac_chess/db/acceptance/verify_constraints.sql
set serveroutput on
whenever sqlerror exit failure rollback

declare
  l_opn1 number;
  l_opn2 number;
  l_gmb1 number;
  l_gmb2 number;
  l_root1 number;
  l_root2 number;
  l_groot1 number;
  l_groot2 number;
  l_child number;
  l_other number;
  l_concept number;
  l_image number;
  l_video number;
  l_count number;
  l_type varchar2(1 char);
  l_opening_type varchar2(20 char);
  l_tag varchar2(32) := rawtohex(sys_guid());

  procedure expect_error(p_sql varchar2, p_code number) is
  begin
    execute immediate p_sql;
    raise_application_error(-20082, 'Expected Oracle error ' || p_code || ': ' || p_sql);
  exception when others then
    if sqlcode <> p_code then raise; end if;
  end;

  function add_line(p_opening number, p_gambit number, p_name varchar2,
                    p_parent number default null) return number is
    l_id number;
  begin
    insert into orac_chess.chess_variation
      (opening_id, gambit_id, name, parent_variation_id, branch_ply, line_kind, pgn)
    values (p_opening, p_gambit, p_name, p_parent,
      case when p_parent is not null then 1 end,
      case when p_parent is null then 'MAIN' else 'ALTERNATIVE' end,
      case when p_parent is null then '1. e4 e5 *' else '1. e4 c5 *' end)
    returning variation_id into l_id;
    return l_id;
  end;
begin
  savepoint chess_constraint_test;
  if sys_context('userenv','con_name') <> 'FREEPDB1' then
    raise_application_error(-20082, 'Verify the target PDB before testing ORAC_CHESS.');
  end if;
  insert into orac_chess.chess_opening(name) values ('Acceptance A ' || l_tag)
    returning opening_id into l_opn1;
  select opening_type into l_opening_type from orac_chess.chess_opening where opening_id=l_opn1;
  if l_opening_type <> 'OPENING' then raise_application_error(-20082, 'Opening default mismatch'); end if;
  insert into orac_chess.chess_opening(name, opening_type) values ('Acceptance B ' || l_tag, 'SYSTEM')
    returning opening_id into l_opn2;
  select opening_type into l_opening_type from orac_chess.chess_opening where opening_id=l_opn2;
  if l_opening_type <> 'SYSTEM' then raise_application_error(-20082, 'System classification rejected'); end if;
  expect_error('insert into orac_chess.chess_opening(name,opening_type) values (''Invalid ' || l_tag || ''',''OTHER'')', -2290);
  expect_error('insert into orac_chess.chess_opening(name,opening_type) values (''Lowercase ' || l_tag || ''',''opening'')', -2290);
  expect_error('insert into orac_chess.chess_opening(name,opening_type) values (''Null ' || l_tag || ''',null)', -1400);
  expect_error('insert into orac_chess.chess_opening(name,opening_type) values (''Empty ' || l_tag || ''','''')', -1400);
  expect_error('update orac_chess.chess_opening set opening_type=''system'' where opening_id=' || l_opn1, -2290);
  expect_error('update orac_chess.chess_opening set opening_type=''OTHER'' where opening_id=' || l_opn1, -2290);
  expect_error('update orac_chess.chess_opening set opening_type=null where opening_id=' || l_opn1, -1407);
  expect_error('update orac_chess.chess_opening set opening_type='''' where opening_id=' || l_opn1, -1407);
  insert into orac_chess.chess_gambit(name) values ('Acceptance A ' || l_tag)
    returning gambit_id into l_gmb1;
  insert into orac_chess.chess_gambit(name) values ('Acceptance B ' || l_tag)
    returning gambit_id into l_gmb2;

  -- Same name under different owners of either type, and across types, succeeds.
  l_root1 := add_line(l_opn1, null, 'Shared');
  l_root2 := add_line(l_opn2, null, 'Shared');
  l_groot1 := add_line(null, l_gmb1, 'Shared');
  l_groot2 := add_line(null, l_gmb2, 'Shared');
  select variation_type into l_type from orac_chess.chess_variation where variation_id=l_root1;
  if l_type <> 'O' then raise_application_error(-20082, 'Opening type mismatch'); end if;
  select variation_type into l_type from orac_chess.chess_variation where variation_id=l_groot1;
  if l_type <> 'G' then raise_application_error(-20082, 'Gambit type mismatch'); end if;
  expect_error('update orac_chess.chess_variation set variation_type=''G'' where variation_id=' || l_root1, -54017);

  -- Use children so root uniqueness cannot mask subject-name uniqueness.
  l_child := add_line(l_opn1, null, 'Alternative', l_root1);
  l_other := add_line(null, l_gmb1, 'Alternative', l_groot1);
  expect_error('insert into orac_chess.chess_variation(opening_id,name,parent_variation_id,branch_ply,line_kind,pgn) values (' || l_opn1 || ',''Alternative'',' || l_root1 || ',1,''ALTERNATIVE'',''1.e4 c5 *'')', -1);
  expect_error('insert into orac_chess.chess_variation(gambit_id,name,parent_variation_id,branch_ply,line_kind,pgn) values (' || l_gmb1 || ',''Alternative'',' || l_groot1 || ',1,''ALTERNATIVE'',''1.e4 c5 *'')', -1);
  expect_error('insert into orac_chess.chess_variation(name,line_kind,pgn) values (''No owner'',''MAIN'',''*'')', -2290);
  -- A child shape avoids an existing-root index masking the ownership check.
  expect_error('insert into orac_chess.chess_variation(opening_id,gambit_id,name,parent_variation_id,branch_ply,line_kind,pgn) values (' || l_opn1 || ',' || l_gmb1 || ',''Two owners'',' || l_root1 || ',1,''ALTERNATIVE'',''1.e4 c5 *'')', -2290);
  expect_error('insert into orac_chess.chess_variation(opening_id,name,line_kind,pgn) values (' || l_opn1 || ',''Second root'',''MAIN'',''*'')', -1);
  expect_error('insert into orac_chess.chess_variation(gambit_id,name,line_kind,pgn) values (' || l_gmb1 || ',''Second root'',''MAIN'',''*'')', -1);
  expect_error('update orac_chess.chess_variation set parent_variation_id=' || l_root2 || ' where variation_id=' || l_child, -2291);
  expect_error('update orac_chess.chess_variation set parent_variation_id=' || l_groot2 || ' where variation_id=' || l_other, -2291);
  expect_error('update orac_chess.chess_variation set parent_variation_id=' || l_child || ' where variation_id=' || l_child, -2290);
  expect_error('update orac_chess.chess_opening set parent_opening_id=opening_id where opening_id=' || l_opn1, -2290);

  expect_error('update orac_chess.chess_variation set branch_ply=-1 where variation_id=' || l_child, -2290);
  expect_error('update orac_chess.chess_variation set branch_ply=null where variation_id=' || l_child, -2290);
  expect_error('update orac_chess.chess_variation set branch_ply=1 where variation_id=' || l_root1, -2290);
  expect_error('update orac_chess.chess_variation set starting_fen=''invalid'' where variation_id=' || l_child, -2290);
  expect_error('update orac_chess.chess_variation set parent_variation_id=' || l_groot1 || ' where variation_id=' || l_child, -2291);

  -- Zero shared plies is a valid relational branch before the first move.
  update orac_chess.chess_variation set branch_ply=0, pgn='1. d4 d5 *'
    where variation_id=l_child;
  select count(*) into l_count from orac_chess.chess_variation
    where variation_id=l_child and branch_ply=0;
  if l_count <> 1 then raise_application_error(-20082, 'Zero-ply branch rejected'); end if;
  expect_error('update orac_chess.chess_variation set line_kind=''ALTERNATIVE'' where variation_id=' || l_root1, -2290);
  expect_error('update orac_chess.chess_variation set line_kind=''MAIN'' where variation_id=' || l_child, -2290);
  -- Storage accepts a root FEN; legal-position/header validation is deferred.
  update orac_chess.chess_variation
    set starting_fen='rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1',
      pgn='[SetUp "1"]' || chr(10) ||
        '[FEN "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"]' ||
        chr(10) || chr(10) || '1... e5 *'
    where variation_id=l_root2;
  select count(*) into l_count from orac_chess.chess_variation
    where variation_id=l_root2 and starting_fen is not null;
  if l_count <> 1 then raise_application_error(-20082, 'Root FEN rejected'); end if;

  insert into orac_chess.chess_opening_eco values (l_opn1, 'A00');
  insert into orac_chess.chess_opening_eco values (l_opn1, 'E99');
  insert into orac_chess.chess_opening_eco values (l_opn2, 'A00');
  expect_error('insert into orac_chess.chess_opening_eco values (' || l_opn1 || ',''A00'')', -1);
  expect_error('insert into orac_chess.chess_opening_eco values (' || l_opn1 || ',''F00'')', -2290);
  expect_error('insert into orac_chess.chess_opening_eco values (' || l_opn1 || ',''a00'')', -2290);
  expect_error('insert into orac_chess.chess_opening_eco values (' || l_opn1 || ',null)', -1400);
  select nvl(min(opening_id), 0)-1 into l_count from orac_chess.chess_opening;
  expect_error('insert into orac_chess.chess_opening_eco values (' || l_count || ',''A00'')', -2291);
  select count(*) into l_count from orac_chess.chess_opening_eco where opening_id in (l_opn1,l_opn2);
  if l_count <> 3 then raise_application_error(-20082, 'ECO mapping cardinality mismatch'); end if;

  select nvl(min(opening_id), 0)-1 into l_count from orac_chess.chess_opening;
  expect_error('insert into orac_chess.chess_opening_gambit values (' || l_count || ',' || l_gmb1 || ')', -2291);
  insert into orac_chess.chess_opening_gambit values (l_opn1,l_gmb1);
  expect_error('insert into orac_chess.chess_opening_gambit values (' || l_opn1 || ',' || l_gmb1 || ')', -1);
  insert into orac_chess.chess_commentary(variation_id,commentary_kind,title,content)
    values (l_child,'INSTRUCTION','Acceptance','Example');
  insert into orac_chess.chess_concept(concept_code,name,category_code)
    values (l_tag,'Acceptance','TACTIC') returning concept_id into l_concept;
  insert into orac_chess.chess_concept_variation values (l_concept,l_child);
  insert into orac_chess.chess_image(image_content,filename,mime_type)
    values (empty_blob(),'acceptance.png','image/png') returning image_id into l_image;
  insert into orac_chess.chess_image_variation values (l_image,l_child);
  insert into orac_chess.chess_video(platform,external_video_id,video_url,title)
    values ('acceptance',l_tag,'https://example.invalid','Acceptance') returning video_id into l_video;
  insert into orac_chess.chess_video_variation values (l_video,l_child);

  -- Classification changes preserve identity and every kind of opening link.
  insert into orac_chess.chess_opening_alias(opening_id,alias_name) values (l_opn1,'Alias ' || l_tag);
  insert into orac_chess.chess_video_opening values (l_video,l_opn1);
  insert into orac_chess.chess_concept_opening values (l_concept,l_opn1);
  insert into orac_chess.chess_image_opening values (l_image,l_opn1);
  insert into orac_chess.chess_commentary(opening_id,commentary_kind,title,content)
    values (l_opn1,'INSTRUCTION','Opening acceptance','Example');
  insert into orac_chess.chess_game(white_player,black_player,result_code,opening_id,pgn)
    values ('Acceptance White','Acceptance Black','*',l_opn1,'1. e4 e5 *');
  update orac_chess.chess_opening set parent_opening_id=l_opn1 where opening_id=l_opn2;
  for classification in (
    select 'SYSTEM' as opening_type from dual union all select 'OPENING' from dual
  ) loop
    update orac_chess.chess_opening set opening_type=classification.opening_type where opening_id=l_opn1;
    select count(*) into l_count from orac_chess.chess_opening o
    where o.opening_id=l_opn1 and o.opening_type=classification.opening_type
      and exists (select 1 from orac_chess.chess_opening where parent_opening_id=o.opening_id)
      and exists (select 1 from orac_chess.chess_opening_alias where opening_id=o.opening_id)
      and exists (select 1 from orac_chess.chess_opening_eco where opening_id=o.opening_id)
      and exists (select 1 from orac_chess.chess_opening_gambit where opening_id=o.opening_id)
      and exists (select 1 from orac_chess.chess_variation where variation_id=l_root1 and opening_id=o.opening_id and variation_type='O')
      and exists (select 1 from orac_chess.chess_video_opening where opening_id=o.opening_id)
      and exists (select 1 from orac_chess.chess_concept_opening where opening_id=o.opening_id)
      and exists (select 1 from orac_chess.chess_image_opening where opening_id=o.opening_id)
      and exists (select 1 from orac_chess.chess_commentary where opening_id=o.opening_id)
      and exists (select 1 from orac_chess.chess_game where opening_id=o.opening_id);
    if l_count <> 1 then raise_application_error(-20082, 'Reclassification lost opening relationships'); end if;
  end loop;
  update orac_chess.chess_opening set opening_type='OPENING' where opening_id=l_opn2;
  select count(*) into l_count from orac_chess.chess_variation
    where variation_id=l_root2 and opening_id=l_opn2 and variation_type='O';
  if l_count <> 1 then raise_application_error(-20082, 'System reclassification lost variation'); end if;
  -- Each inbound reference independently restricts deletion.
  expect_error('delete from orac_chess.chess_variation where variation_id=' || l_child, -2292);
  delete from orac_chess.chess_commentary where variation_id=l_child;
  expect_error('delete from orac_chess.chess_variation where variation_id=' || l_child, -2292);
  delete from orac_chess.chess_concept_variation where variation_id=l_child;
  expect_error('delete from orac_chess.chess_variation where variation_id=' || l_child, -2292);
  delete from orac_chess.chess_image_variation where variation_id=l_child;
  expect_error('delete from orac_chess.chess_variation where variation_id=' || l_child, -2292);
  delete from orac_chess.chess_video_variation where variation_id=l_child;
  delete from orac_chess.chess_variation where variation_id=l_child;

  -- Longer cycles remain a documented application responsibility. Verify that
  -- the read-only traversal detects a rootless cycle rather than claiming rejection.
  savepoint hierarchy_fixture;
  update orac_chess.chess_opening set parent_opening_id=l_opn2 where opening_id=l_opn1;
  update orac_chess.chess_opening set parent_opening_id=l_opn1 where opening_id=l_opn2;
  select count(*) into l_count from (
    select connect_by_iscycle as is_cycle from orac_chess.chess_opening
    start with opening_id=l_opn1
    connect by nocycle prior parent_opening_id=opening_id
  ) where is_cycle=1;
  if l_count = 0 then raise_application_error(-20082, 'Opening cycle diagnostic failed'); end if;
  l_child := add_line(l_opn1, null, 'Cycle child', l_root1);
  update orac_chess.chess_variation set parent_variation_id=l_child, branch_ply=1,
    line_kind='ALTERNATIVE' where variation_id=l_root1;
  select count(*) into l_count from (
    select connect_by_iscycle as is_cycle from orac_chess.chess_variation
    start with variation_id=l_root1
    connect by nocycle prior parent_variation_id=variation_id
  ) where is_cycle=1;
  if l_count = 0 then raise_application_error(-20082, 'Variation cycle diagnostic failed'); end if;
  select count(*) into l_count from (
    select parent_variation_id from orac_chess.chess_variation
    start with variation_id=l_root1
    connect by nocycle prior parent_variation_id=variation_id
  ) where parent_variation_id is null;
  if l_count <> 0 then raise_application_error(-20082, 'Rootless fixture unexpectedly reaches a root'); end if;
  rollback to hierarchy_fixture;
  rollback to chess_constraint_test;
  dbms_output.put_line('ORAC_CHESS semantic checks passed; temporary rows rolled back');
exception when others then
  rollback to chess_constraint_test;
  raise;
end;
/
