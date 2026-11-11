"""Jozi Buddy Secure Study Studio."""
import os

# Inherited TLS key-log destinations can be unwritable in IDE terminals.
os.environ.pop("SSLKEYLOGFILE", None)
