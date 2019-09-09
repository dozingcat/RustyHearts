from dataclasses import dataclass
import math
from typing import Iterable, List, Tuple

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label


def set_rect_background(widget, color: Iterable[float]):
    with widget.canvas.before:
        Color(*color)
        widget._commands_ = {
            'background': Rectangle(size=widget.size)
        }
    def update(inst, value):
        widget._commands_['background'].pos = inst.pos
        widget._commands_['background'].size = inst.size
    widget.bind(pos=update, size=update)


def make_label(**kwargs):
    '''Creates a label and binds its `text_size` to its `size`, allowing
    alignment to work as expected. Defaults to center alignment.
    See http://inclem.net/2014/07/05/kivy/kivy_label_text/
    '''
    kwargs.setdefault('halign', 'center')
    kwargs.setdefault('valign', 'middle')
    label = Label(**kwargs)
    def update(inst, value):
        label.text_size = label.size
    label.bind(size=update)
    return label


def set_round_rect_background(widget, color: Iterable[float], radius: float):
    diam = 2 * radius
    with widget.canvas.before:
        Color(*color)
        circle_size = (diam, diam)
        widget._commands_ = {
            'left_strip': Rectangle(),
            'right_strip': Rectangle(),
            'main_rect': Rectangle(),
            # 0 degrees is up, 90 is right.
            'bottom_left_corner': Ellipse(size=circle_size, angle_start=180, angle_end=270),
            'bottom_right_corner': Ellipse(size=circle_size, angle_start=90, angle_end=180),
            'top_left_corner': Ellipse(size=circle_size, angle_start=270, angle_end=360),
            'top_right_corner': Ellipse(size=circle_size, angle_start=0, angle_end=90),
        }
    def update(inst, value):
        px, py = inst.pos
        sx, sy = inst.size
        c = widget._commands_
        c['left_strip'].pos = (px, py + radius)
        c['left_strip'].size = (radius, sy - diam)
        c['right_strip'].pos = (px + sx - radius, py + radius)
        c['right_strip'].size = (radius, sy - diam)
        c['main_rect'].pos = (px + radius, py)
        c['main_rect'].size = (sx - diam, sy)
        c['bottom_left_corner'].pos = (px, py)
        c['bottom_right_corner'].pos = (px + sx - diam, py)
        c['top_left_corner'].pos = (px, py + sy - diam)
        c['top_right_corner'].pos = (px + sx - diam, py + sy - diam)
    widget.bind(pos=update, size=update)


def label_size(text: str, font_size: float) -> Tuple[int, int]:
   label = CoreLabel(text=text, font_size=font_size)
   label.refresh()
   r1 = label.texture.size
   label.text = text + text
   label.refresh()
   r2 = label.texture.size
   return r1 + r2


@dataclass
class AutosizeTableCell:
    text: str
    layout_weight: int = 1
    relative_font_size: float = 1.0
    relative_padding: float = 0.2
    halign: str = 'center'
    valign: str = 'middle'


@dataclass
class AutosizeTableResult:
    layout: BoxLayout
    base_font_size: float
    width: float
    height: float


def _required_size_for_cells(cells: List[List[AutosizeTableCell]],
                            base_font_size: float) -> Tuple[int, int]:
    required_width = 0
    required_height = 0
    label = None
    last_font_size = -1
    for row in cells:
        row_height = 0
        sumw = sum([cell.layout_weight for cell in row])
        weight_ratios = [sumw / cell.layout_weight for cell in row]
        for cell, wrat in zip(row, weight_ratios):
            fsize = base_font_size * cell.relative_font_size
            # Updating an existing label's font size doesn't affect its computed
            # size, so we have to recreate it if the font size changes.
            if label is None or last_font_size != fsize:
                print(f'New label: {fsize}')
                pad = fsize * cell.relative_padding
                label = CoreLabel(font_size=fsize, padding=pad)
            last_font_size = fsize
            label.text = cell.text
            label.refresh()
            size = label.texture.size
            required_width = max(required_width, size[0] * wrat)
            row_height = max(row_height, size[1])
        required_height += row_height
    return (required_width, required_height)


def create_autosize_table(cells: List[List[AutosizeTableCell]],
                          max_width, max_height) -> AutosizeTableResult:
    table = BoxLayout(orientation='vertical')
    test_base_font_size = 20
    actual_size = _required_size_for_cells(cells, test_base_font_size)
    scale = min(max_width / actual_size[0], max_height / actual_size[1])
    base_font_size = test_base_font_size * scale
    print(f'base_size: {actual_size}, scale: {scale}')
    for row in cells:
        # The height of each row is proportional to its maximum font size, so
        # we can use that as the size hint.
        max_font_size = max(cell.relative_font_size for cell in row)
        row_layout = BoxLayout(orientation='horizontal', size_hint=(1, max_font_size))
        for cell in row:
            # Use a slightly smaller font size than computed to avoid overflow.
            fsize = base_font_size * cell.relative_font_size * 0.9
            padding = (fsize * cell.relative_padding,) * 2
            label = make_label(
                text=cell.text,
                size_hint=(cell.layout_weight, 1),
                font_size=fsize,
                padding=padding,
                halign=cell.halign,
                valign=cell.valign,
            )
            row_layout.add_widget(label)
        table.add_widget(row_layout)

    actual_width = actual_size[0] * scale
    actual_height = actual_size[1] * scale
    return AutosizeTableResult(
        layout=table, width=actual_width, height=actual_height, base_font_size=base_font_size)
