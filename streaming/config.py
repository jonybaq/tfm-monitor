"""Configuración del destino y protocolo de publicación."""

from dataclasses import dataclass, field
from getpass import getpass
import os
from pathlib import Path
import re
from urllib.parse import quote, urlencode

ENV_FILE = Path(__file__).with_name(".env")
AZURE_PUBLISH_USER = "tfm-publisher"


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
        while True:
            key = getwch()
            if key == "\r":
                if clear_on_select:
                    clear_menu = "\033[4A\r" + "\033[2K\033[1B" * 3 + "\033[2K\033[3A"
                    print(clear_menu, end="", flush=True)
                return selected
            if key in {"\x03", "\x1b"}:
                raise KeyboardInterrupt
            if key in {"\x00", "\xe0"} and getwch() in {"H", "P"}:
                selected = 1 - selected
                redraw = True
                break


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
        lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.is_file() else []
        settings = {}
        for line in lines:
            key, sep, value = line.partition("=")
            if sep and key.strip().startswith("STREAMING_"):
                settings[key.strip()] = value

        mode = os.getenv("STREAMING_MODE", settings.get("STREAMING_MODE", "")).strip().lower()
        if not mode and interactive:
            mode = choose_mode()
        mode = mode or "local"
        if mode not in {"local", "azure"}:
            raise ValueError("STREAMING_MODE debe ser local o azure.")

        transport = os.getenv(
            "STREAMING_TRANSPORT", settings.get("STREAMING_TRANSPORT", "")
        ).strip().lower()
        if rtsp_only:
            transport = "rtsp"
        if not transport:
            transport = choose_transport() if interactive else "srt"
        if transport not in {"srt", "rtsp"}:
            raise ValueError("STREAMING_TRANSPORT debe ser srt o rtsp.")
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
            missing = [
                key for key, value in ((host_key, host), (port_key, port_text))
                if not value
            ]
            if needs_phrase and not passphrase:
                missing.append(phrase_key)
            if azure_rtsp and not publish_password:
                missing.append(password_key)
            if missing:
                print("Falta configurar en streaming/.env: " + ", ".join(missing), flush=True)
            if not host:
                if mode == "local":
                    host = input("IP o DNS del receptor local [127.0.0.1]: ").strip()
                    host = host or "127.0.0.1"
                else:
                    host = input("IP pública o DNS de tapo-media: ").strip()
                save[host_key] = host
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
        if not host and mode == "local":
            host = "127.0.0.1"
        if azure_rtsp and not publish_password:
            raise ValueError(f"Configura {password_key} para publicar por RTSP en Azure.")
        if publish_password and not re.fullmatch(r"[A-Za-z0-9_-]{16,79}", publish_password):
            raise ValueError(f"{password_key} debe tener entre 16 y 79 letras, números, guiones o guiones bajos.")
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
            raise ValueError(f"{host_key} debe ser una IP IPv4 o un nombre DNS.")
        if any(character in passphrase for character in "\r\n\x00") or (
            (needs_phrase or passphrase) and not 10 <= len(passphrase.encode("utf-8")) <= 79
        ):
            raise ValueError("La frase SRT debe contener entre 10 y 79 bytes.")
        try:
            port = int(port_text or default_port)
        except ValueError:
            port = 0
        if not 1 <= port <= 65535:
            raise ValueError(f"{port_key} debe estar entre 1 y 65535.")
        audio = os.getenv("STREAMING_AUDIO", settings.get("STREAMING_AUDIO", "on")).strip().lower()
        if audio not in {"on", "off"}:
            raise ValueError("STREAMING_AUDIO debe ser on u off.")
        low_latency = os.getenv(
            "STREAMING_LOW_LATENCY", settings.get("STREAMING_LOW_LATENCY", "off")
        ).strip().lower()
        if low_latency not in {"on", "off"}:
            raise ValueError("STREAMING_LOW_LATENCY debe ser on u off.")
        if save:
            lines = [line for line in lines if line.partition("=")[0].strip() not in save]
            lines.extend(f"{key}={value}" for key, value in save.items())
            env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return cls(
            mode, host, passphrase, audio == "on", port, transport,
            low_latency == "on", publish_password,
        )

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
