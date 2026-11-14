--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 12-Nov-2026
-- Description: Bounded reviewed Chess explanation evidence.
-- Purpose: Expose only declared text and move context through a read-only view.
-- Usage: Included through the managed Chess plugin controller.

--changeset clive:orac_chess_chess_query_opening_text_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_query_opening_text_v as
select opening_id, name, cast(substr(description,1,1000) as varchar2(4000 byte)) description,
       case when length(description)>1000 then 'Y' else 'N' end description_truncated,
       cast(substr(strategy,1,2000) as varchar2(8000 byte)) strategy,
       case when length(strategy)>2000 then 'Y' else 'N' end strategy_truncated
from orac_chess.chess_opening;
--rollback drop view orac_chess.chess_query_opening_text_v;
