from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Optional, Union

import paramiko
from scp import SCPClient

LEGACY_HOST_KEY_ALGORITHMS = ("ssh-rsa", "ssh-dss")


@dataclass
class CommandResult:
    exit_status: int
    stdout: str
    stderr: str


class SSHManager:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        connect_timeout: int,
        encoding: str = "utf-8",
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.connect_timeout = connect_timeout
        self.encoding = encoding
        self.client: Optional[paramiko.SSHClient] = None

    def connect(self) -> None:
        self._enable_legacy_host_key_algorithms()
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.host,
                port=int(self.port),
                username=self.username,
                password=self.password,
                timeout=int(self.connect_timeout),
                banner_timeout=int(self.connect_timeout),
                auth_timeout=int(self.connect_timeout),
                look_for_keys=False,
                allow_agent=False,
            )
            self.client = client
        except Exception as exc:
            client.close()
            raise RuntimeError(
                "SSH 连接失败: "
                f"{exc}; paramiko={_get_package_version('paramiko')}, "
                f"cryptography={_get_package_version('cryptography')}"
            ) from exc

    def _enable_legacy_host_key_algorithms(self) -> None:
        preferred_keys = getattr(paramiko.Transport, "_preferred_keys", ())
        if not preferred_keys:
            return

        updated_keys = tuple(
            dict.fromkeys(LEGACY_HOST_KEY_ALGORITHMS + tuple(preferred_keys))
        )
        paramiko.Transport._preferred_keys = updated_keys

    def execute_command(self, command: str, timeout: int) -> CommandResult:
        if self.client is None:
            raise RuntimeError("SSH 连接尚未建立。")

        command_bytes = command.encode(self.encoding, errors="replace")
        stdin, stdout, stderr = self.client.exec_command(command_bytes, timeout=int(timeout))
        stdin.close()
        exit_status = stdout.channel.recv_exit_status()
        return CommandResult(
            exit_status=exit_status,
            stdout=stdout.read().decode(self.encoding, errors="replace").strip(),
            stderr=stderr.read().decode(self.encoding, errors="replace").strip(),
        )

    def download_file(self, remote_path: str, local_path: Union[str, Path]) -> None:
        if self.client is None:
            raise RuntimeError("SSH 连接尚未建立。")

        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with SCPClient(self.client.get_transport()) as scp:
            scp.get(remote_path, str(local_path))

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def _get_package_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return "not-installed"
