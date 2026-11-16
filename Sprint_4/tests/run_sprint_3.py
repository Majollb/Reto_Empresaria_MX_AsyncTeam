# [Sprint 3] Reenvío hacia tests/sprint_3/run_sprint_3.py
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from tests.sprint_3.run_sprint_3 import main

if __name__ == "__main__":
    main()
