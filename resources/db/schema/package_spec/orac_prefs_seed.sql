create or replace package orac.orac_prefs_seed as
-- ===================================================================
-- Author      : Clive Bostock
-- Date        : 2025-08-31
-- Description : Seeds default user preference values into ORAC.USER_PREFERENCES.
--               Ensures consistent defaults across new users or updates.
-- ===================================================================
  function defaults_q return sys.odcivarchar2list pipelined;
  /**
   * Seed default user preferences for a single user.
   *
   * :param p_user_id: The user_id from ORAC.USERS to seed preferences for.
   * :param p_overwrite: When TRUE, will also update existing preferences.
   */
  procedure seed_user(
    p_user_id   in number,
    p_overwrite in boolean default false
  );

  /**
   * Seed default preferences for all active users.
   *
   * :param p_overwrite: When TRUE, updates existing preferences to match defaults.
   */
  procedure seed_all(
    p_overwrite in boolean default false
  );

end orac_prefs_seed;
/

