# ShopFlow Bot

ShopFlow Bot — Telegram-бот для магазина с каталогом, корзиной, оформлением заказов и административной панелью.

## Возможности

- каталог по категориям
- карточки товаров с фото, описанием, ценой и размерами
- корзина
- оформление заказа через FSM
- ручное подтверждение оплаты администратором
- история заказов и статусы
- отзывы на товары
- административная панель
- фоновые задачи: напоминания об оплате, автоотмена просроченных заказов, рассылка новых товаров

## Технологии

- Python 3.11+
- aiogram 3.x
- SQLAlchemy 2.x async
- PostgreSQL для продакшена
- Redis для FSM
- APScheduler для фоновых задач

## Быстрый запуск

### 1. Установка зависимостей

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Подготовка окружения

```bash
cp .env.example .env
```

Минимально заполните:

- `BOT_TOKEN`
- `ADMIN_IDS`
- `PAYMENT_CARD`
- `PAYMENT_HOLDER`

Для локальной разработки можно использовать:

```env
USE_SQLITE=true
USE_MEMORY_FSM=true
```

### 3. Запуск

```bash
python main.py
```

## Docker

Для запуска через Docker Compose:

```bash
docker compose up -d --build
```

Для такого запуска укажите в `.env`:

```env
USE_SQLITE=false
DATABASE_URL=postgresql+asyncpg://shopflow:shopflow@postgres:5432/shopflow
REDIS_URL=redis://redis:6379/0
USE_MEMORY_FSM=false
```

## Переменные окружения

| Переменная                        | Описание                                          |
| --------------------------------- | ------------------------------------------------- |
| `BOT_TOKEN`                       | токен Telegram-бота                               |
| `SHOP_NAME`                       | название магазина                                 |
| `USE_SQLITE`                      | использовать SQLite для локальной разработки      |
| `SQLITE_PATH`                     | путь к файлу SQLite                               |
| `DATABASE_URL`                    | DSN PostgreSQL                                    |
| `REDIS_URL`                       | DSN Redis для FSM                                 |
| `USE_MEMORY_FSM`                  | использовать память процесса вместо Redis         |
| `ADMIN_IDS`                       | Telegram ID администраторов через запятую         |
| `PAYMENT_CARD`                    | номер карты для ручной оплаты                     |
| `PAYMENT_HOLDER`                  | имя получателя                                    |
| `TIMEZONE`                        | часовой пояс приложения                           |
| `LOG_LEVEL`                       | уровень логирования                               |
| `ORDER_EXPIRY_HOURS`              | автоотмена неоплаченных заказов через N часов     |
| `PAYMENT_REMINDER_AFTER_HOURS`    | через сколько часов отправлять первое напоминание |
| `PAYMENT_REMINDER_INTERVAL_HOURS` | интервал повторных напоминаний                    |
| `MAX_CART_ITEMS`                  | лимит уникальных позиций в корзине                |
| `DB_POOL_SIZE`                    | размер пула соединений БД                         |
| `DB_MAX_OVERFLOW`                 | дополнительный пул соединений                     |
| `DB_POOL_TIMEOUT`                 | таймаут ожидания соединения                       |
| `BROADCAST_CHUNK_SIZE`            | размер пакета рассылки                            |
| `BROADCAST_DELAY_MS`              | задержка между пакетами рассылки                  |

## Структура проекта

```text
bot/
  common/
    presenters.py
  core/
    container.py
    exceptions.py
    scheduler.py
  handlers/
    common/
    user/
    admin/
  keyboards/
  middlewares/
  models/
  services/
  utils/
config.py
main.py
```

## Архитектура

### Handlers
Обрабатывают только Telegram-события и вызывают сервисы.

### Services
Содержат всю бизнес-логику и все операции с базой данных.

### Models
Описывают таблицы БД и состояния FSM.

### Middlewares
Подключают логирование, создают пользователя и внедряют request-scoped контейнер сервисов.

### Keyboards
Содержат только построение интерфейса.

### Utils
Содержат форматтеры и Telegram-хелперы.

### Scheduler
Запускает фоновые задачи через тот же сервисный слой.

## Как работает внедрение зависимостей

На каждый update middleware создаёт request-scoped контейнер `services` с общей `AsyncSession`.

В handlers доступны:

- `services` — набор сервисов приложения
- `db_user` — пользователь из базы данных

Это позволяет:

- не обращаться к БД напрямую из handlers
- переиспользовать бизнес-логику
- держать транзакции в одном месте

## Инициализация базы

Таблицы создаются автоматически при запуске через `create_all`.

Для продакшена рекомендуется сразу использовать PostgreSQL и Redis.

## Deep links

Рассылка новых товаров использует deep link такого вида:

```text
https://t.me/<имя_бота>?start=product_<id>
```

## Расширение проекта

### Добавить новый пользовательский сценарий

1. Добавьте метод в соответствующий сервис
2. Создайте handler, который вызовет сервис
3. При необходимости добавьте клавиатуру
4. Подключите router

### Добавить новое действие в админке

1. Реализуйте бизнес-логику в сервисе
2. Добавьте callback handler в `bot/handlers/admin/`
3. Добавьте кнопку в `bot/keyboards/admin.py`

### Подключить CDN или S3

Поле `Product.images` уже поддерживает ссылки и Telegram file_id. Можно хранить там CDN URL или S3-ссылки.

## Рекомендации для продакшена

- используйте PostgreSQL вместо SQLite
- используйте Redis вместо in-memory FSM
- запускайте бота под systemd или Docker
- настройте резервное копирование БД
- держите `LOG_LEVEL=INFO`
- следите за размером пула БД и доступностью Redis