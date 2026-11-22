"""Configuración del destino y protocolo de publicación."""

from dataclasses import dataclass, field
from getpass import getpass
import os
from pathlib import Path
import re
from urllib.parse import quote, urlencode

ENV_FILE = Path(__file__).with_name(".env")
AZURE_PUBLISH_USER = "tfm-publisher"


class StreamingError(ValueError):
    """Expected streaming failure with a message safe to show in the console."""


def choose_option(
    prompt: str, options: tuple[str, str], *, clear_on_select: bool = False
) -> int:
    """Muestra un selector de consola para Windows."""
    from msvcrt import getwch

    selected = 0
    print(prompt)
    print("Usa las flechas para elegir y pulsa Enter.")
    redraw = False
    while True:
        if redraw:
            print("\033[2A", end="")
        labels = [
            f"> {option}" if index == selected else f"  {option}"
            for index, option in enumerate(options)
        ]
        print("\n".join(labels), flush=True)
        key = _read_menu_key(getwch)
        if key == "enter":
            if clear_on_select:
                clear_menu = "\033[4A\r" + "\033[2K\033[1B" * 3 + "\033[2K\033[3A"
                print(clear_menu, end="", flush=True)
            return selected
        selected = 1 - selected
        redraw = True


def _read_menu_key(read_key) -> str:
    while True:
        key = read_key()
        if key == "\r":
            return "enter"
        if key in {"\x03", "\x1b"}:
            raise KeyboardInterrupt
        if key in {"\x00", "\xe0"} and read_key() in {"H", "P"}:
            return "arrow"


def choose_mode() -> str:
    selected = choose_option(
        "¿Dónde enviar?", ("Local", "Azure"), clear_on_select=True
    )
    return ("local", "azure")[selected]


def choose_transport() -> str:
    selected = choose_option(
        "¿Cómo transmitir?", ("SRT", "RTSP"), clear_on_select=True
    )
    return ("srt", "rtsp")[selected]


def _read_settings(env_file: Path) -> tuple[list[str], dict[str, str]]:
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.is_file() else []
    settings = {}
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and key.strip().startswith("STREAMING_"):
            settings[key.strip()] = value

    return lines, settings


def _select_mode_and_transport(
    settings: dict[str, str], interactive: bool, rtsp_only: bool,
) -> tuple[str, str]:
    mode = os.getenv("STREAMING_MODE", settings.get("STREAMING_MODE", "")).strip().lower()
    if not mode and interactive:
        mode = choose_mode()
    mode = mode or "local"
    if mode not in {"local", "azure"}:
        raise StreamingError("STREAMING_MODE debe ser local o azure.")

    transport = os.getenv(
        "STREAMING_TRANSPORT", settings.get("STREAMING_TRANSPORT", "")
    ).strip().lower()
    if rtsp_only:
        transport = "rtsp"
    if not transport:
        transport = choose_transport() if interactive else "srt"
    if transport not in {"srt", "rtsp"}:
        raise StreamingError("STREAMING_TRANSPORT debe ser srt o rtsp.")
    return mode, transport


def _prompt_missing_destination(
    mode: str, transport: str, keys: tuple[str, str, str, str],
    values: tuple[str, str, str, str], default_port: str,
) -> dict[str, str]:
    host_key, port_key, phrase_key, password_key = keys
    host, port_text, passphrase, publish_password = values
    azure_rtsp = mode == "azure" and transport == "rtsp"
    needs_phrase = mode == "azure" and transport == "srt"
    save = {}
    required = {host_key: host, port_key: port_text}
    if needs_phrase:
        required[phrase_key] = passphrase
    if azure_rtsp:
        required[password_key] = publish_password
    missing = [key for key, value in required.items() if not value]
    if missing:
        print("Falta configurar en streaming/.env: " + ", ".join(missing), flush=True)
    if not host:
        save[host_key] = _prompt_host(mode)
    if not port_text:
        port_text = input(
            f"Puerto {transport.upper()} [{default_port}]: "
        ).strip() or default_port
        save[port_key] = port_text
    if not passphrase and needs_phrase:
        passphrase = getpass("Frase SRT de publicación: ")
        save[phrase_key] = passphrase
    if azure_rtsp and not publish_password:
        publish_password = getpass("Contraseña temporal de publicación en Azure: ")
        save[password_key] = publish_password
    return save


def _prompt_host(mode: str) -> str:
    if mode == "local":
        return input("IP o DNS del receptor local [127.0.0.1]: ").strip() or "127.0.0.1"
    return input("IP pública o DNS de tapo-media: ").strip()


def _validate_publish_password(azure_rtsp: bool, publish_password: str, password_key: str) -> None:
    if azure_rtsp and not publish_password:
        raise StreamingError(f"Configura {password_key} para publicar por RTSP en Azure.")
    if publish_password and not re.fullmatch(r"[A-Za-z0-9_-]{16,79}", publish_password):
        raise StreamingError(f"{password_key} debe tener entre 16 y 79 letras, números, guiones o guiones bajos.")


def _validate_passphrase(passphrase: str, required: bool) -> None:
    if any(character in passphrase for character in "\r\n\x00") or (
        (required or passphrase) and not 10 <= len(passphrase.encode("utf-8")) <= 79
    ):
        raise StreamingError("La frase SRT debe contener entre 10 y 79 bytes.")


def _read_switch(key: str, value: str) -> bool:
    value = value.strip().lower()
    if value not in {"on", "off"}:
        raise StreamingError(f"{key} debe ser on u off.")
    return value == "on"


def _validate_destination(
    *, mode: str, azure_rtsp: bool, needs_phrase: bool, host: str, host_key: str,
    port_text: str, port_key: str, default_port: str, passphrase: str,
    publish_password: str, password_key: str, audio: str, low_latency: str,
) -> tuple[str, int, bool, bool]:
    if not host and mode == "local":
        host = "127.0.0.1"
    _validate_publish_password(azure_rtsp, publish_password, password_key)
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
        raise StreamingError(f"{host_key} debe ser una IP IPv4 o un nombre DNS.")
    _validate_passphrase(passphrase, needs_phrase)
    try:
        port = int(port_text or default_port)
    except ValueError:
        port = 0
    if not 1 <= port <= 65535:
        raise StreamingError(f"{port_key} debe estar entre 1 y 65535.")
    return (
        host, port, _read_switch("STREAMING_AUDIO", audio),
        _read_switch("STREAMING_LOW_LATENCY", low_latency),
    )


def _save_settings(env_file: Path, lines: list[str], values: dict[str, str]) -> None:
    lines = [line for line in lines if line.partition("=")[0].strip() not in values]
    lines.extend(f"{key}={value}" for key, value in values.items())
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class StreamDestination:
    mode: str
    host: str
    passphrase: str = field(default="", repr=False)
    audio_enabled: bool = True
    port: int = 8890
    transport: str = "srt"
    low_latency: bool = False
    publish_password: str = field(default="", repr=False)

    @classmethod
    def from_environment(
        cls, *, interactive: bool = False, env_file: Path = ENV_FILE,
        rtsp_only: bool = False,
    ) -> "StreamDestination":
        lines, settings = _read_settings(env_file)
        mode, transport = _select_mode_and_transport(settings, interactive, rtsp_only)
        azure_rtsp = mode == "azure" and transport == "rtsp"
        needs_phrase = mode == "azure" and transport == "srt"
        prefix = f"STREAMING_{mode.upper()}"
        host_key = f"{prefix}_HOST"
        port_key = f"{prefix}_RTSP_PORT" if transport == "rtsp" else f"{prefix}_PORT"
        default_port = "8554" if transport == "rtsp" else "8890"
        phrase_key = f"{prefix}_SRT_PASSPHRASE"
        host = os.getenv("STREAMING_HOST", os.getenv(host_key, settings.get(host_key, ""))).strip()
        port_text = os.getenv(
            "STREAMING_PORT", os.getenv(port_key, settings.get(port_key, ""))
        ).strip()
        passphrase = (
            os.getenv("STREAMING_SRT_PASSPHRASE", settings.get(phrase_key, ""))
            if transport == "srt" else ""
        )
        password_key = "STREAMING_AZURE_PUBLISH_PASSWORD"
        publish_password = (
            os.getenv(password_key, settings.get(password_key, "")) if mode == "azure" else ""
        )
        save = {}
        if interactive:
            save = _prompt_missing_destination(
                mode, transport, (host_key, port_key, phrase_key, password_key),
                (host, port_text, passphrase, publish_password), default_port,
            )
            host = save.get(host_key, host)
            port_text = save.get(port_key, port_text)
            passphrase = save.get(phrase_key, passphrase)
            publish_password = save.get(password_key, publish_password)
        host, port, audio_enabled, low_latency = _validate_destination(
            mode=mode, azure_rtsp=azure_rtsp, needs_phrase=needs_phrase,
            host=host, host_key=host_key, port_text=port_text, port_key=port_key,
            default_port=default_port, passphrase=passphrase, publish_password=publish_password,
            password_key=password_key, audio=os.getenv("STREAMING_AUDIO", settings.get("STREAMING_AUDIO", "on")),
            low_latency=os.getenv("STREAMING_LOW_LATENCY", settings.get("STREAMING_LOW_LATENCY", "off")),
        )
        if save:
            _save_settings(env_file, lines, save)
        return cls(mode, host, passphrase, audio_enabled, port, transport, low_latency, publish_password)

    @property
    def url(self) -> str:
        if self.transport == "rtsp":
            credentials = (
                f"{AZURE_PUBLISH_USER}:{quote(self.publish_password, safe='')}@"
                if self.publish_password else ""
            )
            return f"rtsp://{credentials}{self.host}:{self.port}/tapo"
        stream_id = "publish:tapo"
        if self.publish_password:
            stream_id += f":{AZURE_PUBLISH_USER}:{self.publish_password}"
        options = {
            "mode": "caller",
            "streamid": stream_id,
            "pkt_size": "1316",
            "timeout": "5000000",
        }
        if self.passphrase:
            options.update(pbkeylen="32", passphrase=self.passphrase)
        return f"srt://{self.host}:{self.port}?{urlencode(options)}"

    @property
    def waiting_message(self) -> str:
        if self.mode == "azure":
            return "Esperando receptor en la nube"
        return "Esperando receptor local"
