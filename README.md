# Commodity Agent

Полуавтоматический AI-агент для проработки международных сырьевых сделок.

**Текущий этап:** Этап 8 (Controlled automation) — MVP завершён

## Быстрый старт

```bash
cp .env.example .env   # опционально: для подключения OpenAI
docker compose up --build
```

После запуска:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs

### Учётные данные по умолчанию

| Поле | Значение |
|------|----------|
| Email | `admin@localhost` |
| Пароль | `changeme` |

## Локальная разработка без Docker

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Запустите PostgreSQL и обновите DATABASE_URL в .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

### Тесты

```bash
cd backend
export TEST_DATABASE_URL=postgresql://commodity:commodity@localhost:5432/commodity_agent_test
pytest -v
```

Создайте тестовую БД:

```sql
CREATE DATABASE commodity_agent_test;
```

## API Endpoints

| Method | Path | Описание |
|--------|------|----------|
| GET | `/health` | Health check |
| POST | `/auth/login` | Вход |
| POST | `/auth/logout` | Выход |
| GET | `/auth/me` | Текущий пользователь |
| PATCH | `/auth/me` | Обновить timezone |
| GET | `/products` | Список товаров (SN500, SN150) |
| GET | `/opportunities` | Список возможностей |
| POST | `/opportunities` | Создать buyer-led возможность |
| GET | `/opportunities/{id}` | Детали возможности |
| PATCH | `/opportunities/{id}` | Обновить возможность |
| POST | `/opportunities/{id}/sources` | Загрузить PDF |
| GET | `/opportunities/{id}/sources` | Список источников |
| POST | `/opportunities/{id}/convert` | Конвертировать в Deal |
| GET | `/deals` | Список сделок |
| GET | `/deals/{id}` | Детали сделки |
| POST | `/deals/{id}/requirements` | Создать Requirement |
| GET | `/deals/{id}/requirements` | Список требований |
| PATCH | `/requirements/{id}` | Обновить Requirement |
| GET | `/settings/ai-budget` | Настройки AI-бюджета |
| PATCH | `/settings/ai-budget` | Обновить AI-бюджет |
| GET | `/settings/ai-usage` | Статистика расходов AI |
| POST | `/sources/{id}/extract` | AI-извлечение из Source |
| GET | `/sources/{id}/extraction` | Последний результат извлечения |
| POST | `/opportunities/{id}/apply-extraction` | Применить извлечение |
| POST | `/opportunities/{id}/import-url` | Импорт публичной HTML-страницы |
| POST | `/opportunities/{id}/import-eml` | Импорт .eml |
| GET | `/research-campaigns` | Список исследовательских кампаний |
| POST | `/research-campaigns` | Создать ResearchCampaign |
| GET | `/research-campaigns/{id}` | Детали кампании |
| POST | `/research-campaigns/{id}/run` | Запустить поиск цепочки |
| GET | `/research-campaigns/{id}/leads` | Лиды (buyers/suppliers/routes) |
| POST | `/research-campaigns/{id}/outreach` | Сгенерировать черновики писем |
| GET | `/research-campaigns/{id}/outreach` | Список черновиков |
| POST | `/research-campaigns/outreach/{id}/mark-sent` | Отметить отправку вручную |
| POST | `/research-campaigns/{id}/import-response` | Импорт ответа (.eml/PDF/text) |
| GET | `/research-campaigns/{id}/facts` | CommercialFacts кампании |
| GET | `/research-campaigns/{id}/viability` | Отчёт viability |
| POST | `/research-campaigns/{id}/create-opportunity` | Создать Opportunity из кампании |
| GET | `/counterparties` | Список контрагентов |
| POST | `/counterparties` | Создать контрагента |
| POST | `/deals/{id}/parties` | Добавить сторону в сделку |
| POST | `/deals/{id}/rfqs` | Создать RFQ из шаблона |
| POST | `/rfqs/{id}/send` | Отправить утверждённый RFQ (mock email) |
| GET | `/inbox` | Связанные входящие/исходящие |
| GET | `/inbox/unlinked` | Несвязанные письма |
| POST | `/inbox/import-eml` | Импорт .eml в inbox |
| POST | `/messages/{id}/link` | Привязать письмо к RFQ |
| GET | `/deals/{id}/supply-offers` | Котировки поставщиков |
| POST | `/supply-offers/{id}/confirm` | Подтвердить извлечение котировки |
| GET | `/deals/{id}/configurations` | Варианты поставки |
| POST | `/deals/{id}/configurations` | Создать конфигурацию из SupplyOffer |
| POST | `/configurations/{id}/recalculate` | Пересчитать экономику (CURRENT) |
| POST | `/configurations/{id}/confirm` | Сохранить сценарий CONFIRMED |
| POST | `/configurations/{id}/transport-legs` | Добавить транспортное плечо |
| POST | `/configurations/{id}/service-quotes` | Добавить котировку услуги |
| GET | `/deals/{id}/offers` | Оферты покупателю |
| POST | `/deals/{id}/offers` | Создать оферту из конфигурации |
| POST | `/offers/{id}/submit-for-approval` | Оферта на approval |
| POST | `/offers/{id}/approve` | Утвердить оферту |
| POST | `/offers/{id}/send` | Отправить оферту (mock email) |
| GET | `/monitoring-rules` | Правила мониторинга |
| POST | `/monitoring-rules` | Создать правило |
| POST | `/monitoring-rules/{id}/run` | Запустить опрос источника |
| GET | `/monitoring-runs/{id}` | Результат запуска |
| POST | `/opportunities/supplier-led` | Создать supplier-led возможность |
| POST | `/supply-offers/{id}/supplier-led` | Supplier-led из подтверждённого SupplyOffer |
| GET | `/opportunities/{id}/supplier-lead` | Контекст, совпадения, сравнение рынка |
| POST | `/opportunities/{id}/match-buyer-needs` | Сопоставить с buyer needs |
| POST | `/supplier-lead-matches/{id}/build-route` | Построить исполнимый маршрут (оценка) |
| POST | `/supplier-lead-matches/{id}/draft-outreach` | Черновик письма покупателю (без отправки) |
| GET | `/settings/automation` | Настройки авто follow-up |
| PATCH | `/settings/automation` | Обновить настройки автоматизации |
| POST | `/automation/run` | Запустить авто follow-up (NON_BINDING) |
| GET | `/automation/runs` | История запусков |
| GET | `/automation/actions` | Журнал авто-действий |
| POST | `/automation/validate` | Проверка допустимости авто-действия |

## UI

- `/opportunities` — buyer-led и supplier-led возможности, мониторинг (пропущенные)
- `/opportunities/{id}` — AI-уточнение продукта, для `SUPPLIER_OFFER`: сопоставление, маршрут, outreach-черновик
- `/research` — Chain Discovery Pilot (создание кампании, поиск, outreach, viability)
- `/monitoring` — мониторинг источников, healthcheck, запуск, публикации → возможности
- `/automation` — настройки и запуск auto follow-up RFQ, журнал действий
- `/products` — открытый каталог товаров со спецификацией (пустой / частичный / полный)
- `/deals/{id}` — сделка: требования, стороны, RFQ, экономика, **оферта**
- `/inbox` — входящие письма, unlinked inbox, ручная привязка
- `/settings` — AI-бюджет

## AI (Этап 1b + Intelligence)

По умолчанию используется `AI_PROVIDER=mock` (без OpenAI ключа). Mock возвращает детерминированные ответы для base oil / SN500 — подходит для разработки и демо.

### Локально (backend/.env)

```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_DEFAULT_MODEL=gpt-4o-mini
OPENAI_FALLBACK_MODEL=gpt-4o
```

Если `AI_PROVIDER=openai`, но ключ пустой — система автоматически переключится на mock.

### Docker (рекомендуется)

1. Скопируйте шаблон:
   ```bash
   cp .env.example .env
   ```
2. Откройте `.env` и укажите:
   ```env
   AI_PROVIDER=openai
   OPENAI_API_KEY=sk-ваш-ключ
   ```
3. Перезапустите backend:
   ```bash
   docker compose restart backend
   ```

`docker-compose.yml` читает переменные из корневого `.env`. Ключ **не** хранится в compose-файле.

Если `AI_PROVIDER=openai`, но ключ пустой — система автоматически переключится на mock.

### Где используется AI

| Операция | UI | Операция в бюджете |
|----------|-----|-------------------|
| Извлечение из документов | `/opportunities/{id}` | extraction |
| Уточнение продукта | `/opportunities/{id}` → «Разрешить продукт» | matching |
| Обогащение контрагента | `/counterparties/{id}` → «Обогатить профиль» | research |

Лимиты и расход — `/settings` (AI-бюджет). При превышении лимита API вернёт `402 Payment Required`.

### Intelligence layer (Этап 9)

- **Product resolution** — примерное описание → нормализованный продукт из каталога + spec values (viscosity, flash point и т.д.), с ручным подтверждением
- **Counterparty enrichment** — AI извлекает capabilities (PRODUCT, FREIGHT, TERMINAL…) и контактные подсказки из текста/профиля

Без API-ключа mock-сценарии покрывают оба потока (см. `backend/tests/test_intelligence.py`).

## Документация

- `PRODUCT_SPEC.md` — продуктовые требования (v3.6)
- `ARCHITECTURE.md` — архитектура и ER-диаграмма
- `DEVELOPMENT_PLAN.md` — план разработки
- `AGENTS.md` — правила для Cursor

## Известные ограничения (Этап 8 / MVP)

- Email/Offer через mock provider
- FX — reference rates-заглушка
- PDF оферты не генерируется
- Disclosure — базовый snapshot, без полного UI контроля
- Финансирование упрощено
- Sensitivity и CONSERVATIVE/TARGET не в UI
- Мониторинг: только MOCK-коннектор (JSON feed), без APScheduler/cron
- RSS и STATIC_HTML коннекторы не реализованы
- Реальный источник MMTC/RCF/NFL не подключён
- Supplier-led: сопоставление только по данным в системе (opportunities + requirements)
- Фрахт и сравнение рынка — оценочные (ESTIMATE), без внешних индексов
- Outreach-черновик не отправляется автоматически (требует ручного шага)
- Автоматизация: только RFQ follow-up (NON_BINDING/INFORMATIONAL), без cron — ручной запуск или внешний scheduler
- Offer/RFQ первичная отправка всегда требует approval

## Структура

```text
backend/     FastAPI + SQLAlchemy + Alembic
frontend/    Next.js + TypeScript
docs/        Дополнительная документация
```
