"""Entry point for launching the map production grid."""

from __future__ import annotations

import map_functions


def main() -> None:
    """Kick off the Tkinter main loop for an interactive grid window."""
    dimensions = map_functions.prompt_for_grid_dimensions()
    if dimensions is None:
        return  # User cancelled the setup dialog

    cols, rows = dimensions
    root = map_functions.create_grid_window(cols, rows)
    root.mainloop()


if __name__ == "__main__":
    main()
