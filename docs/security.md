# Northstar security

## Authentication

The dbt pipeline uses a dedicated Snowflake service user,
NORTHSTAR_DBT_SVC, with RSA key-pair authentication.

The public key is registered in Snowflake. The private key is stored
locally outside the repository in encrypted PKCS#8 format.

The private-key passphrase is supplied through the
NORTHSTAR_KEY_PASSPHRASE environment variable and is entered through
a hidden PowerShell prompt.

## Authorisation

NORTHSTAR_DBT_ROLE can:
- Use NORTHSTAR_WH and NORTHSTAR_FINANCE.
- Read the four raw source tables.
- Create tables and views in the staging and marts schemas.
- Rebuild the dbt models it owns.

NORTHSTAR_ANALYST_ROLE has:
- Warehouse and database usage.
- Read access to existing and future mart tables.

An access test confirmed that the analyst role cannot query RAW.EVENTS.
Secondary roles were disabled during the test to isolate its permissions.

## Encryption

The locally stored private key is encrypted with a passphrase.

Key-pair authentication proves the service identity. Encryption of
connections and warehouse data is a separate concern handled by
Snowflake; this project does not implement its own encryption algorithm.

## Verification

The full dbt build completed successfully after switching the
connection to the service user:
- 8 models built.
- 30 data tests passed.
- 0 errors and 0 warnings.

## Operating practices

Private keys, passphrases and local connection profiles must stay
outside version control.

The current setup is a portfolio implementation. Production work
would also include managed secret storage, key rotation, access
reviews and monitoring of authentication activity.