-- pk index: orac.user_synonyms(alias_type, alias_value)
create unique index orac.usrsyns_pk_idx on orac.user_synonyms(alias_type, alias_value);
