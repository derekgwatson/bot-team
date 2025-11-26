"""Services module for Doc"""
from .sync import sync_service
from .checkup import checkup_service
from .test_runner import test_runner

__all__ = ['sync_service', 'checkup_service', 'test_runner']
