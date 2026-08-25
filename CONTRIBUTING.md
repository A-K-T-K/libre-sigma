# Contributing to LibRE Sigma

Thank you for your interest in contributing to LibRE Sigma. We welcome contributions for new statistical algorithms, user interface enhancements, bug fixes, and documentation improvements.

---

## Development Workflow

### 1. Fork & Clone
```bash
git clone https://github.com/A-K-T-K/libre-tab.git
cd libre-tab
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
# Windows: .\venv\Scripts\activate
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## Adding a New Statistical Plugin

All analytical modules reside in `backend/app/plugins/modules/<category>/`.

To add a new statistical analysis or test:
1. Create a Python module subclassing `AnalysisPlugin` from `app.plugins.base`.
2. Define a Pydantic parameter schema with field descriptions and interactive UI types (e.g. `column_picker`).
3. Implement the `execute(self, df: pd.DataFrame, params: YourParams) -> AnalysisResult` method.
4. Add corresponding unit tests under `tests/`.

---

## Running Tests

Before submitting a Pull Request, ensure the full test suite passes:

```bash
# Run all backend statistical tests
python tests/test_master_suite.py

# Verify frontend build & TypeScript types
cd frontend
npm run build
```

---

## Code Style & Conventions

- **Python**: Follow PEP 8 guidelines. Type annotations and Pydantic schemas are required for all plugin parameters.
- **TypeScript / React**: Use functional components, strict TypeScript types, and Fluent UI design system tokens.
- **Commit Messages**: Write clear, imperative commit messages (e.g. `feat: add Friedman rank test plugin`, `fix: resolve CSV decimal parsing`).

---

## License

By contributing to LibRE Sigma, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
