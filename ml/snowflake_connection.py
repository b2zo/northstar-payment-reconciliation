import getpass
import os
from pathlib import Path

import snowflake.connector


def open_connection():
    key_path = (
        Path.home() / ".dbt" / "northstar_keys" / "northstar_dbt.p8"
    )

    if not key_path.is_file():
        raise FileNotFoundError(f"Private key not found: {key_path}")

    passphrase = os.environ.get("NORTHSTAR_KEY_PASSPHRASE")
    if not passphrase:
        passphrase = getpass.getpass("Private-key passphrase: ")

    return snowflake.connector.connect(
        account="JZFVQTV-JR06489",
        user="NORTHSTAR_DBT_SVC",
        authenticator="SNOWFLAKE_JWT",
        private_key_file=str(key_path),
        private_key_file_pwd=passphrase,
        role="NORTHSTAR_DBT_ROLE",
        warehouse="NORTHSTAR_WH",
        database="NORTHSTAR_FINANCE",
        schema="ANALYTICS_MARTS",
        login_timeout=30,
        session_parameters={
            "QUERY_TAG": "northstar_python_extraction",
            "STATEMENT_TIMEOUT_IN_SECONDS": 60,
        },
    )


def main():
    connection = open_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("USE SECONDARY ROLES NONE")
            cursor.execute("SELECT CURRENT_USER(), CURRENT_ROLE()")
            user, role = cursor.fetchone()

            if (user, role) != (
                "NORTHSTAR_DBT_SVC",
                "NORTHSTAR_DBT_ROLE",
            ):
                raise RuntimeError("Unexpected connection identity")

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM NORTHSTAR_FINANCE.ANALYTICS_MARTS
                    .FCT_RECONCILIATION_EXCEPTIONS
                """
            )
            count = cursor.fetchone()[0]

            print("CONNECTION PASSED")
            print(f"User: {user}")
            print(f"Role: {role}")
            print(f"Exception rows: {count:,}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()