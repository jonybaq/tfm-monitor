"""Local authentication for the Tapo camera control API."""

from pathlib import Path


ENV_FILE = Path(__file__).with_name(".env")


def connect_tapo(host: str, env_file: Path = ENV_FILE):
    try:
        from pytapo import Tapo
    except ImportError:
        print(r"Instala PyTapo con .\.venv\Scripts\python.exe -m pip install -r camera_control/requirements.txt")
        return None

    settings = {}
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                settings[key] = value
    username = settings.get("TAPO_CONTROL_USERNAME", "")
    password = settings.get("TAPO_CLOUD_PASSWORD", "")
    needs_setup = not (username and password)
    if needs_setup:
        username = input("Nombre de usuario [admin]: ").strip() or "admin"
        password = input("Contraseña de la cuenta Tapo (visible): ")
        if not password:
            print("Introduce una contraseña para iniciar sesión.")
            return None

    print(f"Conectando por PyTapo a {host}, puerto 443...")
    try:
        # PyTapo also raises plain Exception on authentication failures.
        camera = Tapo(host, username, password, cloudPassword=password,
                      retryStok=False, printWarnInformation=False)
    except Exception:
        print("PyTapo no pudo abrir la sesión. Comprueba la credencial y la conexión.")
        return None

    print("[OK] Sesión PyTapo iniciada.")
    if needs_setup:
        env_file.write_text(
            f"TAPO_CONTROL_USERNAME={username}\nTAPO_CLOUD_PASSWORD={password}\n",
            encoding="utf-8",
        )
        print("Credenciales guardadas en camera_control/.env.")
    return camera
