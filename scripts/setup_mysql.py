"""One-time MySQL setup: creates the database and app user using the values in .env.

Run from the project folder (with .venv active):
    python -m scripts.setup_mysql

It asks for the MySQL *root* password (hidden while you type) and never stores it.
Safe to run again: it also resets the app user's password to match .env.
"""
import getpass
import re
import sys

import pymysql

from app.config import settings as s


def main() -> int:
    if not s.db_password:
        print("DB_PASSWORD is empty in .env. Set it first, save the file, then run this again.")
        return 1
    if not re.fullmatch(r"\w+", s.db_name):
        print("DB_NAME may only contain letters, digits and _.")
        return 1

    root_pw = getpass.getpass("MySQL root password (hidden): ")
    try:
        conn = pymysql.connect(host=s.db_host, port=s.db_port, user="root", password=root_pw, autocommit=True)
    except pymysql.err.OperationalError as e:
        print(f"Could not log in as root: {e.args[-1]}")
        return 1

    with conn, conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{s.db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        cur.execute("CREATE USER IF NOT EXISTS %s@'localhost' IDENTIFIED BY %s", (s.db_user, s.db_password))
        cur.execute("ALTER USER %s@'localhost' IDENTIFIED BY %s", (s.db_user, s.db_password))
        cur.execute(f"GRANT ALL PRIVILEGES ON `{s.db_name}`.* TO %s@'localhost'", (s.db_user,))
        print(f"Database `{s.db_name}` and user '{s.db_user}'@'localhost' are ready.")

    try:
        pymysql.connect(host=s.db_host, port=s.db_port, user=s.db_user, password=s.db_password, database=s.db_name).close()
    except pymysql.err.OperationalError as e:
        print(f"App user still cannot log in: {e.args[-1]}")
        return 1
    print("Check passed: the app can log in with the password in .env.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
