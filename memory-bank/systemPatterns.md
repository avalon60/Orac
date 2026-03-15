### Global conventions

* **Language:** British English.
* **Indentation:** 2 spaces (no tabs).
* **SQL/PLSQL keywords:** lower‑case.
* **DDL:** Separate `alter table ... add constraint ... primary key` statements (no inline PKEYs). Identity columns for surrogate keys.
* **Dates & IDs:** `created_by/created_on/updated_by/updated_on/row_version` are automaintained.

### Python module template

```python
#!/usr/bin/env python3
"""
#!/usr/bin/env python3
"""
<module summary line>.

More detailed description of what the module does, how it fits into Orac, etc.

Attributes:
    __author__ (str): Module author.
    __date__ (str): Date of creation.
    __description__ (str): One-line description of purpose.
"""

__author__ = "Clive Bostock"
__date__ = "2025-10-03"
__description__ = "<what this script does>"

import argparse


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__description__)
    # add options here
    return parser.parse_args()


def main() -> None:
    """Main entry point for the script."""
    args = parse_args()
    # do stuff with args


if __name__ == "__main__":
    main()
```

### PL/SQL patterns

* `if` / `then` style: `then` on next line aligned with `if`.
* `exception` blocks: keep `then` on same line as `when`.
* Always prefer `dbms_sql` for dynamic binds in `dqu_suite`; resolve `:binds` from `dqu_core.dqu_runtime_binds` with proper typing.
* **logger** calls wrap entry, each parameter, and error cases.

**Skeleton**

```sql
create or replace package body dqu_code.dqu_suite as
  procedure exec_cardinality_test(p_test_id in number) is
  begin
    logger.log('exec_cardinality_test:start', p_test_id => p_test_id);
    -- 1) detect binds from predicates
    -- 2) resolve values from dqu_core.dqu_runtime_binds
    -- 3) execute via dbms_sql; bind by name; handle types
    -- 4) write dqu_test_results
  exception
    when others then
      logger.error('exec_cardinality_test:error', p_test_id => p_test_id, errm => sqlerrm);
      raise;
  end;
end;
/
```

### Git & shell notes for Cline

* Default shell is Linux; **never** emit CRLF sequences. Use `\n` newlines. Avoid `;&` bash typos.
* Useful status snippet:

  ```bash
  git status -sb && echo '===== Porcelain =====' && git status --porcelain=1 -uall
  ```

### MCP server & DSN defaults (for SQCcl)

* Provide a **global default** via rules/anchors and allow per‑target override.
* If `mcp_server` is omitted, Cline should inherit the default.

Example anchors in YAML:

```yaml
x-ci:
  dsn: &default_dsn "cline_mcp"
  mcp_server: &default_mcp "SQCcl"

defaults:
  dsn: *default_dsn
  mcp_server: *default_mcp
```

Then, per target you can either omit `mcp_server` to use default, or override:

```yaml
co01:
  targets:
    - key: co_api
      role: candidate
      schema: co
      package: co_api
      create_test_data: true
      dsn: "cline_mcp_co"
      # mcp_server omitted → defaults to *default_mcp
