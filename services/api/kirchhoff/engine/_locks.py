"""A single process-wide lock shared by every module that enters pandapower's `warnings.catch_warnings()`
region (warning filters are process-global, not thread-safe, so two modules using separate locks could still
race against each other)."""
import threading

WARNINGS_LOCK = threading.Lock()
