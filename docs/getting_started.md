# Getting Started

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

```bash
export ADO_PAT="your-pat-token"
python src/myapp/main.py --org <org> --project <project> --repo-name <repo> --days 30
```

## Running Tests

```bash
python -m pytest -q
```

## Code Quality

- Format code with Black:
  ```bash
  black src/ tests/
  ```

- Lint with Flake8:
  ```bash
  flake8 src/ tests/
  ```

- Type check with MyPy:
  ```bash
  mypy src/
  ```
