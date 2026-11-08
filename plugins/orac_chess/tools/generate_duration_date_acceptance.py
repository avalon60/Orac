"""Generate data-preserving acceptance checks from the Chess APEX source."""

# Author: Clive Bostock
# Date: 07-Nov-2026
# Description: Extract actual exported conversions into anonymous SQL assertions.
# Purpose: Verify duration and English date contracts without application data writes.
# Usage: python3 plugins/orac_chess/tools/generate_duration_date_acceptance.py --output /tmp/chess_duration_date_acceptance.sql

from __future__ import annotations

import argparse
from pathlib import Path
import re


def generate(source: Path) -> str:
    """Build SQL assertions using the canonical export's conversion expressions.

    Args:
        source: Path to the canonical Chess administration APEX export.

    Returns:
        SQLcl script containing anonymous assertions and no application data writes.
    """
    s=source.read_text(encoding="utf-8")
    block=s.split("p_process_name=>'Save video'",1)[1].split('p_process_clob_language',1)[0]
    plsql='\n'.join(re.findall(r"^'((?:[^']|'')*)'(?:,|\)\))?$",block,re.M)).replace("''", "'")
    parser=plsql[plsql.index('  function parse_duration'):plsql.index('  end parse_duration;')+len('  end parse_duration;')]
    query=re.search(r",p_plug_source=>'select video_id, platform, external_video_id, video_url, title, creator, duration_seconds, (.*?) duration_display, published_on",s).group(1).replace("''", "'")
    date_parse=re.search(r"l_published_on := (.*?);",plsql).group(1).replace(':P41_PUBLISHED_ON','p_value')
    date_format=re.search(r"to_char\(published_on,''DD-Mon-YYYY'',''NLS_DATE_LANGUAGE=English''\)",s).group(0).replace("''", "'").replace('published_on','p_date')
    checks=[]
    for value,expected in [(None,'null'),('00:01','1'),('59:59','3599'),('60:00','3600'),('1:00:00','3600'),('2777777:46:39','9999999999')]:
     lit='null' if value is None else "'"+value+"'"
     checks.append(f'  expect_duration({lit}, {expected});')
    for value in ['00:00','0:00:00','-1:00','1.5:00','1:60','1:00:60','1:60:00','1','1:2','1:02:03:04','2777777:46:40','999999999999999999999:00',' 1:00','1:00 ']:
     checks.append(f"  reject_duration('{value}');")
    out='''-- Author: Clive Bostock
    -- Date: 07-Nov-2026
    -- Purpose: Run the actual exported duration parser and date expressions without data writes.
    -- Usage: SQLcl @/tmp/chess_duration_date_acceptance.sql
    -- Generated from canonical APEX source by tools/generate_duration_date_acceptance.py.
    whenever sqlerror exit failure rollback
    set serveroutput on
    set define off
    alter session set nls_date_language=French;
    declare
    '''+parser+'''
      function display_duration(duration_seconds number) return varchar2 is
      begin return '''+query+'''; end;
      function parse_date(p_value varchar2) return date is
      begin return '''+date_parse+'''; end;
      function display_date(p_date date) return varchar2 is
      begin return '''+date_format+'''; end;
      procedure expect_duration(p_value varchar2, p_expected number) is
        l_actual number := parse_duration(p_value);
      begin
        if l_actual != p_expected or (l_actual is null and p_expected is not null)
           or (l_actual is not null and p_expected is null) then
          raise_application_error(-20999, 'Duration mismatch: ' || p_value);
        end if;
        if p_expected is not null and parse_duration(display_duration(l_actual)) != p_expected then
          raise_application_error(-20999, 'Duration round trip mismatch');
        end if;
      end;
      procedure reject_duration(p_value varchar2) is
        l_seconds number;
      begin
        begin
          l_seconds := parse_duration(p_value);
        exception when value_error then return;
        end;
        raise_application_error(-20999, 'Accepted invalid duration: ' || p_value || ' as ' || to_char(l_seconds));
      end;
      procedure reject_date(p_value varchar2) is
        l_date date;
      begin
        begin l_date := parse_date(p_value);
        exception when others then
          if sqlcode between -1899 and -1800 then return; end if;
          raise;
        end;
        raise_application_error(-20999, 'Accepted invalid date: ' || p_value || ' as ' || to_char(l_date, 'YYYY-MM-DD'));
      end;
    begin
    '''+ '\n'.join(checks)+'''
      if display_duration(1) != '00:01' or display_duration(3599) != '59:59'
         or display_duration(3600) != '1:00:00' or display_duration(null) is not null then
        raise_application_error(-20999, 'Duration display mismatch');
      end if;
      if parse_date(null) is not null or display_date(parse_date('29-Feb-2024')) != '29-Feb-2024'
         or display_date(parse_date('07-Nov-2026')) != '07-Nov-2026' then
        raise_application_error(-20999, 'English date round trip mismatch');
      end if;
      reject_date('29-Feb-2023');
      reject_date('31-Apr-2026');
      reject_date('2026-11-07');
      reject_date('7-Nov-2026');
      dbms_output.put_line('PASS: exported duration parser, formatter and English dates');
    end;
    /
    rollback;
    alter session set nls_date_language=English;
    '''
    return out


def main() -> None:
    """Write the acceptance script to the explicitly selected output path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'apex/orac_chess_admin.sql')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    arguments.output.write_text(generate(arguments.source), encoding="utf-8")


if __name__ == '__main__':
    main()
