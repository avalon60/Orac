create or replace package orac_utils authid definer
as
  -----------------------------------------------------------------------------
  --  orac_utils
  --
  --  Utility package for Zen → ORDS prechecks. Provides helpers to:
  --    • read HTTP headers in an ORDS context
  --    • resolve OS usernames → canonical user_ids
  --    • validate devices against allow-list
  --    • optional HMAC/timestamp/nonce verification for spoof/replay protection
  --    • set DB session identity for auditing/row-level security
  --
  --  Typical usage in an ORDS handler:
  --    begin
  --      orac_utils.slave_precheck; -- raises 403 if checks fail
  --      -- continue with business logic
  --    end;
  -----------------------------------------------------------------------------

  -----------------------------------------------------------------------------
  -- Return the value of an HTTP header from OWA/ORDS environment.
  -- Example: header('X-Zen-User') → 'clive'
  -----------------------------------------------------------------------------
  function header(p_name in varchar2) return varchar2;

  -----------------------------------------------------------------------------
  -- Base64url decode (helper for HMAC).
  -----------------------------------------------------------------------------
  function b64url_to_raw(p_b64url in varchar2) return raw;

  -----------------------------------------------------------------------------
  -- Compute HMAC-SHA256 of a message using the provided raw secret.
  -- Example: hmac_sha256(secret_raw, 'clive|AA:BB|2025-08-22T...|nonce')
  -----------------------------------------------------------------------------
  function hmac_sha256(p_secret_raw in raw, p_message in varchar2) return raw;

  -----------------------------------------------------------------------------
  -- Lookup a configuration setting in orac.auth_settings.
  -- Used to retrieve shared HMAC secret or other auth parameters.
  -----------------------------------------------------------------------------
  function get_setting(p_key in varchar2) return varchar2;

  -----------------------------------------------------------------------------
  -- Check if a supplied ISO8601 UTC timestamp is “fresh” within
  -- a skew allowance (default ±120 seconds).
  -- Returns true if valid, false otherwise.
  -----------------------------------------------------------------------------
  function fresh_timestamp(
    p_iso_utc      in varchar2,
    p_skew_seconds in pls_integer default 120
  ) return boolean;

  -----------------------------------------------------------------------------
  -- Verify that a nonce value has not been used recently.
  -- Returns true if unused within ttl_seconds (default 600).
  -- Call mark_nonce_used afterwards to persist the nonce.
  -----------------------------------------------------------------------------
  function nonce_unused(
    p_nonce       in varchar2,
    p_ttl_seconds in pls_integer default 600
  ) return boolean;

  -----------------------------------------------------------------------------
  -- Record a nonce as “used” in orac.auth_nonces.
  -- Used to prevent replay attacks.
  -----------------------------------------------------------------------------
  procedure mark_nonce_used(p_nonce in varchar2);

  -----------------------------------------------------------------------------
  -- Resolve an OS username (alias_type = 'os') into a canonical user_id.
  -- Returns null if not found or inactive.
  -----------------------------------------------------------------------------
  function resolve_user(p_os_user in varchar2) return varchar2;

  -----------------------------------------------------------------------------
  -- Check whether a device is allowed for a given user_id.
  -- Returns true if a matching row exists in orac.devices.
  -----------------------------------------------------------------------------
  function device_allowed(
    p_device_id in varchar2,
    p_user_id   in varchar2
  ) return boolean;

  -----------------------------------------------------------------------------
  -- Tag the current DB session with user_id + host/device info.
  -- Sets DBMS_SESSION.CLIENT_IDENTIFIER and DBMS_APPLICATION_INFO.CLIENT_INFO.
  -----------------------------------------------------------------------------
  procedure set_session_identity(
    p_user_id in varchar2,
    p_host    in varchar2,
    p_device  in varchar2
  );

  -----------------------------------------------------------------------------
  -- Main entrypoint for Zen request validation.
  --
  -- Steps performed:
  --   1. Read X-Zen-User, X-Zen-DevID/MAC, X-Zen-Host headers.
  --   2. Resolve OS user → canonical user_id via orac.user_synonyms.
  --   3. Check device allow-list in orac.devices.
  --   4. If p_require_sig=true, optional HMAC/timestamp/nonce verification
  --      can be added (future extension).
  --   5. Tag session identity.
  --
  -- On failure: sets HTTP 403 Forbidden and stops execution.
  -----------------------------------------------------------------------------
  procedure slave_precheck(p_require_sig in boolean default true);

end orac_utils;
/

