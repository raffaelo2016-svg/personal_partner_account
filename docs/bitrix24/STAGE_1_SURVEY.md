# Этап 1. Техническое обследование Битрикс24

Статус: техническое обследование продуктивного портала завершено 2026-08-01. Все 6 CRM-проверок и согласованные синтетические тесты записи прошли успешно; технически подтверждённая таблица соответствий сохранена в `STAGE_1_FIELD_MAPPING.md`.

## Что уже подготовлено

- read-only REST-клиент с обязательным HTTPS и безопасными ошибками без токена;
- проверка доступности необходимых методов через `method.get`;
- выгрузка полей смарт-процесса `entityTypeId=1070`, контакта и сделки;
- выгрузка категорий, стадий, активных пользователей и хранилищ Диска;
- сокращение данных пользователей до ID, имени и должности — email и телефоны в отчёт не попадают;
- проверенное обновление OAuth-токена с сохранением новой пары в PostgreSQL;
- полная выгрузка 635 CRM-статусов с пагинацией по курсору `next`.
- обработчики установки и событий с проверкой портала и шифрованием OAuth-токенов через PostgreSQL `pgcrypto`.

Основной инструмент обследования выполняет только чтение. Одноразовые тесты записи выполнялись отдельно, под контролем и с обязательной очисткой.

## Подтверждённая конфигурация

- локальное OAuth-приложение установлено на `bitrix.uriteh.ru`;
- HTTPS-обработчики установки и событий опубликованы;
- права `crm`, `task`, `disk`, `user`, `socialnetwork`, `im`, `imbot` подтверждены живым REST-вызовом;
- access- и refresh-токены хранятся в PostgreSQL в зашифрованном виде.

## Результаты синтетических тестов записи

Тесты выполнены 2026-08-01 в продуктивном портале после прямого разрешения администратора. Все объекты имели явную метку `CODEX TEST`; реальные данные клиентов, телефоны, email и документы не использовались.

- элемент смарт-процесса партнёров (`entityTypeId=1070`, категория `19`) создан, прочитан, изменён и удалён;
- контакт создан, прочитан и удалён;
- сделка в категории `3` создана со связями с тестовыми контактом и партнёром, прочитана, изменена и удалена;
- задача создана, прочитана, изменена и удалена; пустой ответ последующего `tasks.task.get` подтвердил отсутствие объекта;
- файл с безопасным текстом создан в изолированном хранилище локального приложения (`ENTITY_TYPE=restapp`), прочитан и удалён навсегда;
- закрытый чат создан только с пользователем, установившим приложение, прочитан, после чего пользователь вышел из чата; повторное чтение стало недоступно;
- все CRM-объекты, задача и файл после теста отсутствуют; другие сотрудники в чат не приглашались.

Передача клиентских документов и паспортных данных этими тестами не разрешалась и не выполнялась.

## Решение по коллабам

Живая проверка `method.get` показала:

- отдельный REST-метод создания коллабы на портале отсутствует (`isExisting=false`, `isAvailable=false`);
- `sonet_group.create` существует, но недоступен установленному приложению (`isExisting=true`, `isAvailable=false`) и создаёт рабочую группу/проект, а не отдельную коллабу;
- доступного автономного сценария создания именно коллабы в текущей конфигурации нет.

Поэтому применяется предусмотренный планом резервный сценарий: администратор создаёт коллабу вручную, а интеграция сохраняет и проверяет её ID. Автоматическое создание коллаб остаётся выключенным до появления документированного и доступного порталу метода.

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

## Выполнение Этапа 1

- [x] реализовать callback установки и защищённое хранение OAuth-токенов;
- [x] проверить обновление access token с обязательным сохранением новой пары токенов;
- [x] выполнить read-only обследование;
- [x] создать разрешённые синтетические тестовые записи и очистить их;
- [x] проверить возможность создания коллабы на текущей редакции портала;
- [x] активировать сценарий ручной привязки коллабы;
- [x] составить и технически подтвердить таблицу соответствия полей;
- [x] получить бизнес-подтверждение безопасного контура таблицы соответствия перед реализацией синхронизации.

## Официальная документация

- OAuth и обновление токенов: https://apidocs.bitrix24.ru/settings/oauth/auto-renewal.html
- callback локального приложения: https://apidocs.bitrix24.ru/settings/app-installation/local-apps/installation-callback.html
- события `event.bind`: https://apidocs.bitrix24.ru/api-reference/events/event-bind.html
- проверка доступности `method.get`: https://apidocs.bitrix24.ru/api-reference/common/system/method-get.html
- поля CRM `crm.item.fields`: https://apidocs.bitrix24.ru/api-reference/crm/universal/crm-item-fields.html
- воронки `crm.category.list`: https://apidocs.bitrix24.ru/api-reference/crm/universal/category/crm-category-list.html
- хранилища `disk.storage.getlist`: https://apidocs.bitrix24.ru/api-reference/disk/storage/disk-storage-get-list.html
- хранилище приложения `disk.storage.getforapp`: https://apidocs.bitrix24.com/api-reference/disk/storage/disk-storage-get-for-app.html
- загрузка файла `disk.storage.uploadfile`: https://apidocs.bitrix24.com/api-reference/disk/storage/disk-storage-upload-file.html
- безвозвратное удаление файла `disk.file.delete`: https://apidocs.bitrix24.com/api-reference/disk/file/disk-file-delete.html
- создание чата `im.chat.add`: https://apidocs.bitrix24.com/api-reference/chats/im-chat-add.html
- выход из чата `im.chat.leave`: https://apidocs.bitrix24.com/api-reference/chats/chat-users/im-chat-leave.html
- создание рабочей группы или проекта `sonet_group.create`: https://apidocs.bitrix24.com/api-reference/sonet-group/sonet-group-create.html
