"""Allow running as `python -m invest_signal_kit`."""

import sys

from .cli import main

sys.exit(main())
