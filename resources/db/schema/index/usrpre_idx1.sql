-- idx: user_prompt_elements by (user, category)
create index orac.usrpre_idx1 on orac.user_prompt_elements(user_id, category_code);
