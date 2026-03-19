# pyre-ignore-all-errors[21]
import os
import sys

# Asegurar que el directorio raíz está en el path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.health_checks import run_all_checks # type: ignore

if __name__ == "__main__":
    try:
        run_all_checks()
    except Exception as e:
        print(f"\n[CRITICAL ERROR] El script falló: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n" + "=" * 60)
        input("Presiona Enter para salir...")
