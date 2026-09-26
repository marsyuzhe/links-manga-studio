"""PyInstaller entry point; keep package-relative imports in app.main intact."""
from app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
