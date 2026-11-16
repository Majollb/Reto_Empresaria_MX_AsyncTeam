import os
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

site_candidates = [
    Path.home() / "AppData" / "Roaming" / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "site-packages",
    Path(r"C:\Program Files\Unity\Hub\Editor\6000.6.3f1\Editor\Data\PlaybackEngines\WebGLSupport\BuildTools\Emscripten\python\Lib\site-packages")
]
for p in site_candidates:
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from tests import snapshot_uploads, restore_clean_state
from tests.sprint_4 import test_historia_usuario_10, test_historia_usuario_11, test_historia_usuario_12

def main():
    print("=" * 80)
    print(" EJECUCIÓN DE PRUEBAS - SPRINT 4: CIERRE, TRAZABILIDAD Y REPORTES EJECUTIVOS")
    print(" Automatización y Software del Bajío")
    print(" Alcance: HU-10 (Cierre y Recurrencia), HU-11 (Auditoría/Trazabilidad), HU-12 (Reportes y CSV)")
    print("=" * 80)

    initial_uploads = snapshot_uploads()
    try:
        test_historia_usuario_10()
        test_historia_usuario_11()
        test_historia_usuario_12()

        print("\n" + "#" * 80)
        print("  VERIFICACIÓN SPRINT 4 EXITOSA: 100% DE CRITERIOS (HU-10 A HU-12) CUMPLIDOS")
        print("#" * 80 + "\n")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[FALLO EN SPRINT 4]: {str(e)}")
        sys.exit(1)
    finally:
        restore_clean_state(initial_uploads)

if __name__ == "__main__":
    main()
