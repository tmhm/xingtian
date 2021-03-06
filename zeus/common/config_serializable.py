# -*- coding:utf-8 -*-

# Copyright (C) 2020. Huawei Technologies Co., Ltd. All rights reserved.
# This program is free software; you can redistribute it and/or modify
# it under the terms of the MIT License.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# MIT License for more details.

"""Convert class to string."""
import json
import logging
from copy import deepcopy
from inspect import ismethod, isfunction
from .config import Config
from .class_factory import ClassFactory
from .file_ops import FileOps
from zeus.common.util.check import valid_rule


__all__ = ["ConfigSerializable", "backup_configs"]
logger = logging.getLogger(__name__)


class ConfigSerializable(object):
    """Seriablizable config base class."""

    __original__value__ = None

    def to_json(self):
        """Serialize config to a dictionary."""
        attrs = [attr for attr in dir(self) if not attr.startswith("__")]
        attrs = [attr for attr in attrs if not ismethod(getattr(self, attr)) and not isfunction(getattr(self, attr))]
        attr_dict = {}
        for attr in attrs:
            value = getattr(self, attr)
            if isinstance(value, type) and isinstance(value(), ConfigSerializable):
                value = value().to_json()
            elif isinstance(value, ConfigSerializable):
                value = value.to_json()
            attr_dict[attr] = value
        return Config(deepcopy(attr_dict))

    @classmethod
    def from_json(cls, data, skip_check=True):
        """Restore config from a dictionary or a file."""
        if not data:
            return cls
        config = Config(deepcopy(data))
        if not skip_check:
            cls.check_config(config)
        # link config
        if _is_link_config(cls):
            _load_link_config(cls, config)
            return cls
        # normal config
        for attr in config:
            if not hasattr(cls, attr):
                setattr(cls, attr, config[attr])
                continue
            class_value = getattr(cls, attr)
            config_value = config[attr]
            if isinstance(class_value, type) and isinstance(config_value, dict):
                setattr(cls, attr, class_value.from_json(config_value, skip_check))
            else:
                setattr(cls, attr, config_value)
        # PipeStepConfig
        if cls.__name__ == "PipeStepConfig":
            if "pipe_step" in data:
                if "type" in data["pipe_step"]:
                    cls.type = data["pipe_step"]["type"]
                if "models_folder" in data["pipe_step"]:
                    cls.models_folder = data["pipe_step"]["models_folder"]
        return cls

    def __repr__(self):
        """Serialize config to a string."""
        return json.dumps(self.to_json())

    @classmethod
    def check_config(cls, config):
        """Check config."""
        valid_rule(cls, config, cls.rules())

    @classmethod
    def rules(cls):
        """Return rules for checking."""
        return {}

    @classmethod
    def backup_original_value(cls):
        """Backup class original data."""
        if not cls.__original__value__:
            cls.__original__value__ = cls().to_json()
        return cls.__original__value__

    @classmethod
    def renew(cls):
        """Restore class original data."""
        if cls.__original__value__:
            cls.from_json(cls.__original__value__)


def _is_link_config(_cls):
    return hasattr(_cls, "type") and hasattr(_cls, "_class_type") and \
        hasattr(_cls, "_class_data")


def _load_link_config(_cls, config):
    if not isinstance(config, dict) or "type" not in config:
        logger.error("Failed to unserialize config, class={}, config={}".format(
            str(_cls()), str(config)))
        return None
    class_type = _cls._class_type
    class_name = config["type"]
    if not class_name:
        return None
    if "_class_data" in config:
        # restore config
        class_data = config["_class_data"]
    else:
        # first set config
        class_data = config
    config_cls = _get_specific_class_config(class_type, class_name)
    if config_cls:
        setattr(_cls, "type", class_name)
        if class_data:
            setattr(_cls, "_class_data", config_cls.from_json(class_data))
        else:
            setattr(_cls, "_class_data", config_cls)
    else:
        logger.error("Failed to unserialize config, class={}, config={}".format(
            str(_cls()), str(config)))


def _get_specific_class_config(class_type, class_name):
    specific_class = ClassFactory.get_cls(class_type, class_name)
    if hasattr(specific_class, 'config') and specific_class.config:
        return type(specific_class.config)
    else:
        return None


def backup_configs():
    """Backup all configs."""
    classes = []
    _get_all_config_cls(classes, ConfigSerializable)
    for subclass in classes:
        subclass.backup_original_value()


def _get_all_config_cls(classes, base_class):
    subclasses = base_class.__subclasses__()
    for subclass in subclasses:
        classes.append(subclass)
        _get_all_config_cls(classes, subclass)
