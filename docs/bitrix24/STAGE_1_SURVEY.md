# Этап 1. Техническое обследование Битрикс24

Статус: начат. Локальная подготовка завершена; обследование портала ожидает OAuth-доступ администратора.

## Что уже подготовлено

- read-only REST-клиент с обязательным HTTPS и безопасными ошибками без токена;
- проверка доступности необходимых методов через `method.get`;
- выгрузка полей смарт-процесса `entityTypeId=1070`, контакта и сделки;
- выгрузка категорий, стадий, активных пользователей и хранилищ Диска;
- сокращение данных пользователей до ID, имени и должности — email и телефоны в отчёт не попадают;
- явная фиксация того, что обновление OAuth-токена пока не проверено.
- обработчики установки и событий с проверкой портала и шифрованием OAuth-токенов через PostgreSQL `pgcrypto`.

Инструмент выполняет только чтение. Он не создаёт партнёров, клиентов, сделки, задачи, чаты, коллабы или файлы.

## Что требуется от администратора ЮРИТЕХ

1. Создать на портале `bitrix.uriteh.ru` локальное приложение типа «использует только API».
2. Указать публичный HTTPS callback установки. Реализация callback и зашифрованного хранения токенов относится к Этапу 2; до неё для обследования можно временно передать значения напрямую в серверный `.env`.
3. Выдать приложению права: CRM, задачи, чаты/боты, Диск, рабочие группы, пользователи и события.
4. Разрешить создание тестовых записей либо предоставить тестовый портал.
5. Подтвердить, что обработка клиентских документов и паспортных данных в Битрикс24 согласована. До подтверждения тесты используют только синтетические данные.

Токены и секрет приложения нельзя помещать в Git, JSON-отчёт, задачу Битрикс24 или переписку.

## Запуск read-only обследования

В `backend/.env` временно задаются:

```text
BITRIX_CLIENT_ENDPOINT=https://bitrix.uriteh.ru/rest/
BITRIX_ACCESS_TOKEN=<access_token из auth callback>
BITRIX_SMART_PROCESS_ENTITY_TYPE_ID=1070
BITRIX_DEAL_CATEGORY_ID=3
```

Затем из папки `backend`:

```bash
poetry run python -m app.integrations.bitrix24.survey_cli \
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
