# ShopMate Authentication and User-Experience Audit

## Current architecture

- Database table `app_users` stores `username`, normalized username, optional `email`, normalized email, required `display_name`, linked `profile_id`, password hash/salt/iterations/algorithm, account status, timestamps, and `last_login_at`.
- Signup request currently requires `username`, `password`, and `confirm_password`. `display_name` and `email` are optional in the backend schema.
- Login requires `login_identity` plus `password`; the frontend labels this field **Username or email**.
- The frontend signup form requires Username, Password, and Confirm password. Display name and Email are visible but optional.
- The authentication response and session workspace return `account.display_name`; the frontend normalizer prefers `display_name`, then account/username fallbacks.
- The sidebar/account area shows the normalized display name and uses its first character for the avatar.
- The current initial chat copy is generic (`Fresh start! What are you shopping for today?`). The login heading is generic (`Welcome back`) rather than `Welcome back, <display name>!`.
- Logout clears the browser token. A later username-or-email login returns the persisted workspace and display name.

## Target-UX gap

The desired signup contract (Display Name, Email, Password) does not match the current backend or frontend. Username participates in required request validation, database uniqueness/normalization, login identity, and UI state. Display name is already suitable as presentation identity, and email is already stored and accepted for login, but username cannot simply be hidden without changing validation, uniqueness rules, account creation, and migration/backfill behavior.

## Can username be removed safely later?

**REQUIRES MIGRATION.** A safe change needs an email-required/unique contract, a migration/backfill policy for existing accounts without email, updated registration/login schemas, frontend form changes, and compatibility handling for existing username logins.

## Display-name greeting status

**NO.** Display name is returned and shown in the account/sidebar UI, but personalized post-signup and welcome-back greeting sentences are not currently implemented.

## Diagnostic-only recommendations (not implemented)

1. Make normalized email the required unique authentication identity while preserving legacy username login during migration.
2. Keep `display_name` as required presentation identity and return it in every auth/session workspace.
3. Remove username from new signup UI only after backend migration and compatibility tests.
4. Generate greeting copy from authenticated `display_name` after registration and login.
5. Add contract tests for logout/login persistence, email uniqueness, legacy accounts, and display-name rendering.
