"""Verify adopted status behavior through the complete native-attempt lifecycle.

The earlier standalone .next fixture is preserved in b497 history. Status now
requires exact factory-world binding and completion of its native call scope.
"""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parent.parent/'attempt_lifetime/test_lifecycle.py'),run_name='__main__')
