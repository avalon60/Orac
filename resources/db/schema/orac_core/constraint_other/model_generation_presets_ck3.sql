-- __author__: clive
-- __date__: 2026-05-23
-- __description__: validates generation preset numeric ranges


alter table orac_core.model_generation_presets
  add constraint model_generation_presets_ck3
  check (
    (temperature is null or temperature between 0 and 2)
    and (top_p is null or top_p between 0 and 1)
    and (top_k is null or top_k >= 1)
    and (repeat_penalty is null or repeat_penalty > 0)
    and (num_predict is null or num_predict >= 1)
  )
;
