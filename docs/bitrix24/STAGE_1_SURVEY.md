# Этап 1. Техническое обследование Битрикс24

Статус: read-only обследование продуктивного портала завершено 2026-08-01. Все 6 CRM-проверок прошли успешно; черновик таблицы соответствий сохранён в `STAGE_1_FIELD_MAPPING.md`.

## Что уже подготовлено

- read-only REST-клиент с обязательным HTTPS и безопасными ошибками без токена;
- проверка доступности необходимых методов через `method.get`;
- выгрузка полей смарт-процесса `entityTypeId=1070`, контакта и сделки;
- выгрузка категорий, стадий, активных пользователей и хранилищ Диска;
- сокращение данных пользователей до ID, имени и должности — email и телефоны в отчёт не попадают;
- проверенное обновление OAuth-токена с сохранением новой пары в PostgreSQL;
- полная выгрузка 635 CRM-статусов с пагинацией по курсору `next`.
- обработчики установки и событий с проверкой портала и шифрованием OAuth-токенов через PostgreSQL `pgcrypto`.

Инструмент выполняет только чтение. Он не создаёт партнёров, клиентов, сделки, задачи, чаты, коллабы или файлы.

## Подтверждённая конфигурация

- локальное OAuth-приложение установлено на `bitrix.uriteh.ru`;
- HTTPS-обработчики установки и событий опубликованы;
- права `crm`, `task`, `disk`, `user`, `socialnetwork`, `im`, `imbot` подтверждены живым REST-вызовом;
- access- и refresh-токены хранятся в PostgreSQL в зашифрованном виде.

Для тестов с записью ещё нужны разрешение на синтетические записи в продуктивном портале либо тестовый портал. Передача клиентских документов и паспортных данных требует отдельного подтверждения.

Токены и секрет приложения нельзя помещать в Git, JSON-отчёт, задачу Битрикс24 или переписку.

## Запуск read-only обследования

После установки локального приложения команда по умолчанию берёт access token из
зашифрованного хранилища PostgreSQL. Из папки `backend` выполните:

```bash
poetry run python -m app.integrations.bitrix24.survey_cli \
  --portal-domain bitrix.uriteh.ru \
  --output ../docs/bitrix24/survey-result.json
```

Токен расшифровывается только в памяти процесса и не выводится в терминал или
JSON-отчёт.

Если access token истёк или скоро истечёт, команда автоматически получает новую
пару токенов и сохраняет оба значения в PostgreSQL в зашифрованном виде.

Для локальной разработки без сохранённой установки можно явно использовать
переменные окружения. В `backend/.env` временно задаются:

```text
BITRIX_CLIENT_ENDPOINT=https://bitrix.uriteh.ru/rest/
BITRIX_ACCESS_TOKEN=<access_token из auth callback>
BITRIX_CLIENT_ID=<код локального приложения>
BITRIX_CLIENT_SECRET=<ключ локального приложения>
BITRIX_SMART_PROCESS_ENTITY_TYPE_ID=1070
BITRIX_DEAL_CATEGORY_ID=3
```

Затем из папки `backend`:

```bash
poetry run python -m app.integrations.bitrix24.survey_cli \
  --from-env \
  --output ../docs/bitrix24/survey-result.json
```

`survey-result.json` содержит конфигурацию портала и не должен публиковаться наружу. После проверки доступов он становится основанием для таблицы соответствия полей.

## Следующие действия Этапа 1

- реализовать callback установки и защищённое хранение OAuth-токенов;
- проверить обновление access token с обязательным сохранением новой пары токенов;
- выполнить read-only обследование;
- создать синтетические тестовые записи в отдельном тестовом контуре;
- проверить создание коллабы на текущей редакции портала;
- составить и согласовать таблицу соответствия полей;
- удалить или архивировать тестовые записи по согласованию с администратором.

## Официальная документация

- OAuth и обновление токенов: https://apidocs.bitrix24.ru/settings/oauth/auto-renewal.html
- callback локального приложения: https://apidocs.bitrix24.ru/settings/app-installation/local-apps/installation-callback.html
- события `event.bind`: https://apidocs.bitrix24.ru/api-reference/events/event-bind.html
- проверка доступности `method.get`: https://apidocs.bitrix24.ru/api-reference/common/system/method-get.html
- поля CRM `crm.item.fields`: https://apidocs.bitrix24.ru/api-reference/crm/universal/crm-item-fields.html
- воронки `crm.category.list`: https://apidocs.bitrix24.ru/api-reference/crm/universal/category/crm-category-list.html
- хранилища `disk.storage.getlist`: https://apidocs.bitrix24.ru/api-reference/disk/storage/disk-storage-get-list.html
