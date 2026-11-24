# -*- coding: utf-8 -*-
"""timecapsule-dev-mailer: печатает письмо о запечатанной капсуле.

Источник — очередь timecapsule-dev-mail (SNS -> SQS). Функция подключена к VPC,
поэтому обращается к RDS по приватному адресу. Повторная доставка SQS не создаёт
второе уведомление: вставка идёт с ON CONFLICT (capsule_id, kind) DO NOTHING.
"""
import json
import os
import time

import psycopg2


def connect():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode=os.environ.get("PGSSLMODE", "require").replace("no-verify", "require"),
        connect_timeout=10,
    )


def handler(event, context):
    delay = int(os.environ.get("MAIL_DELAY_SECONDS", "5"))
    print("получено сообщений: %d" % len(event.get("Records", [])))
    conn = connect()
    processed = []
    try:
        for rec in event.get("Records", []):
            body = json.loads(rec["body"])
            if body.get("event") != "capsule.sealed":
                print("пропущено событие:", body.get("event"))
                continue

            time.sleep(delay)  # медленный почтовый сервер

            with conn.cursor() as cur:
                cur.execute(
                    """insert into notifications (capsule_id, user_id, kind, capsule_title)
                       values (%s, %s, 'sealed', %s)
                       on conflict (capsule_id, kind) do nothing
                       returning id""",
                    (body["capsule_id"], body["user_id"], body["title"]))
                duplicate = cur.fetchone() is None
            conn.commit()
            print("капсула %s: письмо %s" % (body["capsule_id"],
                                             "уже было (дубль)" if duplicate else "записано"))
            processed.append({"capsule_id": body["capsule_id"], "duplicate": duplicate})
    finally:
        conn.close()
    return {"processed": processed, "count": len(processed)}
