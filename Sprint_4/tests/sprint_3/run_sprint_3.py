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
from tests.sprint_3 import test_historia_usuario_7, test_historia_usuario_8, test_historia_usuario_9

def main():
    print("=" * 80)
    print(" EJECUCIÓN DE PRUEBAS - SPRINT 3: ATENCIÓN, SEGUIMIENTO Y CICLO DE VIDA")
    print(" Automatización y Software del Bajío")
    print(" Alcance: HU-07 (Asignación/Reasignación), HU-08 (Transiciones/Tiempos), HU-09 (Bitácora/Adjuntos)")
    print("=" * 80)

    initial_uploads = snapshot_uploads()
    try:
        test_historia_usuario_7()
        test_historia_usuario_8()
        test_historia_usuario_9()

        print("\n" + "#" * 80)
        print("  VERIFICACIÓN SPRINT 3 EXITOSA: 100% DE CRITERIOS (HU-07 A HU-09) CUMPLIDOS")
        print("#" * 80 + "\n")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[FALLO EN SPRINT 3]: {str(e)}")
        sys.exit(1)
    finally:
        restore_clean_state(initial_uploads)

if __name__ == "__main__":
    main()


