# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os

import boto3
import psycopg2


def handler(event, context):

    DATABASE_ACCOUNT_IAM_ROLE = os.environ["DATABASE_ACCOUNT_IAM_ROLE"]
    RDS_PROXY_APPLICATION_ENDPOINT = os.environ["RDS_PROXY_APPLICATION_ENDPOINT"]
    DB_USERNAME = os.environ["DB_USERNAME"]
    DBNAME = os.environ["DBNAME"]
    REGION = os.environ["AWS_REGION"]
    PORT = "5432"

    sts_connection = boto3.client("sts")

    database_account_session = sts_connection.assume_role(
        RoleArn=DATABASE_ACCOUNT_IAM_ROLE,
        RoleSessionName="cross_acct_connection",
    )

    ACCESS_KEY = database_account_session["Credentials"]["AccessKeyId"]
    SECRET_KEY = database_account_session["Credentials"]["SecretAccessKey"]
    SESSION_TOKEN = database_account_session["Credentials"]["SessionToken"]

    client = boto3.client(
        "rds",
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        aws_session_token=SESSION_TOKEN,
    )

    token = client.generate_db_auth_token(
        DBHostname=RDS_PROXY_APPLICATION_ENDPOINT,
        Port=int(PORT),
        DBUsername=DB_USERNAME,
        Region=REGION,
    )

    conn = psycopg2.connect(
        host=RDS_PROXY_APPLICATION_ENDPOINT,
        port=PORT,
        database=DBNAME,
        user=DB_USERNAME,
        password=token,
        sslmode="require",
    )

    cur = conn.cursor()
    cur.execute("""select * from information_schema.tables""")
    print(cur.fetchall())

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": "Database connection was successful!",
    }
