# timecapsule-mailer

AWS Lambda-функция `timecapsule-dev-mailer` для лабораторной работы №7 (часть 2):
отправка письма о запечатанной капсуле вынесена из HTTP-запроса в фоновую обработку.

## Что делает функция

1. Получает сообщения из очереди `timecapsule-dev-mail` (триггер SQS, `BatchSize = 1`).
2. Для каждого сообщения с `event = capsule.sealed` «отправляет письмо» — в учебной
   версии это задержка `MAIL_DELAY_SECONDS` и запись факта отправки в таблицу
   `notifications`.
3. Вставка идёт с `ON CONFLICT (capsule_id, kind) DO NOTHING`, поэтому повторная
   доставка сообщения (at-least-once) не создаёт второе уведомление.

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | подключение к RDS PostgreSQL |
| `PGSSLMODE` | `require` (значение `no-verify` приводится к `require`) |
| `MAIL_DELAY_SECONDS` | задержка, имитирующая почтовый сервер (по умолчанию 5) |

Секретов в репозитории нет: значения задаются в конфигурации функции, права
доступа к SQS и VPC — у роли выполнения.

## Сборка пакета

Функция написана на Python 3.12 и зависит от `psycopg2-binary` (manylinux-колесо):

```bash
pip install --target build -r requirements.txt \
  --platform manylinux2014_x86_64 --python-version 3.12 \
  --implementation cp --only-binary=:all:
cd build && zip -r ../mailer.zip . && cd ..
zip -g mailer.zip handler.py
```

Затем `aws lambda update-function-code --function-name timecapsule-dev-mailer \
  --zip-file fileb://mailer.zip`.

## Инфраструктура

* Очередь `timecapsule-dev-mail` + DLQ `timecapsule-dev-mail-dlq`
  (`maxReceiveCount = 3`, хранение 14 суток).
* Триггер SQS с `ScalingConfig.MaximumConcurrency = 2`
  (резервированная конкурентность в учебном аккаунте недоступна).
* Функция в приватных подсетях VPC, SG `timecapsule-dev-lambda-sg`, доступ к RDS по 5432.
* Таймаут функции 30 с, `VisibilityTimeout` очереди 120 с.

## Проверка

* Успешная обработка: в журнале `получено сообщений: 1` и
  `капсула <id>: письмо записано`.
* Повторная доставка: `капсула <id>: письмо уже было (дубль)`, в БД одна строка.
* Сбой (неверный пароль БД): `OperationalError`, сообщение возвращается в очередь
  и после третьего приёма уходит в DLQ; после исправления — redrive из DLQ.

Контракты событий: см. `docs/events.md` в репозитории `timecapsule-app`.
