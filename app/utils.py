"""
Toolkit
"""
from enum import Enum
from typing import Any


def remove_empty_fields(source: Any):
    if isinstance(source, dict):
        return {
            k: remove_empty_fields(v) for k, v in source.items() if v is not None
        }

    if isinstance(source, list):
        return [remove_empty_fields(x) for x in source]

    # convert enum to string
    if isinstance(source, Enum):
        return source.name

    return source


def write_fake_config(filename: str, service_url: str, debug_level='INFO'):
    """
    create a fake config file before KAG loaded
    this function should be called before **import kag**
    @:param service_url: the service url
    @:param debug_level: the debug level
    """

    content = f"""
# keep this fake config to cheat openspg-kag
# warning: 
#     KAG load this file as global config in 'kag.common.conf.KAGConfigMgr'. so we lost all default configs in kag.
#     if you want to use default configs, update this file.
project:
  host_addr: {service_url}

log:
  level: {debug_level}

vectorize_model:
  type: openai
    """
    with open(filename, "w") as f:
        f.write(content)
    pass
