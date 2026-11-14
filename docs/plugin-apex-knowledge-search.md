# Plugin APEX Knowledge Search

Plugin-installed APEX applications can search documents ingested into their
own `PLUGIN:<plugin_id>` knowledge scope. Core owns the search request, query
embedding, authorisation, retrieval, and results. A plugin application receives
no direct access to Core knowledge tables or the general retrieval package.

## APEX contract

The application runs in the shared `ORAC` workspace as `ORAC_APX_PUB`. From an
authenticated page process, submit a query and retain the returned numeric ID
in session state:

```sql
declare
  l_request_id number;
begin
  orac_code.knowledge_apex_search_api.submit_search(
    p_query => :P1_QUERY,
    p_request_id => l_request_id
  );
  :P1_REQUEST_ID := l_request_id;
end;
```

After the page request commits, poll with `read_search`. It returns a status
and a cursor with `ordinal`, `document_id`, `document_version_id`, `chunk_id`,
`chunk_no`, `title`, `relevance_score`, and `excerpt`. `COMPLETED` returns at
most six current excerpts of 2,200 characters each. `NO_EVIDENCE` returns an
empty cursor. `QUEUED` and `PROCESSING` mean the page should poll again.
`FAILED` is a safe terminal failure; `EXPIRED` means the request has passed its
24-hour lifetime. Submission is limited to 30 requests per user and app in an
hour and five pending requests. The application should escape excerpts when
rendering them.

The API reads the exact `APP_USER` and `APP_ID` from the active APEX session.
It maps the installed app to its registered plugin scope and checks that user's
current `USE` grant. Neither procedure accepts a username, plugin ID, or scope
selector. Polling requires the same user and app and rechecks the grant. A
withdrawn or superseded chunk is omitted from the cursor. SQLcl calls without
an active APEX session fail closed.

## Core processing

The Core `knowledge_apex_search` scheduled service claims queued requests,
generates query embeddings with the active knowledge profile, and runs the
existing authorised plugin-scope retrieval. It stores only bounded result
identities and scores in the transient request row; passage text is selected
from the current searchable view when the APEX app polls. The worker purges
expired rows. Core's retrieval audit records the search decision and outcome;
query text and passages are not logged by the worker.

The feature requires `[knowledge].enabled = true`, an eligible installed
plugin, completed searchable ingestion, and a current `USE` grant for the
signed-in user on that plugin scope. It does not search project scopes.
