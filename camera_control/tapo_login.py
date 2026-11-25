"""Local authentication for the Tapo camera control API."""

from getpass import GetPassWarning, getpass
from pathlib import Path
from warnings import catch_warnings, simplefilter

ENV_FILE = Path(__file__).with_name(".env")


def _read_credentials() -> tuple[str, str]:
    settings = {}
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                settings[key] = value
    return settings.get("TAPO_CONTROL_USERNAME", ""), settings.get("TAPO_CLOUD_PASSWORD", "")


def _save_credentials(username: str, password: str) -> None:
    ENV_FILE.write_text(
        f"TAPO_CONTROL_USERNAME={username}\nTAPO_CLOUD_PASSWORD={password}\n",
        encoding="utf-8",
    )


def connect_tapo(host: str):
    try:
        from pytapo import Tapo
    except ImportError:
        print(r"Instala PyTapo con .\.venv\Scripts\python.exe -m pip install -r camera_control/requirements.txt")
        return None

    username, password = _read_credentials()
    needs_setup = not (username and password)
    if needs_setup:
        username = input("Nombre de usuario [admin]: ").strip() or "admin"
        try:
            with catch_warnings():
                simplefilter("error", GetPassWarning)
                password = getpass("Contraseña de la cuenta Tapo: ")
        except GetPassWarning:
            print("Usa una terminal que permita ingresar la contraseña sin mostrarla.")
            return None
        if not password:
            print("Introduce una contraseña para iniciar sesión.")
            return None

    print(f"Conectando por PyTapo a {host}, puerto 443...")
    try:
        # PyTapo also raises plain Exception on authentication failures.
        camera = Tapo(host, username, password, cloudPassword=password,
                      retryStok=False, printWarnInformation=False)
    except Exception as error:
        if type(error) is not Exception and not isinstance(error, OSError):
            raise
        print("PyTapo no pudo abrir la sesión. Comprueba la credencial y la conexión.")
        return None

    print("[OK] Sesión PyTapo iniciada.")
    if needs_setup:
        _save_credentials(username, password)
        print("Credenciales guardadas en camera_control/.env.")
    return camera
