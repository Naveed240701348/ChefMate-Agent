# ChefMate-Agent 🍳

> **An AI-powered Recipe Preparation web application** — built with Python Flask and powered by **IBM watsonx Orchestrate**.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 AI Chat | ChatGPT-style interface wired to IBM watsonx Orchestrate |
| 🍲 Recipe Cards | Rich cards with nutrition, steps, tips, and substitutions |
| 🌙 Dark / Light Mode | System-aware with manual toggle, persisted in localStorage |
| 📱 Responsive | Mobile, tablet, and desktop layouts |
| 🛒 Shopping List | One-prompt shopping list generator |
| ❤️ Saved Recipes | Persist favourites in localStorage |
| 🌍 30+ Cuisines | Italian, Japanese, Indian, Thai, Mexican, and more |
| 🥗 8 Diet Types | Vegan, Keto, Gluten-Free, Halal, Paleo, etc. |
| ⚡ Retry Logic | Automatic retry with back-off on API failures |

---

## 📁 Project Structure

```
chefmate-agent/
├── app.py                    # Flask entry point
├── config.py                 # Configuration (reads .env)
├── requirements.txt          # Python dependencies
├── .env                      # 🔒 Secrets — never commit this!
│
├── routes/
│   ├── __init__.py
│   ├── pages.py              # HTML page routes (/, /chat)
│   └── api.py                # REST API routes (/api/chat, /api/health)
│
├── services/
│   ├── __init__.py
│   └── orchestrate_service.py  # IBM watsonx Orchestrate integration
│
├── utils/
│   ├── __init__.py
│   └── helpers.py            # Input sanitisation, response builders
│
├── templates/
│   ├── base.html             # Base layout (navbar, footer, CDN links)
│   ├── index.html            # Home page
│   └── chat.html             # AI Chat page
│
└── static/
    ├── css/
    │   ├── main.css          # Global styles & components
    │   ├── chat.css          # Chat page–specific styles
    │   └── animations.css    # Keyframes & animation utilities
    ├── js/
    │   ├── theme.js          # Dark/light mode manager
    │   ├── main.js           # Home page JS (scroll, ripple, etc.)
    │   └── chat.js           # Chat page JS (send, render, sidebar)
    └── images/
        └── favicon.svg
```

---

## 🚀 Quick Start

### 1 — Clone or download the project

```bash
git clone <your-repo-url>
cd chefmate-agent
```

### 2 — Create and activate a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — Configure environment variables

Create a file named `.env` in the project root (the file is git-ignored):

```env
ORCHESTRATE_API_KEY=your_ibm_cloud_api_key
ORCHESTRATE_URL=https://api.us-south.assistant.watson.cloud.ibm.com
ORCHESTRATE_AGENT_ID=your_agent_id
IBM_PROJECT_ID=your_project_id
FLASK_SECRET_KEY=change-me-in-production
FLASK_ENV=development
FLASK_DEBUG=True
```

> **Where to find these values:**
> - Log in to [IBM Cloud](https://cloud.ibm.com/)
> - Open **watsonx Orchestrate** → your **ChefMate-Agent** instance
> - Copy the **API key**, **Service URL**, and **Agent / Assistant ID**

### 5 — Run the development server

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

---

## 🔑 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Home page |
| `GET` | `/chat` | AI Chat page |
| `POST` | `/api/chat` | Send a message → get AI response |
| `POST` | `/api/chat/clear` | Clear the server-side session |
| `GET` | `/api/health` | Liveness probe |

### POST /api/chat — Request

```json
{
  "message": "Give me a quick pasta recipe for 2",
  "conversation_id": "conv-abc123"
}
```

### POST /api/chat — Response (success)

```json
{
  "success": true,
  "response": "Here's a quick Spaghetti Aglio e Olio...",
  "session_id": "session-xyz",
  "timestamp": "08 Jul 2026, 11:42 AM"
}
```

---

## 🌐 Deployment

### Heroku

```bash
# Install the Heroku CLI, then:
heroku create chefmate-agent
heroku config:set ORCHESTRATE_API_KEY=xxx ORCHESTRATE_URL=xxx ORCHESTRATE_AGENT_ID=xxx
git push heroku main
```

### Render / Railway

Point to `gunicorn app:app` as the start command and add the env vars in the dashboard.

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

---

## 🛡️ Security Notes

- Never commit your `.env` file — it is listed in `.gitignore`
- Rotate your IBM API key regularly
- Set `FLASK_DEBUG=False` and a strong `FLASK_SECRET_KEY` in production
- All user input is HTML-escaped server-side before forwarding to the AI

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 · Flask 3 |
| AI | IBM watsonx Orchestrate (REST API) |
| Frontend | HTML5 · CSS3 · Vanilla JS · Bootstrap 5 |
| Fonts | Inter · Poppins (Google Fonts) |
| Icons | Bootstrap Icons |
| Markdown | Marked.js · DOMPurify |

---

## 📄 License

MIT © 2026 ChefMate-Agent
