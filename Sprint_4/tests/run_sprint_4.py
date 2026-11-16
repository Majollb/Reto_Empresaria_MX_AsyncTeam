# [Sprint 4] Reenvío hacia tests/sprint_4/run_sprint_4.py
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from tests.sprint_4.run_sprint_4 import main

if __name__ == "__main__":
    main()
