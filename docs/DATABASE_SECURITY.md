# Database and device credential security

CAMS requires a master passphrase at every application start. The passphrase is
never written to a settings file. It unlocks two independent protection layers:

- Every runtime and workspace database is opened through SQLCipher Community
  Edition. CAMS derives a 256-bit raw database key in memory and executes
  `PRAGMA key` before the first query on every connection.
- Device login passwords are Fernet-encrypted with a fresh key per value. That
  key is wrapped with the CAMS RSA-2048 public key using OAEP/SHA-256. Only the
  passphrase-protected private key can unwrap it.

On first launch, the CAMS keypair is created at
`~/.config/cams/keys/` on Linux or `%APPDATA%\CAMS\keys\` on Windows. The private
key is stored only as encrypted PKCS#8 PEM. Decrypted key material exists only
in process memory and is released during application shutdown.

## Migration

When CAMS encounters a legacy plaintext SQLite file, it exports it to a new
SQLCipher file, verifies the result, and atomically replaces the old file. It
then encrypts plaintext values in `t01_devices.password` in one transaction.
Legacy database images inside workspace snapshots and status-migration backups
are upgraded as well.

## Backup and recovery

Back up the encrypted private key separately from database and `.ntp` backups.
Keep the public and private key files together, but do not place them in Git or
inside the same backup set as the databases. Restoring data requires all of:

1. the SQLCipher database or `.ntp` project;
2. the original CAMS private/public keypair; and
3. the master passphrase.

There is no recovery key or backdoor. Losing the private key or forgetting the
master passphrase permanently prevents recovery of stored device passwords.

## Dependency policy

`sqlcipher3-binary` must be installed from a compatible wheel. The uv project
configuration disables source builds for this package, so unsupported Python or
platform combinations fail during setup instead of silently requiring a local
compiler and OpenSSL toolchain.

SQLCipher Community Edition attribution and the complete BSD-style license are
available from About in CAMS and in `UI/resources/licenses/SQLCIPHER.txt`.
