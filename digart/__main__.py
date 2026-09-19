"""Allow ``python -m digart``."""

import sys

from digart.main_entry import main

if __name__ == "__main__":
    sys.exit(main())
