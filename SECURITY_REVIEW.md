# WontNote — Local Security Review

Date: October 21, 2026

## Scope

The Python cryptographic core, local vault storage, PyWebView API bridge, and HTML note editor were reviewed. All attack attempts were applied to temporary vaults in the test directory; no real user vault was read, reset, or subjected to password guessing.

## Verified and Resolved Issues

1. **Plaintext overwrite of a locked vault:** `create_vault` was modifying an existing vault when the API was called directly. An initial regression test reproduced this behaviour. A check for an existing vault and atomic, exclusive file creation — also preventing cross-process overwrites — was added.
2. **Unauthenticated vault deletion:** `reset_vault` relied solely on the UI confirmation prompt. An initial regression test was able to delete a locked test vault. The Python layer now requires current-password verification and explicit confirmation. An incorrect password leaves all files untouched.
3. **Unlimited online attempts:** Password and recovery-key attempts are subject to a shared, in-process rate limit. After five failed attempts a lockout starting at 5 seconds and increasing up to 60 seconds is applied. Authentication and lock operations are serialised under the same lock.
4. **Resource exhaustion via tampered header:** An Argon2 parameter in the vault file requesting 1 GiB of memory is rejected at the bridge layer before computation begins. The application's normal parameters (64 MiB / 3 iterations) are unchanged.
5. **Residual UI data after lock:** In addition to note body and title, folders, search state, recovery key, password fields, and counters are cleared from the DOM. The password field is cleared after a successful login. The workspace is temporarily disabled during save and lock operations.
6. **Note content and external resources:** The HTML sanitiser strips script, event attributes, iframe, and external link elements. Drag-and-drop and paste accept plain text only. Remote font requests were removed. CSP blocks objects and frames. `unsafe-eval` is retained due to PyWebView's `new Function` and `eval` requirements; `unsafe-inline` is retained due to existing HTML events — CSP alone does not constitute XSS protection.

Preferences are persisted in a separate JSON file that accepts only allowlisted keys and values. Passwords and notes cannot be written to this file. WebView private mode is preserved; session data is not persisted via the browser as a preference-storage side-channel.

## Attack Vectors Attempted

- Empty and incorrect passwords, SQL-injection-style password strings, invalid recovery keys.
- Reading, creating, editing, deleting notes, and regenerating the recovery key while locked.
- Flipping the last byte of the ciphertext block.
- Replacing an existing vault with a new password and resetting without verification.
- Running login and lock operations concurrently.
- Overwriting an existing target in a file-creation race.
- Forged note fields and a resource-exhausting header.

Decrypting notes with an incorrect password/key or tampered ciphertext could not be achieved. These results are from limited regression tests and do not represent a comprehensive independent penetration test or a guarantee of unbreakability.

## Limitations

The online lockout resets on application restart and does not prevent offline password guessing against a copy of the vault. A strong password is required. Access via a valid recovery key is intended behaviour. Data in an open session cannot be protected against an OS administrator, a memory dump, malware, or physical file deletion. Memory zeroing in Python is best-effort. Auto-lock will not complete locking — and will display an error — if saving the pending note fails, in order to avoid data loss. Auto-lock and the minimise event should be tested separately in a real desktop environment.

## Verification

`tests/test_security_audit.py` covers isolated attack regressions, `tests/test_gui_api.py` covers lock and persistence behaviour, and `tests/test_frontend.cjs` covers preference/shortcut/UI-cleanup flows. Full test results are reported in the application delivery message.
