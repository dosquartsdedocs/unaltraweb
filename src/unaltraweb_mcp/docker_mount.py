from __future__ import annotations

import os
from pathlib import Path


def docker_bind_mount(source: str | os.PathLike[str], target: str | os.PathLike[str], *, readonly: bool = False) -> str:
    source_value = os.fspath(source)
    target_value = os.fspath(target)
    if not Path(source_value).is_absolute() or not Path(target_value).is_absolute():
        raise ValueError("Docker bind source and target must be absolute paths")
    if any(character in value for value in (source_value, target_value) for character in "\r\n"):
        raise ValueError("Docker bind source and target must not contain carriage returns or newlines")

    def csv_field(value: str) -> str:
        return f'"{value.replace(chr(34), chr(34) * 2)}"'

    mount = f"type=bind,{csv_field(f'source={source_value}')},{csv_field(f'target={target_value}')}"
    return f"{mount},readonly" if readonly else mount
