from pathlib import Path
from typing import Any, Optional, Union

import yaml


class ConfigError(Exception):
    """Raised when runtime configuration is missing or invalid."""


class ConfigManager:
    def __init__(self, config_path: Union[str, Path] = "config/environments.yaml"):
        self.config_path = Path(config_path)
        self._config: Optional[dict[str, Any]] = None

    def load(self) -> dict[str, Any]:
        if self._config is not None:
            return self._config

        if not self.config_path.exists():
            raise ConfigError(
                "缺少运行配置文件 config/environments.yaml，请先复制 "
                "config/environments.example.yaml 生成 config/environments.yaml，"
                "并填写对应环境的服务器、路径、用户名和密码。"
            )

        try:
            with self.config_path.open("r", encoding="utf-8") as file:
                config = yaml.safe_load(file) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"配置文件解析失败: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"配置文件读取失败: {exc}") from exc

        if not isinstance(config, dict) or not isinstance(config.get("environments"), dict):
            raise ConfigError("配置文件格式错误：根节点必须包含 environments 对象。")

        self._config = config
        return config

    def get_environment(self, env: str) -> dict[str, Any]:
        environments = self.load()["environments"]
        env_config = environments.get(env)
        if not isinstance(env_config, dict):
            raise ConfigError(f"未找到环境配置: {env}")
        return env_config

    def get_package_config(self, env: str) -> dict[str, Any]:
        env_config = self.get_environment(env)
        package_config = env_config.get("package")
        if not isinstance(package_config, dict):
            raise ConfigError(f"环境 {env} 缺少 package 配置。")

        required_fields = [
            "host",
            "port",
            "protocol",
            "username",
            "remote_root",
            "package_name_template",
            "remote_temp_dir",
            "local_root",
            "connect_timeout",
            "command_timeout",
        ]
        optional_fields = ["password"]
        missing_fields = [
            field
            for field in required_fields
            if field not in package_config or package_config.get(field) in (None, "")
        ]
        missing_fields.extend(field for field in optional_fields if field not in package_config)
        if missing_fields:
            raise ConfigError(f"环境 {env} 的 package 配置缺少必填项: {', '.join(missing_fields)}")

        if package_config.get("protocol") != "ssh":
            raise ConfigError(f"环境 {env} 的 package.protocol 当前仅支持 ssh。")

        return package_config
