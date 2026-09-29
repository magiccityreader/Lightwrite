# Legacy Python Lightwrite (1.2.x)

The curses/Python implementation archived when Lightwrite 2.0 moved to Go + Charm.
Run from this directory:

```bash
PYTHONPATH=src python3 -m lightwrite
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 tests/smoke_pty.py
```
