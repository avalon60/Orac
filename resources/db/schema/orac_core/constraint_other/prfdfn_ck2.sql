-- __author__: clive
-- __date__: 2026-04-27
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.preference_definitions
  add constraint prfdfn_ck2
  check
  (
    control_type in
    (
      'text',
      'textarea',
      'number',
      'checkbox',
      'select_list',
      'select_one',
      'popup_lov',
      'radio_group',
      'switch',
      'display_only'
    )
  )
;
