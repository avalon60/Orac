"""Generate deterministic Liquibase Java source assets from pinned local sources."""
# Author: Clive Bostock
# Date: 02-Nov-2026
# Description: Generate source-only Oracle JVM installation assets.
# Purpose: Package pinned chess validation sources without JAR loading or JVM grants.
# Usage: python3 plugins/orac_chess/tools/generate_java_sources.py --check

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


def generate(root: Path) -> dict[Path, str]:
    """Build deterministic source and compilation assets.

    Args:
        root: Plugin source directory.

    Returns:
        Generated file paths mapped to their complete contents.
    """
    for line in (root / 'vendor/SHA256SUMS').read_text().splitlines():
        expected, relative = line.split('  ', 1)
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Vendor checksum mismatch: {relative}')
    files = sorted((root / 'vendor').glob('*/src/**/*.java'))
    files += [root / 'java/OracChessValidator.java']
    output: dict[Path, str] = {}
    includes: list[str] = []
    names: list[tuple[str, str]] = []
    header = '''--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Generated pinned Java source; edit upstream or adapter source.
-- Purpose: Source-only Oracle JVM chess validation with no external permissions.
-- Usage: Managed plugin Liquibase controller; regenerate using tools/generate_java_sources.py.
'''
    for index, path in enumerate(files, 1):
        text = "\n".join(line for line in path.read_text().splitlines() if line.strip())
        match = re.search(r'^package\s+([\w.]+)\s*;', text, re.MULTILINE)
        name = (match[1].replace('.', '/') + '/' if match else '') + path.stem
        key = f'{index:03d}_{path.stem}'
        names.append((key, name))
        relative = f'java_source/{key}.sql'
        statement = f'create or replace java source named "{name}" as\n{text.rstrip()}'
        chunks = [statement[i:i + 4000] for i in range(0, len(statement), 4000)]
        assignments = ''.join("  l_source := l_source || to_clob('" + chunk.replace("'", "''") + "');\n" for chunk in chunks)
        output[root / 'db/diagnostics' / relative] = header + f'''
--changeset clive:orac_chess_java_{key} context:plugin,prod labels:plugin runOnChange:true stripComments:false endDelimiter:/
declare
  l_source clob;
begin
{assignments}  execute immediate l_source;
end;
/
--rollback drop java source "{name}";
'''
        includes.append(relative)
    compile_sql = header
    for key, name in names:
        compile_sql += f'''
--changeset clive:orac_chess_java_compile_{key} context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "{name}" compile;
'''
    output[root / 'db/diagnostics/java_source/chess_java_compile.sql'] = compile_sql
    includes.append('java_source/chess_java_compile.sql')
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog xmlns="http://www.liquibase.org/xml/ns/dbchangelog" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog https://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.30.xsd">
'''
    xml += '  <changeSet id="orac_chess_java_sqlcl_settings" author="clive" runAlways="true" runOnChange="true"><sql splitStatements="false">set define off\nset scan off\nset sqlblanklines on</sql></changeSet>\n'
    xml += ''.join(f'  <include file="{p}" relativeToChangelogFile="true"/>\n' for p in includes)
    output[root / 'db/diagnostics/javaController.xml'] = xml + '</databaseChangeLog>\n'
    return output


def main() -> None:
    """Write assets, or exit nonzero when checked assets have drifted."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check generated files without changing them.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = generate(root)
    for path, text in output.items():
        if args.check:
            if not path.exists() or path.read_text() != text:
                raise SystemExit(f'Generated Java asset differs: {path}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    print(f'{len(output)} Java installation assets verified' if args.check else f'{len(output)} Java installation assets generated')


if __name__ == '__main__':
    main()
