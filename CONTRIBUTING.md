## Дедлайни

| Коли | ? |
|---|---|
| 18.11, 10:00 | подача посилання на репозиторій через форму |
| 20.11, 23:59 | останній пуш коду в `main` |
| 21.11, ранок | звіт автоматичної перевірки від організаторів |
| 23.11, 10:00 | README, `docs/`, відео; змінювати можна лише `README.md`, `LICENSE`, `.env.example`, `docs/`, `presentation/` |
| 26.11, 18:00 | слайди фіналу в `presentation/` |

## Запуск

Спочатку в корені: `cp .env.example .env`

### Docker

| Що | Команда |
|---|---|
| весь стек | `docker compose up --build -d` |
| весь стек з GPU (NVIDIA) | `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d` |
| без Ollama (швидко, без моделей) | `docker compose up --build -d --no-deps backend frontend` |
| логи | `docker compose logs -f <ollama\|backend\|frontend>` |
| зупинити | `docker compose down` |

Відкрити http://localhost. Перший запуск Ollama качає моделі (~5 ГБ), стан: http://localhost/api/ai/status

GPU: на Linux потрібен `nvidia-container-toolkit`

### Без Docker

**Backend** http://localhost:8000/api/docs
```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** http://localhost:5173
```bash
cd frontend
npm install
npm run dev
```

## Гілки

- гілки: `feat/`, `fix/`, `docs/`
- коміти: `feat: …`, `fix: …`, `docs: …`, `chore: …`, `update: …`, `hotfix: …`

## Перед пушем

```bash
cd ./frontend && npm run check && cd ..
cd ./backend && pytest && cd ..
```
