# Contributing to VocalPro

Thanks for your interest in contributing! This guide will help you get started.

## 🚀 Quick Start

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/vocal-pro.git
cd vocal-pro

# 3. Run setup (creates venv, installs deps, builds Flutter)
setup.bat

# 4. Create a feature branch
git checkout -b feature/your-feature-name

# 5. Make your changes and test
python -m pytest tests/unit/ tests/integration/ -v
cd flutter_app && flutter test && cd ..

# 6. Commit and push
git add .
git commit -m "Add your feature"
git push origin feature/your-feature-name

# 7. Open a Pull Request on GitHub
```

## 📋 Development Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Backend / API server |
| Flutter SDK | 3.29+ | Desktop frontend |
| FFmpeg | Any | Audio processing |
| Git | Any | Version control |

## 🏗️ Project Structure

```
vocal-pro/
├── api_server/           # FastAPI backend
│   ├── main.py           # REST + WebSocket endpoints
│   ├── run_server.py     # Server launcher
│   └── requirements.txt  # Python API deps
├── code/                 # Core Python modules
│   ├── separation_engine.py  # Demucs AI separation
│   ├── audio_postprocess.py  # VAD, gating, denoising
│   ├── config.py             # Configuration management
│   ├── utils.py              # FFmpeg + audio utilities
│   └── _shared.py            # Shared constants
├── flutter_app/          # Flutter desktop app
│   ├── lib/
│   │   ├── main.dart         # Entry point
│   │   ├── screens/          # UI screens
│   │   ├── controllers/      # State management
│   │   ├── services/         # API client
│   │   ├── widgets/          # Reusable components
│   │   └── l10n/             # 16 language translations
│   └── pubspec.yaml          # Flutter deps
├── tests/                # Test suites
│   ├── unit/             # Unit tests (fast, no GPU)
│   ├── integration/      # Integration tests
│   └── api/              # API endpoint tests
├── setup.bat             # One-click installer
├── run.bat               # App launcher
└── pyproject.toml        # Python project config
```

## 🧪 Testing

### Python Tests

```bash
# Activate virtual environment first
venv\Scripts\activate

# Run unit + integration tests (fast, no GPU needed)
python -m pytest tests/unit/ tests/integration/ -v

# Run a specific test file
python -m pytest tests/unit/test_config.py -v

# Run a specific test
python -m pytest tests/unit/test_config.py::TestConfig::test_load_default -v

# Run tests matching a keyword
python -m pytest -k "denoise" -v
```

### Flutter Tests

```bash
cd flutter_app

# Run all Flutter tests
flutter test

# Run a specific test file
flutter test test/widget_test.dart
```

### API Tests

```bash
# Start the server first
venv\Scripts\activate
python api_server/main.py &

# Run API tests (requires running server)
python -m pytest tests/api/ -v
```

## 🎨 Code Style

### Python
- Follow PEP 8 style
- Use type hints where practical
- Keep functions focused (single responsibility)
- Add docstrings for public functions
- Use `snake_case` for variables and functions
- Use `PascalCase` for classes

### Dart / Flutter
- Follow the [Dart style guide](https://dart.dev/effective-dart/style)
- Use `lowerCamelCase` for variables and functions
- Use `PascalCase` for classes and enums
- Prefer `const` constructors where possible
- Use `final` for immutable variables

### Commit Messages
- Use clear, descriptive commit messages
- Start with a verb: `Add`, `Fix`, `Update`, `Remove`, `Refactor`
- Keep the first line under 72 characters
- Reference issues when applicable: `Fix #42`

```
Add stem volume slider to separation screen

- Add 0-200% slider per stem
- Persist volume settings in config
- Update mix preview on slider change

Fixes #42
```

## 🔧 Making Changes

### Adding a New Feature

1. **Open an issue first** to discuss the feature
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Write tests for your changes
4. Ensure all tests pass
5. Submit a pull request

### Fixing a Bug

1. **Check existing issues** to avoid duplicates
2. Create a bugfix branch: `git checkout -b fix/my-bug`
3. Write a test that reproduces the bug
4. Fix the bug
5. Ensure all tests pass
6. Submit a pull request

### Adding a New Language

1. Copy `flutter_app/assets/lang/en.json` to `flutter_app/assets/lang/XX.json`
2. Translate all strings in the new file
3. Add the locale to `flutter_app/lib/l10n/app_localizations.dart`
4. Test that the app loads the new locale correctly

### Adding a New API Endpoint

1. Add the endpoint to `api_server/main.py`
2. Add a Pydantic model for request/response if needed
3. Write API tests in `tests/api/`
4. Update the README API reference

## 🐛 Reporting Bugs

When reporting bugs, please include:

1. **OS and version** (e.g., Windows 11 23H2)
2. **Python version** (`python --version`)
3. **Flutter version** (`flutter --version`)
4. **Steps to reproduce** the issue
5. **Expected behavior** vs **actual behavior**
6. **Error messages** or logs (if any)
7. **Screenshots** (if applicable)

### Getting Logs

```bash
# Server log (after running the app)
type %TEMP%\vocalpro_server.log

# Or check the console output when running:
python api_server/main.py
```

## 📦 Dependency Management

### Python
- Core deps are in `pyproject.toml` under `[project.dependencies]`
- Heavy ML deps are in `[project.optional-dependencies.full]`
- Test deps are in `[project.optional-dependencies.test]`
- API deps are in `api_server/requirements.txt`

### Flutter
- All deps are in `flutter_app/pubspec.yaml`
- Run `flutter pub get` after adding a new dependency

## 🏷️ Versioning

We use [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes to the API or configuration
- **MINOR** (0.X.0): New features, backward compatible
- **PATCH** (0.0.X): Bug fixes, backward compatible

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 💬 Getting Help

- **Issues**: [GitHub Issues](https://github.com/lam3y35/vocal-pro/issues)
- **Discussions**: [GitHub Discussions](https://github.com/lam3y35/vocal-pro/discussions)

## 🙏 Thank You

Every contribution helps make VocalPro better. Whether it's a bug fix, a new feature, documentation improvement, or just a typo fix — we appreciate it!
