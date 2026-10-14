# SkillSwap — Python Flask

A modern skill-exchange website built with Python Flask + SQLite + HTML/CSS.

## Features
- User registration and login
- Password hashing
- Session-based authentication
- Add skills: "I can teach" / "I want to learn"
- Search and explore skills
- Automatic basic matching
- Profile editing
- Send messages to matched users
- Responsive modern UI
- Demo data on first launch

## Run on Windows

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open:
http://127.0.0.1:5000

Demo login:
Email: aarav@skillswap.demo
Password: 123456

## Project structure

skillswap/
├── app.py
├── requirements.txt
├── README.md
├── skillswap.db       # created automatically
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── auth.html
│   ├── dashboard.html
│   ├── skills.html
│   └── profile.html
└── static/
    └── style.css

For production, change the Flask secret key and use a production WSGI server. The built-in Flask development server is intended for local development/testing.
