import os
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
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
from tests.sprint_1 import test_historia_usuario_1, test_historia_usuario_2, test_historia_usuario_3
from tests.sprint_2 import test_historia_usuario_4, test_historia_usuario_5, test_historia_usuario_6
from tests.sprint_3 import test_historia_usuario_7, test_historia_usuario_8, test_historia_usuario_9
from tests.sprint_4 import test_historia_usuario_10, test_historia_usuario_11, test_historia_usuario_12

def main():
    print("=" * 80)
    print(" EJECUCIÓN DE PRUEBAS INTEGRALES POR SPRINTS (HU-01 A HU-12)")
    print(" Automatización y Software del Bajío")
    print("=" * 80)

    initial_uploads = snapshot_uploads()
    try:
        print("\n" + "#" * 80)
        print("  >>> INICIANDO SPRINT 1: HU-01, HU-02, HU-03 (SEGURIDAD Y USUARIOS)")
        print("#" * 80)
        test_historia_usuario_1()
        test_historia_usuario_2()
        test_historia_usuario_3()
        print("\n[OK] SPRINT 1 COMPLETADO AL 100% CON ÉXITO.\n")

        print("#" * 80)
        print("  >>> INICIANDO SPRINT 2: HU-04, HU-05, HU-06 (CATÁLOGOS, TICKETS Y FILTROS)")
        print("#" * 80)
        test_historia_usuario_4()
        test_historia_usuario_5()
        test_historia_usuario_6()
        print("\n[OK] SPRINT 2 COMPLETADO AL 100% CON ÉXITO.\n")

        print("#" * 80)
        print("  >>> INICIANDO SPRINT 3: HU-07, HU-08, HU-09 (ATENCIÓN, SEGUIMIENTO Y TIEMPOS)")
        print("#" * 80)
        test_historia_usuario_7()
        test_historia_usuario_8()
        test_historia_usuario_9()
        print("\n[OK] SPRINT 3 COMPLETADO AL 100% CON ÉXITO.\n")

        print("#" * 80)
        print("  >>> INICIANDO SPRINT 4: HU-10, HU-11, HU-12 (CIERRE, TRAZABILIDAD Y REPORTES)")
        print("#" * 80)
        test_historia_usuario_10()
        test_historia_usuario_11()
        test_historia_usuario_12()
        print("\n[OK] SPRINT 4 COMPLETADO AL 100% CON ÉXITO.\n")

        print("=" * 80)
        print("  ENTREGA TOTALMENTE VERIFICADA: SPRINT 1, SPRINT 2, SPRINT 3 Y SPRINT 4 APROBADOS AL 100%")
        print("=" * 80 + "\n")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[FALLO EN EJECUCIÓN]: {str(e)}")
        sys.exit(1)
    finally:
        restore_clean_state(initial_uploads)

if __name__ == "__main__":
    main()
