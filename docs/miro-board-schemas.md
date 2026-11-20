# Моніторинг виконання антикорупційної програми — схеми

Повна копія дошки Miro

---

# 1. Загальна логіка

## Архітектура системи

```mermaid
flowchart LR
classDef user fill:#B3E65F,stroke:#84AC43,color:#2F440B
classDef fe fill:#9CE6FF,stroke:#4FB1D3,color:#1C4657
classDef be fill:#FFE86D,stroke:#CBB333,color:#574900
classDef data fill:#B8ACFB,stroke:#7D6DD4,color:#231266
classDef ext fill:#DDDDD8,stroke:#A8A8A0,color:#434339
subgraph users [Користувачі]
u1[Виконавець]:::user
u2[Координатор]:::user
u3[Керівник]:::user
u4[Аналітик]:::user
u5[Адміністратор]:::user
end
subgraph front [Frontend SPA]
f1[Кабінет виконавця]:::fe
f2[Кабінет координатора]:::fe
f3[Executive Dashboard]:::fe
f4[Аналітика і звіти]:::fe
f5[Адмінка]:::fe
end
gw[API Gateway<br/>REST, JWT, RBAC, аудит]:::be
subgraph back [Backend сервіси]
b1[Program Register]:::be
b2[Activity і Evidence]:::be
b3[Deadline Control]:::be
b4[Risk Flags Engine]:::be
b5[Reporting Engine]:::be
b6[Audit Trail]:::be
b7[AI-помічник<br/>локальна модель, лише пропонує]:::be
end
subgraph store [Дані]
d1[(PostgreSQL)]:::data
d2[(MinIO<br/>Object Lock, файли незмінні)]:::data
d3[Планувальник задач]:::data
end
subgraph ext [Зовнішні системи]
e1[Keycloak SSO]:::ext
e2[Портал доброчесності НАЗК]:::ext
e3[СЕД відомства]:::ext
e4[Пошта]:::ext
end
u1 --> f1
u2 --> f2
u3 --> f3
u4 --> f4
u5 --> f5
f1 --> gw
f2 --> gw
f3 --> gw
f4 --> gw
f5 --> gw
gw -->|вхід| e1
gw --> b1
gw --> b2
gw --> b4
gw --> b5
gw --> b6
b1 --> d1
b2 --> d1
b2 -->|документи| d2
b4 --> d1
b6 --> d1
d3 --> b3
d3 --> b4
b3 -->|нагадування| e4
b5 -->|експорт| e2
b5 -->|паперова форма| e3
b7 -.->|підказки| b4
```

## Життєвий цикл заходу

```mermaid
flowchart LR
classDef general fill:#FFE86D,stroke:#CBB333,color:#574900
classDef decision fill:#9CE6FF,stroke:#4FB1D3,color:#1C4657
classDef terminator fill:#B3E65F,stroke:#84AC43,color:#2F440B
classDef problem fill:#FFB575,stroke:#CA7933,color:#542700
s0([Чернетка<br/>паспорт заповнює координатор]):::terminator
s1[Заплановано<br/>виконавець бачить захід]:::general
s2[В роботі<br/>проміжні результати]:::general
s3[На перевірці<br/>виконавець не редагує]:::general
s4{{Рішення координатора}}:::decision
s5[Повернено<br/>з обовʼязковим коментарем]:::general
s7([Виконано<br/>лише додавання документів]):::terminator
s10([Не виконано<br/>з поясненням причин]):::terminator
q{{Індикатор ризику змінився?}}:::decision
ok([Ризик зменшено]):::terminator
f1[Прапорець Прострочено<br/>статус не змінюється]:::problem
f2[Прапорець Формальне закриття<br/>знімає лише керівник]:::problem
perm[Постійний захід<br/>новий період щопівроку]:::general
s0 -->|паспорт затверджено| s1
s1 -->|настала дата початку| s2
s2 -->|опис і документи| s3
s3 --> s4
s4 -->|зауваження| s5
s5 -->|доповнено| s3
s4 -->|погоджено| s7
s7 --> q
q -->|так| ok
q -->|ні| f2
s2 -->|кінець періоду| s10
s5 -->|кінець періоду| s10
s2 -.->|строк минув| f1
s3 -.->|строк минув| f1
s5 -.->|строк минув| f1
s7 -.->|якщо постійний| perm
s10 -.->|якщо постійний| perm
perm -.-> s2
```

## Повний цикл роботи із заходом

```mermaid
sequenceDiagram
autonumber
actor K as Координатор
participant S as Система
actor V as Виконавець
actor H as Керівник
participant N as Портал НАЗК
K->>S: Створює паспорт програми і заходи
K->>S: Повʼязує захід з ризиком та індикатором
S->>V: Призначення і нагадування про строк
V->>S: Вносить результат і документи за один крок
S->>S: Хеш документа і запис у журнал дій
S->>S: Перевірка правил Risk Flags
alt Є зауваження
K->>V: Повертає на доопрацювання
V->>S: Доповнює результат
end
K->>S: Погоджує виконання
S->>H: Оновлений Executive Dashboard
H->>S: Приймає рекомендацію, призначає відповідального і строк
K->>S: Формує звіт за півріччя
S->>N: Дані у структурі полів Порталу
```

## Правила Risk Flags

```mermaid
flowchart LR
classDef general fill:#FFE86D,stroke:#CBB333,color:#574900
classDef decision fill:#9CE6FF,stroke:#4FB1D3,color:#1C4657
classDef terminator fill:#B3E65F,stroke:#84AC43,color:#2F440B
classDef problem fill:#FFB575,stroke:#CA7933,color:#542700
t([Зміна заходу або щоденний запуск о 06:00]):::terminator
r1{{Строк минув, а статус не Виконано?}}:::decision
r2{{Виконано, але немає документів?}}:::decision
r3{{Виконано, а індикатор ризику не змінився?}}:::decision
r4{{Опис повторює назву заходу, немає числа чи посилання?}}:::decision
r5{{Індикатор не досяг цілі на контрольну дату?}}:::decision
r6{{У підрозділу друге порушення строку за період?}}:::decision
f1[Прострочено]:::problem
f2[Немає підтвердження]:::problem
f3[Формальне закриття]:::problem
f4[Неінформативний опис]:::problem
f5[Невиконання показника]:::problem
f6[Повторне порушення строків]:::problem
out[RiskFlag: правило, дані, пояснення]:::general
end1([Черга координатора і Dashboard керівника]):::terminator
t --> r1
t --> r2
t --> r3
t --> r4
t --> r5
t --> r6
r1 -->|так| f1
r2 -->|так| f2
r3 -->|так| f3
r4 -->|так| f4
r5 -->|так| f5
r6 -->|так| f6
f1 --> out
f2 --> out
f3 --> out
f4 --> out
f5 --> out
f6 --> out
out --> end1
```

## Звіт за півріччя для Порталу НАЗК

```mermaid
flowchart TD
classDef general fill:#FFE86D,stroke:#CBB333,color:#574900
classDef decision fill:#9CE6FF,stroke:#4FB1D3,color:#1C4657
classDef terminator fill:#B3E65F,stroke:#84AC43,color:#2F440B
start([Координатор обирає півріччя]):::terminator
loop1[Для кожного заходу трьох розділів]:::general
q1{{Захід постійного характеру?}}:::decision
d1[Фактичний строк = 30 червня або 31 грудня]:::general
d2[Фактичний строк = дата погодження виконання]:::general
q2{{Плановий строк уже настав?}}:::decision
st1[Стан: Строк виконання не настав]:::general
q3{{Статус заходу}}:::decision
st2[Стан: Виконано, опис результату з системи]:::general
st3[Стан: Не виконано, пояснення причин]:::general
q4{{Програма містить інформацію з обмеженим доступом?}}:::decision
o1([Експорт у структурі полів Порталу]):::terminator
o2([Друкована форма для подання на папері]):::terminator
start --> loop1
loop1 --> q1
q1 -->|так| d1
q1 -->|ні| q2
q2 -->|ні| st1
q2 -->|так| d2
d1 --> q3
d2 --> q3
q3 -->|Виконано| st2
q3 -->|інше| st3
st1 --> q4
st2 --> q4
st3 --> q4
q4 -->|ні| o1
q4 -->|так| o2
```

---

# 2. Бекенд

## Діаграма класів (доменна модель)

```mermaid
classDiagram
direction TB
Program "1" *-- "3" Section : розділи
Program "*" --> "1" OrgUnit : орган
Section "1" *-- "*" Measure : заходи
Measure "*" --> "0..1" CorruptionRisk : усуває
CorruptionRisk "1" *-- "1..*" Indicator : вимірюється (KRI)
CorruptionRisk "*" --> "0..1" OrgUnit : власник
CorruptionRisk "1" *-- "*" Incident : інциденти
CorruptionRisk "1" *-- "*" RiskSignal : сигнали
Measure "*" --> "0..1" Indicator : оцінюється за (індикатор виконання)
Measure "1" *-- "*" DeadlineChange : перенесення строку
Indicator "1" *-- "*" IndicatorValue : історія
Measure "1" *-- "*" MeasureAssignment : виконавці
MeasureAssignment "*" --> "1" OrgUnit
MeasureAssignment "*" --> "0..1" User
User "*" --> "1" OrgUnit
Measure "1" *-- "1..*" MeasurePeriod : півріччя
MeasurePeriod "1" *-- "*" ProgressUpdate
MeasurePeriod "1" *-- "*" Evidence
MeasurePeriod "1" *-- "*" Approval
MeasurePeriod --> MeasureStatus
RiskFlag --> FlagType
Measure "1" *-- "*" Reminder
Measure "1" *-- "*" RiskFlag
Recommendation "*" --> "0..1" RiskFlag : на підставі
Report "*" --> "1" Program
AuditLogEntry "*" --> "1" User : автор
class Program:::core {
+id: UUID
+title: string
+periodStart: date
+periodEnd: date
+hasRestrictedInfo: bool
+status: ProgramStatus
+approve(): void
}
class Section:::core {
+id: UUID
+number: int 1..3
+title: string
}
class Measure:::core {
+id: UUID
+code: string
+title: string
+isPermanent: bool
+plannedDeadline: date
+indicatorText: string
+internalDeadline(): date
+isOverdue(): bool
}
class DeadlineChange:::ctrl {
+id: UUID
+decidedOn: date
+oldDeadline: date
+newDeadline: date
+reason: text
+decidedBy: UUID
}
class MeasurePeriod:::core {
+id: UUID
+period: HalfYear
+status: MeasureStatus
+actualDate: date
+resultDescription: text
+nonExecutionReason: text
+submit(): void
+approve(): void
+returnForRework(comment): void
+toNazkState(): string
}
class MeasureStatus:::core {
<<enumeration>>
DRAFT
PLANNED
IN_PROGRESS
ON_REVIEW
RETURNED
DONE
PARTIAL
NOT_DONE
}
class FlagType:::ctrl {
<<enumeration>>
OVERDUE
NO_EVIDENCE
FORMAL_CLOSURE
WORSENING
VAGUE_RESULT
TARGET_MISSED
REPEATED_DELAY
REPEATED_POSTPONEMENT
DATE_OUT_OF_PERIOD
BACKDATED_EVIDENCE
NO_EXPLANATION
PREMATURE_DESCRIPTION
}
class CorruptionRisk:::core {
+id: UUID
+code: string
+description: text
+process: string
+content: text
+sources: text
+existingControls: text
+probability: int 1..4
+impact: int 1..4
+level: RiskLevel
}
class Incident:::core {
+id: UUID
+occurredOn: date
+confirmed: bool
+source: string
}
class RiskSignal:::ctrl {
+id: UUID
+type: SignalType
+ruleCode: string
+facts: json
+status: FlagStatus
}
class Indicator:::core {
+id: UUID
+name: string
+unit: string
+baseline: decimal
+target: decimal
+direction: KriDirection
+weight: decimal
+lagMonths: int
+independent: bool
+targetDate: date
+baselineHash: string
+isImproved(): bool
}
class IndicatorValue:::core {
+id: UUID
+value: decimal
+measuredAt: date
+sourceEvidenceId: UUID
}
class OrgUnit:::people {
+id: UUID
+parentId: UUID
+name: string
}
class User:::people {
+id: UUID
+displayName: string
+role: Role
}
class MeasureAssignment:::people {
+isResponsible: bool
}
class ProgressUpdate:::exec {
+id: UUID
+statusFrom: MeasureStatus
+statusTo: MeasureStatus
+text: text
+createdAt: datetime
}
class Evidence:::exec {
+id: UUID
+fileName: string
+objectKey: string
+sha256: string
+docType: string
+documentDate: date
+version: int
+uploadedAt: datetime
}
class Approval:::exec {
+id: UUID
+decision: Decision
+comment: text
+createdAt: datetime
}
class Reminder:::ctrl {
+id: UUID
+sendAt: datetime
+channel: Channel
+sent: bool
}
class RiskFlag:::ctrl {
+id: UUID
+type: FlagType
+ruleCode: string
+facts: json
+status: FlagStatus
+explain(): string
}
class Recommendation:::ctrl {
+id: UUID
+text: text
+basis: json
+responsibleId: UUID
+dueDate: date
+status: RecStatus
}
class AuditLogEntry:::ctrl {
+id: UUID
+entity: string
+entityId: UUID
+action: string
+oldValue: json
+newValue: json
+at: datetime
+prevHash: string
}
class Report:::rep {
+id: UUID
+period: HalfYear
+type: ReportType
+fileKey: string
+generatedAt: datetime
+toNazkFields(): list
}
classDef core fill:#FFE86D,stroke:#CBB333,color:#574900
classDef people fill:#B3E65F,stroke:#84AC43,color:#2F440B
classDef exec fill:#9CE6FF,stroke:#4FB1D3,color:#1C4657
classDef ctrl fill:#FFB575,stroke:#CA7933,color:#542700
classDef rep fill:#B8ACFB,stroke:#7D6DD4,color:#231266
```

## Схема БД (PostgreSQL)

```mermaid
erDiagram
programs {
uuid id PK
uuid org_unit_id FK
text title
date period_start
date period_end
bool has_restricted_info
text status
}
sections {
uuid id PK
uuid program_id FK
int number
text title
}
measures {
uuid id PK
uuid section_id FK
uuid risk_id FK
uuid indicator_id FK
text code
text title
bool is_permanent
date planned_deadline
text indicator_text
}
deadline_changes {
uuid id PK
uuid measure_id FK
date decided_on
date old_deadline
date new_deadline
text reason
uuid decided_by FK
}
measure_periods {
uuid id PK
uuid measure_id FK
text period
text status
date actual_date
text result_description
text non_execution_reason
}
corruption_risks {
uuid id PK
uuid program_id FK
uuid owner_unit_id FK
text code
text description
text process
text content
text sources
text existing_controls
int probability
int impact
text level
}
incidents {
uuid id PK
uuid risk_id FK
date occurred_on
bool confirmed
text source
}
risk_signals {
uuid id PK
uuid risk_id FK
uuid indicator_id FK
text type
text rule_code
jsonb facts
text status
}
indicators {
uuid id PK
uuid risk_id FK
text name
numeric baseline
numeric target
text direction
numeric weight
int lag_months
bool independent
date target_date
}
indicator_values {
uuid id PK
uuid indicator_id FK
uuid source_evidence_id FK
numeric value
date measured_at
}
org_units {
uuid id PK
uuid parent_id FK
text name
}
users {
uuid id PK
uuid org_unit_id FK
text keycloak_id
text role
}
measure_assignments {
uuid measure_id FK
uuid org_unit_id FK
uuid user_id FK
bool is_responsible
}
progress_updates {
uuid id PK
uuid measure_period_id FK
uuid author_id FK
text status_to
text body
timestamptz created_at
}
evidence_files {
uuid id PK
uuid measure_period_id FK
text object_key
text sha256
text doc_type
date document_date
int version
timestamptz uploaded_at
}
approvals {
uuid id PK
uuid measure_period_id FK
uuid reviewer_id FK
text decision
text comment
}
risk_flags {
uuid id PK
uuid measure_id FK
text type
text rule_code
jsonb facts
text status
}
reports {
uuid id PK
uuid program_id FK
text period
text type
text file_key
}
audit_log {
bigint id PK
uuid user_id FK
text entity
uuid entity_id
text action
jsonb old_value
jsonb new_value
text prev_hash
timestamptz at
}
programs ||--|{ sections : "має"
sections ||--o{ measures : "містить"
corruption_risks ||--o{ measures : "усувається"
corruption_risks ||--|{ indicators : "вимірюється (KRI)"
corruption_risks ||--o{ incidents : "інциденти"
corruption_risks ||--o{ risk_signals : "сигнали"
org_units ||--o{ corruption_risks : "власник"
indicators ||--o{ measures : "індикатор виконання"
indicators ||--o{ indicator_values : "історія"
measures ||--o{ deadline_changes : "перенесення"
measures ||--o{ measure_assignments : "виконавці"
org_units ||--o{ measure_assignments : ""
org_units ||--o{ users : ""
measures ||--|{ measure_periods : "півріччя"
measure_periods ||--o{ progress_updates : ""
measure_periods ||--o{ evidence_files : ""
measure_periods ||--o{ approvals : ""
measures ||--o{ risk_flags : ""
programs ||--o{ reports : ""
users ||--o{ audit_log : "дії"
```

## REST API за модулями

```mermaid
flowchart LR
classDef general fill:#FFE86D,stroke:#CBB333,color:#574900
classDef mw fill:#9CE6FF,stroke:#4FB1D3,color:#1C4657
classDef data fill:#B8ACFB,stroke:#7D6DD4,color:#231266
req([HTTP запит з фронту]):::mw
mw1[JWT від Keycloak]:::mw
mw2[RBAC: роль і належність до заходу]:::mw
mw3[Audit interceptor: запис змін]:::mw
subgraph core_api [Програма і заходи]
p1["/programs<br/>GET, POST, GET /id/passport, POST /id/approve"]:::general
p2["/measures<br/>GET ?mine, POST, PATCH /id"]:::general
p3["/measures/id/submit, /approve, /return"]:::general
p4["/measures/id/evidence<br/>POST, GET, без DELETE"]:::general
p5["/risks, /indicators/id/values"]:::general
end
subgraph ctrl_api [Контроль і аналітика]
c1["/flags<br/>GET, POST /id/resolve"]:::general
c2["/dashboard/executor, /coordinator, /executive"]:::general
c3["/recommendations<br/>GET, POST /id/accept"]:::general
c4["/reports<br/>POST /generate, GET /id/nazk, /id/print"]:::general
c5["/audit?entity=..."]:::general
c6["/admin/users, /org-units, /dictionaries"]:::general
end
db[(PostgreSQL і MinIO)]:::data
req --> mw1
mw1 --> mw2
mw2 --> mw3
mw3 --> p1
mw3 --> p2
mw3 --> p3
mw3 --> p4
mw3 --> p5
mw3 --> c1
mw3 --> c2
mw3 --> c3
mw3 --> c4
mw3 --> c5
mw3 --> c6
p3 --> db
p4 --> db
c4 --> db
```

## Внесення результату виконавцем: що робить бекенд

```mermaid
sequenceDiagram
autonumber
participant F as Frontend
participant A as API
participant M as MeasureService
participant O as MinIO
participant D as PostgreSQL
participant L as AuditTrail
participant R as RiskFlagsEngine
F->>A: POST /measures/id/submit з описом і файлами
A->>A: Перевірка JWT, ролі і що захід свій
A->>M: submit(dto)
M->>O: putObject з Object Lock
O-->>M: objectKey
M->>M: sha256 кожного файлу
M->>D: Одна транзакція: evidence, progress_update, статус На перевірці
M->>L: append старе і нове значення, prevHash
M->>R: evaluate(measureId)
R->>D: INSERT risk_flags, якщо спрацювало правило
M-->>A: Оновлений захід і прапорці
A-->>F: 200 OK, картка На перевірці
```

---

# 3. Фронтенд

## Роутинг і доступ за ролями

```mermaid
flowchart LR
classDef exec fill:#FFE86D,stroke:#CBB333,color:#574900
classDef coord fill:#B3E65F,stroke:#84AC43,color:#2F440B
classDef head fill:#9CE6FF,stroke:#4FB1D3,color:#1C4657
classDef anal fill:#B8ACFB,stroke:#7D6DD4,color:#231266
classDef admin fill:#DDDDD8,stroke:#A8A8A0,color:#434339
login(["/login через Keycloak"])
role{{Роль користувача}}
subgraph r_exec [Виконавець]
e1["/my<br/>мої заходи, строки, нагадування"]:::exec
e2["/my/measures/:id<br/>картка і внесення за один крок"]:::exec
e3["/my/history<br/>історія і зауваження"]:::exec
end
subgraph r_coord [Координатор]
c1["/program<br/>паспорт програми"]:::coord
c2["/review<br/>черга на перевірку"]:::coord
c3["/measures/:id<br/>перевірка, погодження"]:::coord
c4["/flags<br/>Risk Flags"]:::coord
c5["/calendar<br/>контрольні строки"]:::coord
c6["/reports<br/>звіт НАЗК і друк"]:::coord
end
subgraph r_head [Керівник]
h1["/dashboard<br/>Executive Dashboard"]:::head
h2["/dashboard/units/:id<br/>деталізація по підрозділу"]:::head
h3["/recommendations<br/>прийняти або відхилити"]:::head
end
subgraph r_anal [Аналітик]
a1["/analytics<br/>тренди і динаміка ризиків"]:::anal
a2["/analytics/export"]:::anal
end
subgraph r_admin [Адміністратор]
d1["/admin/users"]:::admin
d2["/admin/org-units"]:::admin
d3["/admin/dictionaries<br/>реєстр ризиків, напрями"]:::admin
end
login --> role
role -->|виконавець| e1
role -->|координатор| c1
role -->|керівник| h1
role -->|аналітик| a1
role -->|адмін| d1
e1 --> e2
e1 --> e3
c1 --> c2
c2 --> c3
c1 --> c4
c1 --> c5
c1 --> c6
h1 --> h2
h1 --> h3
a1 --> a2
d1 --> d2
d1 --> d3
```

## Структура компонентів

```mermaid
flowchart TD
classDef shell fill:#9CE6FF,stroke:#4FB1D3,color:#1C4657
classDef page fill:#FFE86D,stroke:#CBB333,color:#574900
classDef comp fill:#B3E65F,stroke:#84AC43,color:#2F440B
classDef infra fill:#DDDDD8,stroke:#A8A8A0,color:#434339
app[App]:::shell
auth[AuthProvider<br/>Keycloak, токен]:::shell
guard[RoleGuard<br/>маршрути за роллю]:::shell
layout[Layout<br/>Sidebar за роллю, Topbar зі сповіщеннями]:::shell
api[API client і кеш запитів]:::infra
subgraph pages [Сторінки]
pg1[MyMeasuresPage]:::page
pg2[MeasureDetailsPage]:::page
pg3[ReviewQueuePage]:::page
pg4[ProgramPassportPage]:::page
pg5[ExecutiveDashboardPage]:::page
pg6[ReportsPage]:::page
end
subgraph shared [Спільні компоненти]
k1[MeasureCard]:::comp
k2[StatusBadge<br/>колір статусу]:::comp
k3[EvidenceUploader<br/>підказка, які документи потрібні]:::comp
k4[FlagList<br/>правило і пояснення]:::comp
k5[KpiTile і ProgressChart]:::comp
k6[RiskHeatMap<br/>без рейтингування]:::comp
k7[DeadlineCalendar]:::comp
k8[AuditTimeline]:::comp
end
app --> auth
auth --> guard
guard --> layout
layout --> pages
pages --> shared
pages --> api
```

## Юзер-флоу виконавця: внесення за один крок

```mermaid
flowchart LR
classDef general fill:#FFE86D,stroke:#CBB333,color:#574900
classDef decision fill:#9CE6FF,stroke:#4FB1D3,color:#1C4657
classDef terminator fill:#B3E65F,stroke:#84AC43,color:#2F440B
classDef problem fill:#FFB575,stroke:#CA7933,color:#542700
n1([Нагадування: до строку 3 дні]):::terminator
n2[Список Мої заходи<br/>кольори статусів]:::general
n3[Картка заходу]:::general
n4[Одна форма: статус, опис результату, файли]:::general
n5{{Опис має число або посилання і не повторює назву?}}:::decision
n6[Підказка: додай показник або документ]:::problem
n7{{Є обовʼязкові документи?}}:::decision
n8[Надіслати]:::general
n9([Статус На перевірці]):::terminator
n10[Повернено із зауваженням]:::problem
n1 --> n2
n2 --> n3
n3 --> n4
n4 --> n5
n5 -->|ні| n6
n6 --> n4
n5 -->|так| n7
n7 -->|ні| n6
n7 -->|так| n8
n8 --> n9
n9 -.->|координатор повернув| n10
n10 --> n4
```

## Що на якому дашборді

```mermaid
flowchart TD
classDef exec fill:#FFE86D,stroke:#CBB333,color:#574900
classDef coord fill:#B3E65F,stroke:#84AC43,color:#2F440B
classDef head fill:#9CE6FF,stroke:#4FB1D3,color:#1C4657
subgraph db_exec [Кабінет виконавця]
x1[Мої заходи на найближчі 30 днів]:::exec
x2[Повернені із зауваженнями]:::exec
x3[Прострочені]:::exec
end
subgraph db_coord [Панель координатора]
y1[Черга на перевірку]:::coord
y2[Risk Flags за типами]:::coord
y3[Прогрес за трьома розділами]:::coord
y4[Календар контрольних строків]:::coord
y5[Готовність звіту за півріччя]:::coord
end
subgraph db_head [Executive Dashboard]
z1[Загальний стан програми]:::head
z2[Критичні заходи]:::head
z3[Стан корупційних ризиків: до і після]:::head
z4[Карта ризику невиконання за підрозділами]:::head
z5[Найближчі контрольні строки]:::head
z6[Рекомендації на рішення]:::head
end
src[(Одні й ті самі дані заходів)]
src --> x1
src --> y1
src --> z1
```

---
