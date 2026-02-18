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
python src/myapp/main.py
```

## Running Tests

```bash
pytest tests/
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
