# Contributing to VERONIKA AI

Thank you for your interest in contributing to **VERONIKA AI**! We welcome community contributions, bug reports, and feature proposals.

---

## 🛠 Development Setup

1. Fork the repository and clone your fork:
   ```bash
   git clone https://github.com/swapnil127kp-design/VERONIKA-AI.git
   cd VERONIKA-AI
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Run the test suite to ensure everything is operational:
   ```bash
   pytest tests/
   ```

---

## 📝 Guidelines

* **Code Quality**: Follow PEP 8 standards. Write clear docstrings and comments.
* **Security**: Never commit sensitive API keys or personal credentials. Use `.env.example` as a template.
* **Testing**: Add or update unit tests in `tests/` for any new logic or bug fixes.
* **Commits**: Use concise, conventional commit messages (e.g. `feat: add MCP tool registry filter`, `fix: handle audio device disconnect`).

---

## 📬 Submitting Changes

1. Create a feature branch (`git checkout -b feature/amazing-feature`).
2. Commit your changes (`git commit -m 'feat: implement amazing feature'`).
3. Push to your branch (`git push origin feature/amazing-feature`).
4. Open a Pull Request detailing your changes and how they have been tested.
