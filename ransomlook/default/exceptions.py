#!/usr/bin/env python3


class RansomlookException(Exception):
    pass


class MissingEnv(RansomlookException):
    pass


class CreateDirectoryException(RansomlookException):
    pass


class ConfigError(RansomlookException):
    pass
