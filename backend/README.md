# Backend (FastAPI) — Mitra

Реалізація схем з дошки Miro: доменна модель («Діаграма класів»), таблиці («Схема БД»), REST API за модулями,
життєвий цикл заходу, правила Risk Flags, звіт за півріччя для Порталу НАЗК.

## Локальний запуск
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate      # Windows; Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest -q                   # тести AI + e2e повного циклу заходу
```
- Змінні беруться з кореневого `.env` (див. `../.env.example`).
- За замовчуванням — SQLite у `backend/data/app.db`; PostgreSQL — через `DATABASE_URL` (у docker-compose — PostgreSQL).
- При першому старті порожня БД заповнюється **синтетичним набором організаторів** (Завдання 2,
  `app/datasets/zavdannia-2/`): 14 підрозділів, 19 користувачів, 14 ризиків, 50 заходів, звіти за І півріччя 2026,
  41 підтвердний матеріал, журнал дій. «Сьогодні» закріплюється на дату зрізу набору — 06.07.2026
  (`DEMO_TODAY` має пріоритет). `DEMO_DATASET=false` — власний демо-seed (3 розділи, 22 заходи, 8 ризиків).
  Щоб перестворити — видаліть `backend/data/`.
- Swagger: http://localhost:8000/api/docs
- Фронтенд (`npm run dev` у `frontend/`) проксує `/api/*` на `localhost:8000`.

## Авторизація (токен)
Кожен користувач має персональний токен; у БД зберігається лише sha256 токена.
- `POST /api/auth/login` `{"token": "..."}` → користувач і сеанс. **Браузер** отримує сеанс у cookie `mitra_session`
  (`HttpOnly`, `Secure`, `SameSite=Strict`): скрипти сторінки його не бачать, фронт у `localStorage` токенів не тримає.
  Запити, що змінюють дані, фронт шле із заголовком `X-Requested-With` — без нього запит за cookie відхиляється (захист від CSRF).
  Вихід — `POST /api/auth/logout`.
- **Скрипти й інтеграції** беруть `sessionToken` з відповіді входу (або персональний токен) і шлють
  `Authorization: Bearer <token>`; оновлений токен сеансу приходить у заголовку `X-Session-Token`.
- Сеанс діє `SESSION_HOURS` годин (за активності подовжується, але не довше `SESSION_MAX_DAYS` від входу) і стає недійсним
  після перевипуску персонального токена. Підписується окремим ключем `SESSION_SECRET` (обовʼязковий: без нього сервер
  не стартує), тож його можна змінити, не чіпаючи `REPORT_SECRET` і перевірку виданих звітів за QR. `GET /api/auth/me`.
- Персональний токен, виданий адміністратором, діє `TOKEN_DAYS` днів (90 за замовчуванням, `tokenExpiresAt` у відповіді); сеанс не живе довше за токен. Демо-токени строку не мають.
- Новий користувач: `POST /api/admin/users` повертає `token` один раз; перевипуск — `POST /api/admin/users/{id}/token` (токен іншого адміністратора — лише з `X-Admin-Password`).
- Надання або зняття ролі `ADMIN` (створення адміністратора, зміна ролі, видалення адміністратора) потребує секретного пароля: поле `adminPassword` у тілі або заголовок `X-Admin-Password` для `DELETE`. Хеш задається в `ADMIN_GRANT_HASH` (`.env`); у коді пароля немає, і поки хеш не задано, надання ролі `ADMIN` вимкнено.
- У Swagger — кнопка **Authorize**.

Демо-акаунти (синтетичні дані). Вбудованих токенів немає: токен акаунта — `demo-<імʼя>-<12 символів HMAC>`
від `DEMO_TOKEN_SECRET`, свій для кожного розгортання. Без `DEMO_TOKEN_SECRET` демо-дані не завантажуються (сервер
не стартує з поясненням). З `DEMO_LOGIN=true` сторінка входу показує акаунти кнопками (`GET /api/auth/demo-accounts`);
токен окремого акаунта: `DEMO_TOKEN_SECRET=… python -c "from app.auth import demo_token; print(demo_token('coord'))"`.

#### Набір організаторів (за замовчуванням)

Синтетичний набір Завдання 2: стан на 06.07.2026, звітний період — І півріччя 2026.

| Імʼя | Роль | Посада / підрозділ |
|---|---|---|
| `admin` | Адміністратор | Адміністратор системи |
| `coord` | Координатор | Головний спеціаліст сектору з питань запобігання та виявлення корупції |
| `head` | Керівник | Керівник відомства |
| `head-sector` | Керівник | Завідувач сектору з питань запобігання та виявлення корупції |
| `analyst` | Аналітик | Аналітик Управління внутрішнього аудиту |
| `ex-p01` | Виконавець | Сектор з питань запобігання та виявлення корупції |
| `ex-p02` | Виконавець | Департамент кадрового забезпечення |
| `ex-p03` | Виконавець | Департамент закупівель |
| `ex-p04` | Виконавець | Фінансово-економічний департамент |
| `ex-p05` | Виконавець | Управління матеріально-технічного забезпечення |
| `ex-p06` | Виконавець | Юридичний департамент |
| `ex-p07` | Виконавець | Департамент освіти і науки |
| `ex-p08` | Виконавець | Управління цифрової трансформації |
| `ex-p09` | Виконавець | Управління внутрішнього аудиту |
| `ex-p10` | Виконавець | Управління майна і землекористування |
| `ex-p11` | Виконавець | Управління комунікацій |
| `ex-p12` | Виконавець | Військовий навчальний заклад «Умовний» |
| `ex-p13` | Виконавець | Військово-медичний центр «Умовний» |
| `ex-p14` | Виконавець | Державне підприємство «Умовний ремонтний завод» |

#### Власний демо-seed (`DEMO_DATASET=false`)

| Імʼя | Роль |
|---|---|
| `admin` | Адміністратор |
| `coord` | Координатор |
| `head` | Керівник |
| `analyst` | Аналітик |
| `ex-proc` | Виконавець · закупівлі |
| `ex-fin` | Виконавець · фінанси |
| `ex-hr` | Виконавець · персонал |
| `ex-com` | Виконавець · комунікації |
| `ex-log` | Виконавець · логістика |
| `ex-legal` | Виконавець · юридичне |
| `ex-it` | Виконавець · ІТ |
| `ex-aud` | Виконавець · внутрішній аудит |

Ролі: `EXECUTOR`, `COORDINATOR`, `HEAD`, `ANALYST`, `ADMIN`. Матриця прав описана в `app/auth.py`: адміністратор веде облікові записи і не працює з предметними даними; аналітика доступна ролі `ANALYST`; рекомендації бачать координатор, керівник і аналітик, а рішення ухвалює керівник.

## Структура
```
app/
  models.py        ORM = таблиці зі схеми БД + методи з діаграми класів (isOverdue, isImproved, toNazkState…)
  enums.py         MeasureStatus, FlagType, Role, … ; назви 3 розділів НАЗК
  schemas/domain.py  DTO (JSON у camelCase)
  auth.py          Bearer-токен → User, RBAC, «захід свій»
  audit.py         журнал дій з ланцюжком хешів (prevHash → hash), перевірка цілісності
  services/
    measures.py    паспорт програми, CRUD заходів, життєвий цикл (submit/approve/return), періоди-півріччя
    control.py     Risk Flags engine (R1–R6), рекомендації за правилами, нагадування, щоденна задача 06:00
    reports.py     звіт НАЗК (JSON/CSV/DOCX/PDF/XLSX), друкована форма (HTML), аналітична довідка (правила I1–I7)
    analytics.py   аналітика програми: KPI, тренди статусів і Risk Flags, динаміка ризиків, експорт
    performance.py аналітика у двох режимах: основний (висновок, прогрес) і розширений для аудиту
    exporters.py   генерація XLSX (openpyxl), DOCX (python-docx), CSV
    notify.py      доставка нагадувань e-mail (SMTP)
    importer.py    імпорт набору даних з JSON (замість seed), CLI
    dashboards.py  кабінет виконавця, панель координатора, Executive Dashboard, карта підрозділів
    storage.py     write-once сховище файлів (замінник MinIO Object Lock), sha256
    seed.py        синтетичні демо-дані
  llm.py, routers/ai.py  клієнт локальної LLM
  routers/         REST API (нижче)
```

## Ендпоінти (усі під `/api`)
| Модуль | Метод і шлях | Опис |
|---|---|---|
| Програма | `GET/POST /programs`, `GET /programs/{id}` | реєстр програм |
| | `GET /programs/{id}/passport` | електронний паспорт: 3 розділи → заходи, ризики, строки, відповідальні |
| | `POST /programs/{id}/approve` | затвердження (DRAFT → PLANNED → IN_PROGRESS) |
| Заходи | `GET /measures?mine&programId&sectionId&orgUnitId&riskId&status&overdue&q` | список (виконавець бачить лише свої) |
| | `POST /measures`, `GET/PATCH /measures/{id}` | створення / картка / редагування |
| | `POST /measures/{id}/progress` | проміжний результат |
| | `POST /measures/{id}/submit` (multipart: `resultDescription` або `nonExecutionReason`, `files[]` + `documentTypes[]` і `documentDates[]` на кожен файл, `indicatorValue` — факт кількісного індикатора виконання, обовʼязковий при «Виконано») | внесення за один крок → ON_REVIEW, повертає `hints`; необовʼязковий `aiDraftKey` (з `/ai/intake/report`) — у журналі `submit` видно, чи змінено пропозицію (`aiDraftEdited`) |
| | `POST /measures/{id}/approve` (`comment`, `indicatorValue?`) | погодження → DONE / NOT_DONE |
| | `POST /measures/{id}/return` (`comment` обовʼязковий) | повернення на доопрацювання |
| | `GET/POST /measures/{id}/evidence`, `GET …/evidence/{eid}/download` | підтвердні матеріали з типом і датою документа (обовʼязкові), **без DELETE**, перевірка sha256 |
| | `POST /measures/{id}/deadline-changes` `{newDeadline, reason}` | лише координатор; внутрішнє перенесення строку (строк у програмі не змінюється), ≥ 2 — прапорець R6a |
| | `GET /measures/{id}/history`, `GET /measures/{id}/periods` | історія з журналу дій, півріччя |
| Ризики | `GET/POST /risks`, `GET /risks/{id}` | реєстр корупційних ризиків (поля словника: процес, зміст, джерела, наявні заходи контролю, власник) і KRI в одному запиті (`indicator`); рівень має відповідати балу x·y (інакше 422), без рівня — рахується з балу; код унікальний (409) |
| | `PATCH /risks/{id}` `{probability, impact, justification}` | координатор; переоцінка робочою групою, рівень з балу, запис у журнал дій |
| | `GET/POST /indicators`, `GET/POST /indicators/{id}/values` | індикатори та історія значень |
| Контроль | `GET /flags?status&type&programId&measureId`, `POST /flags/{id}/resolve` | Risk Flags (FORMAL_CLOSURE знімає лише керівник) |
| | `POST /flags/evaluate` | запустити щоденну задачу вручну |
| Дашборди | `GET /dashboard/executor`, `/dashboard/coordinator`, `/dashboard/executive`, `/dashboard/units/{id}` | панелі за ролями |
| | `GET /reminders` | нагадування поточного користувача (з `deliveries` — доставка e-mail) |
| Рекомендації | `GET /recommendations`, `POST /{id}/accept` (`responsibleId`, `dueDate`, `text?`), `POST /{id}/reject`, `POST /{id}/complete` (`comment`) | перегляд: координатор, керівник, аналітик; рішення ухвалює керівник; `text` — власне формулювання; прийняту рекомендацію закриває відповідальний або керівник. Відхилена не пропонується знову, доки відкритий прапорець, через який її сформовано |
| Звіти | `POST /reports/generate` (`programId`, `period`=`2026-H2`, `type`=NAZK/PRINT/INTERNAL), `GET /reports` | |
| | `GET /reports/{id}/nazk?format=json\|csv`, `GET /reports/{id}/print` | поля Порталу НАЗК / друкована форма |
| | `GET /reports/{id}/internal` | аналітична довідка (для `type=INTERNAL`): висновки, показники, ризики, рекомендації |
| | `GET /reports/{id}/export?format=docx\|pdf\|xlsx` | DOCX чи PDF (форма НАЗК або довідка) / XLSX. Усі завантаження (і `nazk`, `print`) віддають копії, зафіксовані при генерації (`report_files`, хеші в журналі, дія `issue_copies`): кожне завантаження побайтово однакове |
| | `GET /reports/{id}/integrity` | SHA-256 знімка, підпис HMAC (`REPORT_SECRET`), посилання і QR (SVG) для перевірки |
| | `GET /reports/{id}/verify?h=…&sig=…` | **публічно, без токена**: перевірка справжності за QR (`/verify` на фронті): HMAC-підпис, хеш вмісту звіту і sha256 збереженого файлу проти запису `generate` у журналі дій |
| | `GET /reports/copies/check?sha256=…&id=…` | **публічно**: чи є файл копією, виданою системою (хеш рахує браузер, файл не надсилається); `id` обмежує пошук одним звітом |
| | `POST /reports/{id}/sign` | підписати звіт, сформований до підписів, і зафіксувати його копії |
| Аналітика | `GET /analytics/summary?programId` | основний режим: висновок за правилом, прогрес, розділи, найближчі строки, що потребує уваги. Аналітик — уся програма; керівник — лише його підрозділ із підпорядкованими |
| | `GET /analytics/performance?programId&period&orgUnitId&userId`, `GET /analytics/performance/export` | розширений режим: лічильники за звітними завданнями (захід × півріччя) у розрізі підрозділів, виконавців і перевіряючих, реєстр завдань, хронологія подань, погоджень і повернень з коментарями; XLSX з тими самими фільтрами. Аналітик — уся програма; керівник — лише свій підрозділ (інший підрозділ чи особа у фільтрі → 403) |
| | `GET /analytics/peers?programId` | виконавець: власна статистика і статистика колег, з якими він виконує спільні заходи; лише числа — без назв їхніх заходів, коментарів, дат і ідентифікаторів |
| | `GET /analytics/overview?programId&weeks`, `GET /analytics/export?format=xlsx\|csv\|json` | аналітик: KPI, тренди статусів і Risk Flags, динаміка ризиків за індикаторами (вкладка «Динаміка»). Координатор і адміністратор аналітики не мають |
| Аудит | `GET /audit?entity&entityId&userId`, `GET /audit/verify` | журнал дій, перевірка ланцюжка хешів |
| Адмін | `GET/POST /admin/users`, `PATCH /admin/users/{id}`, `DELETE /admin/users/{id}`, `POST /admin/users/{id}/token`, `GET/POST /admin/org-units`, `GET /admin/dictionaries` | `DELETE` відкликає токен і позначає запис видаленим (запис лишається для журналу дій, персональні призначення переходять на підрозділ); себе видалити не можна |
| | `PUT /admin/users/{id}/contacts` | контакти користувача для нагадувань |
| | `POST /admin/import?dryRun` | імпорт набору даних (формат нижче) |
| Auth | `POST /auth/login`, `GET /auth/me`, `GET/PUT /auth/me/contacts` | контакти: `[{channel: EMAIL, address}]` |
| Покриття | `GET /programs/{id}/coverage` | координатор, керівник, аналітик; прогалини C1–C3: ризик без заходів, захід розділу 2 без ризику, без індикатора |
| AI | `GET /ai/status` | будь-який автентифікований користувач (`status.enabled` — стан вмикача); локальна LLM (Ollama або OpenAI-сумісний сервер через `LLM_BASE_URL`), лише підказки |
| | `POST /ai/chat`, `POST /ai/embed` | діагностика моделі, лише адміністратор: предметні ШІ-функції мають власні ендпоінти з перевірками |
| | `POST /ai/measures/{id}/rewrite` (`text`) | виконавець заходу: чіткіший опис результату; `text` повертається, лише якщо не додає чисел і проходить правило R4, інакше `null` і `note` з причиною |
| | `POST /ai/recommendations/{id}/suggest` | пропозиція моделі до рекомендації (координатор, керівник, аналітик): `text`, `steps`, `rationale`; зберігається в `basis.aiSuggestions`, сама рекомендація не змінюється |
| | `POST /ai/intake/report` (multipart: `file`, `period?`) | виконавець; звіт за зразком A (`docs/zrazky/`, DOCX/XLSX/PDF з текстом/TXT) → чернетка «внесення за один крок» для одного з **власних** заходів у редагованому статусі: `measureId`, `candidates[]`, `outcome` (`done`/`not_done`), `text`, джерело кожного (`document`/`rule`/`model`), `hints`, `warnings`, `draftKey`. Статус і файли не змінюються; не за зразком → 422 зі списком `missingFields` |
| | `POST /ai/intake/measure` (multipart: `file`, `programId`) | координатор; картка заходу за зразком B → чернетка `MeasureIn` + `fields{name: {value, source}}`, `warnings` (розділ 2 без ризику, зайнятий номер, невідомий підрозділ), `similar[]`. Захід не створюється |
| | `POST /ai/risks/{id}/measure-draft` `{programId}` | координатор; чернетка заходу для ризику без заходів (C1) у формі `MeasureDraft`: назву і документи пропонує модель, решта — правила; 503, якщо ШІ вимкнено |
| | `POST /ai/risks/{id}/explain` | координатор, керівник, аналітик; пояснення стану ризику з посиланнями `[n]` (`references`: ризик, індикатори, заходи, сигнали, прапорці); переказ моделі лише за перевіркою джерел і чисел, інакше `ruleText` |
| | `POST /ai/periods/{id}/evidence-check` | координатор, керівник, аналітик; правила V1–V3 щодо підтвердних файлів + порада з дослівними цитатами; статус не змінюється |
| | `POST /ai/ask` `{question}` | усі, крім адміністратора; відповідь по даних у межах прав ролі з посиланнями на записи |
| | `GET /ai/chats`, `POST /ai/chats` `{title?}` | усі, крім адміністратора; власні розмови з асистентом (`AiChatSummary`: `id`, `title`, `messageCount`, `createdAt`, `updatedAt`), нові першими; без назви — «Нова розмова», назва береться з першого питання |
| | `GET /ai/chats/{id}`, `PATCH /ai/chats/{id}` `{title}`, `DELETE /ai/chats/{id}` | власник розмови (чужа → 404); `AiChatOut` = summary + `messages[]` (`id`, `role` user/assistant, `content`, `answerSource`, `references`, `model`, `modelUsed`, `createdAt`) + `disclaimer`; DELETE мʼяке (204), питання лишаються в журналі |
| | `POST /ai/chats/{id}/messages` `{question}` | власник; як `/ai/ask`, але з урахуванням 3 останніх обмінів: попередні питання і записи останньої відповіді допомагають зрозуміти уточнення, факти — лише з поточних записів; повертає оновлений `AiChatOut` (або 202 з `jobId`); понад 200 повідомлень → 409 |
| | `GET /admin/settings/ai`, `PUT /admin/settings/ai` `{enabled}` | адміністратор; вмикач ШІ (у журналі); `AI_ENABLED=false` у середовищі не перевизначається (409) |
| Інше | `GET /health` | |

## Внесення документом (зразки A/B) — контракт для фронтенду

Бекенд готовий, UI — трек 2.8 у `docs/tracks.md` (фронтенд-команда). Зразки і поля: `docs/zrazky/README.md`, файли-зразки там само.

**A. Звіт виконавця → `SubmitForm`.** `POST /ai/intake/report` (multipart `file`, `period?`), роль EXECUTOR.
```json
{"measureId": "uuid|null", "period": "2026-H2", "measureSource": "document|rule|model|null",
 "candidates": [{"measureId": "uuid", "code": "3.2", "title": "…", "period": "2026-H2", "score": 0.93, "reason": "…"}],
 "outcome": "done|not_done|null", "outcomeSource": "rule|model|null",
 "text": "…", "textSource": "document|model", "documentText": "…",
 "hints": ["…"], "warnings": ["…"], "fileName": "zvit.docx", "fileSha256": "…",
 "draftKey": "hex|null", "model": "gemma3:4b", "modelUsed": false, "disclaimer": "…"}
```
- `measureId = null` → користувач обирає захід із `candidates`; `outcome = null` → обирає стан сам.
- `done` → `text` у поле «Опис результату» (`resultDescription`), `not_done` → «Причини невиконання» (`nonExecutionReason`).
- Перетягнутий файл додати до `files[]` форми; на сервер він потрапляє лише разом із `submit`. У `submit` передати `aiDraftKey = draftKey`.
- `textSource = model` → бейдж «Пропозиція моделі» і кнопка «Повернути текст документа» (`documentText`).
- Помилки: 415 (формат), 413 (розмір), 422 `{"detail": {"message", "missingFields": []}}` (не за зразком), 409 (немає заходів, що очікують звіту).

**B. Картка заходу → `MeasureForm`.** `POST /ai/intake/measure` (multipart `file`, `programId`), роль COORDINATOR.
```json
{"measure": {"sectionId": "uuid|null", "code": "2.9", "title": "…", "isPermanent": false, "plannedDeadline": "2026-12-31",
             "riskId": "uuid|null", "indicatorId": "uuid|null", "requiredEvidence": "…",
             "assignments": [{"orgUnitId": "uuid", "isResponsible": true}]},
 "fields": {"title": {"value": "…", "source": "document", "documentValue": "…"}, "section": {…}, "code": {…},
            "plannedDeadline": {…}, "isPermanent": {…}, "assignments": {…}, "risk": {…}, "indicator": {…}, "requiredEvidence": {…}},
 "warnings": ["…"], "similar": [{"measureId": "uuid", "code": "2.3", "title": "…", "score": 0.8}],
 "fileName": "kartka.xlsx", "model": "gemma3:4b", "modelUsed": true, "disclaimer": "…"}
```
- `measure` має форму `MeasureIn`: після перевірки координатор відправляє її наявним `POST /measures`.
- Біля поля показати `fields[name].source` (з документа / за правилом / пропозиція моделі) і, якщо значення змінено, `documentValue`.

## Правила Risk Flags (явні, з поясненням у `facts` + `explanation`)
| Код | Тип | Умова |
|---|---|---|
| R1 | OVERDUE | строк минув, статус ≠ DONE, результат не подано |
| E1 | NO_EVIDENCE | виконано (або подано як виконаний) без документа визначеної форми |
| F1 / F2 | FORMAL_CLOSURE / WORSENING | захід розділу 2 виконано, а індикатор ризику пройшов < 10 % шляху / погіршився; до кінця лагу — попередньо (знімає лише керівник) |
| R4 | VAGUE_RESULT | опис схожий на назву (≥75%) або без числа/посилання |
| R5 | TARGET_MISSED | строк настав, а індикатор виконання нижче цілі |
| R6 | REPEATED_DELAY | у підрозділу ≥2 прострочені заходи за період |
| R6a | REPEATED_POSTPONEMENT | ≥ 2 рішення координатора про перенесення строку |
| R7a–R7e | DATE_OUT_OF_PERIOD, BACKDATED_EVIDENCE, NO_EXPLANATION, PREMATURE_DESCRIPTION | дата поза періодом; документи датовано пізніше за виконання; «Не виконано» без пояснення; опис до настання строку |

Повний опис — [docs/decision-rules.md](../docs/decision-rules.md); відповідність ключу організаторів (29 кейсів) перевіряє `tests/test_key_cases.py`.

Прапорці перевіряються після кожної зміни заходу та щодня о 06:00; статус заходу вони не змінюють.

## Аналітична довідка (`type=INTERNAL`) — висновки за правилами
| Код | Висновок | Рівень |
|---|---|---|
| I1 | частка виконаних, на перевірці, повернених, невиконаних | INFO |
| I2 | прострочені заходи | CRITICAL від 25% програми, інакше WARNING |
| I3 | зменшення ризиків за індикаторами; формальне закриття (усі заходи виконано, індикатор не покращився) | CRITICAL / WARNING / INFO |
| I4 | виконані заходи без підтвердних матеріалів | WARNING |
| I5 | частка повернень ≥ 30% | WARNING |
| I6 | середній час перевірки > 10 дн. | WARNING |
| I7 | підрозділи з ≥ 2 простроченими заходами (за абеткою, без рейтингу) | WARNING |

## Нагадування поза застосунком
Нагадування за 7/3/1 день створюються щоденною задачею; кожні `NOTIFY_INTERVAL_MINUTES` хвилин настали нагадування позначаються доставленими в застосунку і надсилаються на e-mail користувача через SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS`). Без `SMTP_HOST` нагадування лишаються лише в застосунку. Кожна спроба записується (`SENT` / `FAILED` / `SKIPPED` для старших за `NOTIFY_MAX_AGE_DAYS`), повторно на той самий канал нагадування не надсилається.

## Імпорт даних
JSON з розділами `orgUnits`, `users`, `risks` (з `indicators`), `indicators`, `programs` (з `measures`); посилання за природними ключами (назва підрозділу, `displayName`, код ризику, назва індикатора). Приклад: [`data/sample-import.json`](../data/sample-import.json). Повторний імпорт оновлює наявні записи; помилка посилання → нічого не зберігається.
- API: `POST /api/admin/import?dryRun=true` (адміністратор)
- CLI: `python -m app.services.importer ../data/sample-import.json [--dry-run]`
- Під час першого старту замість демо-seed: `IMPORT_FILE=../data/sample-import.json`

## Docker (весь стек з PostgreSQL)
З кореня репозиторію: `docker compose up --build` → http://localhost
