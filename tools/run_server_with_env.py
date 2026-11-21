import os
from pathlib import Path
import sys

# Load .env file from project root first, then fall back to cleverfund_backend/.env
env_paths = [
    Path(__file__).resolve().parents[1] / '.env',  # root .env
    Path(__file__).resolve().parents[1] / 'cleverfund_backend' / '.env',  # backend .env
]

for env_path in env_paths:
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            # Do not print or log secrets
            os.environ.setdefault(k, v)

# Now start the backend app
# Ensure package import paths include project root and cleverfund_backend
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'cleverfund_backend'))

from cleverfund_backend import app as clever_app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting CleverFund backend on http://127.0.0.1:{port}")
    clever_app.run(debug=True, host='127.0.0.1', port=port)
