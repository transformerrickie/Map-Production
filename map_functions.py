"""Grid creation and interaction helpers for the map production tool."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from datetime import datetime
from typing import Dict, Final, Optional, Tuple
from tkinter import messagebox

try:
    from PIL import Image, ImageDraw
except ImportError:  # Pillow is optional but required for exports.
    Image = None
    ImageDraw = None

# Public constants that describe the grid layout and styling.
DEFAULT_COLS: Final[int] = 20
DEFAULT_ROWS: Final[int] = 10
MAX_DIMENSION: Final[int] = 50
MIN_DIMENSION: Final[int] = 1
CELL_SIZE: Final[int] = 20  # pixel size of each square
WINDOW_BACKGROUND: Final[str] = "#cccccc"
MARGIN_COLOR: Final[str] = "white"
FILL_COLOR: Final[str] = "white"
OUTLINE_COLOR: Final[str] = "black"
OUTLINE_WIDTH: Final[int] = 1
PADDING: Final[int] = 10  # additional pixel padding around the border blocks
CELL_TAG: Final[str] = "cell"
GREY_FILL: Final[str] = "#808080"
FIXED_BORDER_TAG: Final[str] = "fixed-border"
FIXED_BORDER_FILL: Final[str] = "black"
BLUE_TILE_FILL: Final[str] = "#1e90ff"
RED_TILE_FILL: Final[str] = "#ff4040"
BORDER_THICKNESS_CELLS: Final[int] = 1
SAVE_BUTTON_TEXT: Final[str] = "[save?]"
SELECT_BLUE_BUTTON_TEXT: Final[str] = "[select blue tile]"
SELECT_RED_BUTTON_TEXT: Final[str] = "[select red tile]"
DEFAULT_FILENAME_TEMPLATE: Final[str] = "map_snapshot_{timestamp}.jpg"
GRID_DESCRIPTION: Final[str] = (
    "Black blocks - hard-coded boundaries.\n"
    "Blue block - player entering location.\n"
    "Red block - drone entering location (or drone base).\n"
    "Grey blocks - walls or obstacles the drone cannot pass.\n"
    "White blocks - pathways and open areas for both player and drone."
)


def prompt_for_grid_dimensions(
    default_cols: int = DEFAULT_COLS,
    default_rows: int = DEFAULT_ROWS,
) -> Optional[Tuple[int, int]]:
    """Prompt the user for grid dimensions and return a validated pair."""
    prompt = tk.Tk()
    prompt.title("Map Grid Setup")
    prompt.resizable(False, False)
    prompt.configure(padx=20, pady=20)

    cols_var = tk.StringVar(value=str(default_cols))
    rows_var = tk.StringVar(value=str(default_rows))
    error_var = tk.StringVar(value="")
    result: Dict[str, Optional[Tuple[int, int]]] = {"value": None}

    def parse_dimension(value: str) -> Optional[int]:
        try:
            dimension = int(value)
        except ValueError:
            return None
        if dimension < MIN_DIMENSION or dimension > MAX_DIMENSION:
            return None
        return dimension

    def on_confirm(_: object = None) -> None:
        error_var.set("")
        cols_value = parse_dimension(cols_var.get())
        rows_value = parse_dimension(rows_var.get())
        if cols_value is None or rows_value is None:
            error_var.set("please re-enter valid number")
            return
        result["value"] = (cols_value, rows_value)
        prompt.destroy()

    def on_close() -> None:
        result["value"] = None
        prompt.destroy()

    prompt.protocol("WM_DELETE_WINDOW", on_close)

    tk.Label(prompt, text="Columns (1-50):").grid(row=0, column=0, sticky="w", pady=(0, 5))
    tk.Entry(prompt, textvariable=cols_var, width=10).grid(row=0, column=1, pady=(0, 5))

    tk.Label(prompt, text="Rows (1-50):").grid(row=1, column=0, sticky="w", pady=(0, 5))
    tk.Entry(prompt, textvariable=rows_var, width=10).grid(row=1, column=1, pady=(0, 5))

    tk.Button(prompt, text="confirm", command=on_confirm).grid(row=2, column=0, columnspan=2, pady=(10, 0))
    tk.Label(prompt, textvariable=error_var, fg="red").grid(row=3, column=0, columnspan=2, pady=(5, 0))

    prompt.bind("<Return>", on_confirm)
    prompt.mainloop()

    return result["value"]


def _color_cell(canvas: tk.Canvas, x: int, y: int, fill_color: str) -> None:
    """Update the fill color of the grid cell under the given coordinates."""
    root_widget = canvas.master
    if getattr(root_widget, "selecting_blue_tile", False) or getattr(
        root_widget, "selecting_red_tile", False
    ):
        return

    overlap = canvas.find_overlapping(x, y, x, y)
    for item_id in overlap:
        tags = canvas.gettags(item_id)
        if FIXED_BORDER_TAG in tags:
            return  # fixed border squares remain unchanged
        if CELL_TAG in tags:
            canvas.itemconfigure(item_id, fill=fill_color)
            return


def _border_item_from_event(canvas: tk.Canvas, event: tk.Event) -> Optional[int]:
    """Locate a fixed-border item under the cursor for the given event."""
    items = canvas.find_withtag("current")
    if not items:
        items = canvas.find_overlapping(event.x, event.y, event.x, event.y)
    for item_id in items:
        if FIXED_BORDER_TAG in canvas.gettags(item_id):
            return item_id
    return None


def _positions_adjacent(
    first: Optional[Tuple[int, int]],
    second: Optional[Tuple[int, int]],
) -> bool:
    """Return True when the two border positions are orthogonally adjacent."""
    if first is None or second is None:
        return False
    col_a, row_a = first
    col_b, row_b = second
    return abs(col_a - col_b) + abs(row_a - row_b) == 1


def _apply_blue_tile(canvas: tk.Canvas, root: tk.Tk, item_id: int) -> None:
    """Assign the blue tile to the specified border rectangle."""
    previous_id = getattr(root, "blue_tile_id", None)
    if previous_id and previous_id != item_id:
        try:
            canvas.itemconfigure(previous_id, fill=FIXED_BORDER_FILL)
        except tk.TclError:
            pass
    canvas.itemconfigure(item_id, fill=BLUE_TILE_FILL)
    root.blue_tile_id = item_id


def _clear_blue_tile(canvas: tk.Canvas, root: tk.Tk, item_id: Optional[int] = None) -> None:
    """Remove the blue tile colouring, restoring the original border fill."""
    target_id = item_id if item_id is not None else getattr(root, "blue_tile_id", None)
    if target_id is None:
        return
    try:
        canvas.itemconfigure(target_id, fill=FIXED_BORDER_FILL)
    except tk.TclError:
        pass
    if getattr(root, "blue_tile_id", None) == target_id:
        root.blue_tile_id = None


def _apply_red_tile(canvas: tk.Canvas, root: tk.Tk, item_id: int) -> None:
    """Assign the red tile to the specified border rectangle."""
    previous_id = getattr(root, "red_tile_id", None)
    if previous_id and previous_id != item_id:
        try:
            canvas.itemconfigure(previous_id, fill=FIXED_BORDER_FILL)
        except tk.TclError:
            pass
    canvas.itemconfigure(item_id, fill=RED_TILE_FILL)
    root.red_tile_id = item_id


def _clear_red_tile(canvas: tk.Canvas, root: tk.Tk, item_id: Optional[int] = None) -> None:
    """Remove the red tile colouring, restoring the original border fill."""
    target_id = item_id if item_id is not None else getattr(root, "red_tile_id", None)
    if target_id is None:
        return
    try:
        canvas.itemconfigure(target_id, fill=FIXED_BORDER_FILL)
    except tk.TclError:
        pass
    if getattr(root, "red_tile_id", None) == target_id:
        root.red_tile_id = None


def enable_left_click_grey(canvas: tk.Canvas) -> None:
    """Allow users to turn cells grey while holding the left mouse button."""
    handler = lambda event: _color_cell(canvas, event.x, event.y, GREY_FILL)
    canvas.tag_bind(CELL_TAG, "<Button-1>", handler, add=True)
    canvas.tag_bind(CELL_TAG, "<B1-Motion>", handler, add=True)
    canvas.bind("<B1-Motion>", handler, add=True)


def enable_right_click_white(canvas: tk.Canvas, white_fill: str) -> None:
    """Allow users to reset cells to white while holding the right mouse button."""
    handler = lambda event: _color_cell(canvas, event.x, event.y, white_fill)
    canvas.tag_bind(CELL_TAG, "<Button-3>", handler, add=True)
    canvas.tag_bind(CELL_TAG, "<B3-Motion>", handler, add=True)
    canvas.bind("<B3-Motion>", handler, add=True)


def save_canvas_snapshot(
    canvas: tk.Canvas,
    filename: Optional[str] = None,
) -> Optional[Path]:
    """Render the canvas contents to a JPEG file without relying on screen capture."""
    if Image is None or ImageDraw is None:
        messagebox.showerror(
            "Save Failed",
            "Saving screenshots requires Pillow (PIL) with Image and ImageDraw modules.",
        )
        return None

    try:
        canvas.update_idletasks()
        width = int(canvas.winfo_width())
        height = int(canvas.winfo_height())
        image = Image.new("RGB", (width, height), color=MARGIN_COLOR)
        draw = ImageDraw.Draw(image)

        def _draw_items(tag: str) -> None:
            for item_id in canvas.find_withtag(tag):
                coords = canvas.coords(item_id)
                if len(coords) != 4:
                    continue
                x0, y0, x1, y1 = (int(round(value)) for value in coords)
                fill = canvas.itemcget(item_id, "fill") or MARGIN_COLOR
                outline = canvas.itemcget(item_id, "outline") or ""
                outline_width_str = canvas.itemcget(item_id, "width")
                try:
                    outline_width = max(1, int(round(float(outline_width_str))))
                except (TypeError, ValueError):
                    outline_width = OUTLINE_WIDTH
                draw.rectangle(
                    [x0, y0, x1, y1],
                    fill=fill,
                    outline=outline if outline else None,
                    width=outline_width,
                )

        _draw_items(FIXED_BORDER_TAG)
        _draw_items(CELL_TAG)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = Path(__file__).resolve().parent
        filename = filename or DEFAULT_FILENAME_TEMPLATE.format(timestamp=timestamp)
        target_path = target_dir / filename
        image.save(target_path, "JPEG")
    except Exception as exc:  # safeguard unexpected capture issues
        messagebox.showerror("Save Failed", f"Unable to save screenshot:\n{exc}")
        return None

    messagebox.showinfo("Saved", f"Screenshot saved to:\n{target_path}")
    return target_path


def create_grid_window(cols: int, rows: int) -> tk.Tk:
    """Create and return a Tkinter window with an interactive grid."""
    root = tk.Tk()
    root.title("Map Production Grid")
    root.configure(bg=WINDOW_BACKGROUND)

    border_pixels = BORDER_THICKNESS_CELLS * CELL_SIZE
    grid_left = PADDING + border_pixels
    grid_top = PADDING + border_pixels
    grid_width = cols * CELL_SIZE
    grid_height = rows * CELL_SIZE

    canvas_width = grid_width + (PADDING + border_pixels) * 2
    canvas_height = grid_height + (PADDING + border_pixels) * 2

    canvas = tk.Canvas(
        root,
        width=canvas_width,
        height=canvas_height,
        bg=MARGIN_COLOR,
        highlightthickness=0,
    )
    canvas.pack(padx=20, pady=20)
    root.canvas = canvas  # expose canvas for callers that need direct access
    root.grid_cols = cols
    root.grid_rows = rows
    root.blue_tile_id = None
    root.selecting_blue_tile = False
    root.red_tile_id = None
    root.selecting_red_tile = False
    root.border_positions: Dict[int, Tuple[int, int]] = {} # type: ignore
    status_var = tk.StringVar(value="")

    def set_status(message: str) -> None:
        status_var.set(message)

    def handle_border_left_click(event: tk.Event) -> None:
        if not root.selecting_blue_tile and not root.selecting_red_tile:
            return
        item_id = _border_item_from_event(canvas, event)
        if item_id is None:
            return

        item_pos = root.border_positions.get(item_id)

        if root.selecting_blue_tile:
            if root.red_tile_id == item_id:
                messagebox.showerror("Blue Tile", "Blue and red tiles cannot occupy the same block.")
                set_status("Blue tile location unavailable; overlaps red tile.")
                return
            red_pos = (
                root.border_positions.get(root.red_tile_id)
                if root.red_tile_id is not None
                else None
            )
            if _positions_adjacent(item_pos, red_pos):
                messagebox.showerror("Blue Tile", "Blue tile cannot be placed next to the red tile.")
                set_status("Blue tile must not touch the red tile.")
                return
            _apply_blue_tile(canvas, root, item_id)
            root.selecting_blue_tile = False
            select_blue_button.config(state="normal")
            select_red_button.config(state="normal")
            set_status("Blue tile placed.")

        elif root.selecting_red_tile:
            if root.blue_tile_id == item_id:
                messagebox.showerror("Red Tile", "Red and blue tiles cannot occupy the same block.")
                set_status("Red tile location unavailable; overlaps blue tile.")
                return
            blue_pos = (
                root.border_positions.get(root.blue_tile_id)
                if root.blue_tile_id is not None
                else None
            )
            if _positions_adjacent(item_pos, blue_pos):
                messagebox.showerror("Red Tile", "Red tile cannot be placed next to the blue tile.")
                set_status("Red tile must not touch the blue tile.")
                return
            _apply_red_tile(canvas, root, item_id)
            root.selecting_red_tile = False
            select_red_button.config(state="normal")
            select_blue_button.config(state="normal")
            set_status("Red tile placed.")

    def handle_border_right_click(event: tk.Event) -> None:
        if not root.selecting_blue_tile and not root.selecting_red_tile:
            return
        item_id = _border_item_from_event(canvas, event)
        if item_id is None:
            return
        if root.selecting_blue_tile:
            if root.blue_tile_id == item_id:
                _clear_blue_tile(canvas, root, item_id)
                root.selecting_blue_tile = False
                select_blue_button.config(state="normal")
                select_red_button.config(state="normal")
                set_status("Blue tile cleared.")
            elif root.blue_tile_id is None:
                root.selecting_blue_tile = False
                select_blue_button.config(state="normal")
                select_red_button.config(state="normal")
                set_status("Blue tile selection cancelled.")
        elif root.selecting_red_tile:
            if root.red_tile_id == item_id:
                _clear_red_tile(canvas, root, item_id)
                root.selecting_red_tile = False
                select_red_button.config(state="normal")
                select_blue_button.config(state="normal")
                set_status("Red tile cleared.")
            elif root.red_tile_id is None:
                root.selecting_red_tile = False
                select_red_button.config(state="normal")
                select_blue_button.config(state="normal")
                set_status("Red tile selection cancelled.")

    # Draw the primary grid of editable cells.
    for row in range(rows):
        for col in range(cols):
            x0 = grid_left + col * CELL_SIZE
            y0 = grid_top + row * CELL_SIZE
            x1 = x0 + CELL_SIZE
            y1 = y0 + CELL_SIZE
            canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=FILL_COLOR,
                outline=OUTLINE_COLOR,
                width=OUTLINE_WIDTH,
                tags=(CELL_TAG,),
            )

    # Surround the grid with a ring of fixed border blocks.
    def _draw_border_cell(col_index: int, row_index: int, *, fill: str = FIXED_BORDER_FILL) -> None:
        bx0 = grid_left + col_index * CELL_SIZE
        by0 = grid_top + row_index * CELL_SIZE
        bx1 = bx0 + CELL_SIZE
        by1 = by0 + CELL_SIZE
        item_id = canvas.create_rectangle(
            bx0,
            by0,
            bx1,
            by1,
            fill=fill,
            outline=OUTLINE_COLOR,
            width=OUTLINE_WIDTH,
            tags=(FIXED_BORDER_TAG,),
        )
        root.border_positions[item_id] = (col_index, row_index)

    # Top and bottom rows (including corners)
    for col_index in range(-BORDER_THICKNESS_CELLS, cols + BORDER_THICKNESS_CELLS):
        _draw_border_cell(col_index, -BORDER_THICKNESS_CELLS)
        _draw_border_cell(col_index, rows)

    # Left and right columns (exclude corners already drawn)
    for row_index in range(rows):
        _draw_border_cell(-BORDER_THICKNESS_CELLS, row_index)
        _draw_border_cell(cols, row_index)

    canvas.tag_raise(FIXED_BORDER_TAG)
    canvas.tag_bind(FIXED_BORDER_TAG, "<Button-1>", handle_border_left_click, add=True)
    canvas.tag_bind(FIXED_BORDER_TAG, "<Button-3>", handle_border_right_click, add=True)

    enable_left_click_grey(canvas)
    enable_right_click_white(canvas, FILL_COLOR)

    description_label = tk.Label(
        root,
        text=GRID_DESCRIPTION,
        justify="left",
        anchor="w",
        bg=WINDOW_BACKGROUND,
        wraplength=canvas_width,
    )
    description_label.pack(padx=20, pady=(5, 0), anchor="w", fill="x")

    def start_blue_tile_selection() -> None:
        if root.selecting_blue_tile:
            return
        if root.selecting_red_tile:
            set_status("Finish placing the red tile before choosing the blue tile.")
            return
        root.selecting_blue_tile = True
        select_blue_button.config(state="disabled")
        select_red_button.config(state="disabled")
        set_status("Select a border block for the blue tile. Right-click the current blue tile to clear it.")

    def start_red_tile_selection() -> None:
        if root.selecting_red_tile:
            return
        if root.selecting_blue_tile:
            set_status("Finish placing the blue tile before choosing the red tile.")
            return
        root.selecting_red_tile = True
        select_red_button.config(state="disabled")
        select_blue_button.config(state="disabled")
        set_status("Select a border block for the red tile. Right-click the current red tile to clear it.")

    button_frame = tk.Frame(root)
    button_frame.pack(pady=(10, 0))

    def guarded_save() -> None:
        if root.blue_tile_id is None or root.red_tile_id is None:
            messagebox.showerror(
                "Save Blocked",
                "Place both the blue and red border tiles before saving a screenshot.",
            )
            return
        save_canvas_snapshot(canvas)

    save_button = tk.Button(
        button_frame,
        text=SAVE_BUTTON_TEXT,
        command=guarded_save,
    )
    save_button.pack(side="left", padx=5)

    select_blue_button = tk.Button(
        button_frame,
        text=SELECT_BLUE_BUTTON_TEXT,
        command=start_blue_tile_selection,
    )
    select_blue_button.pack(side="left", padx=5)

    select_red_button = tk.Button(
        button_frame,
        text=SELECT_RED_BUTTON_TEXT,
        command=start_red_tile_selection,
    )
    select_red_button.pack(side="left", padx=5)

    status_label = tk.Label(root, textvariable=status_var, fg="blue")
    status_label.pack(pady=(5, 0))
    set_status("Use the buttons to place blue and red border tiles.")

    return root
