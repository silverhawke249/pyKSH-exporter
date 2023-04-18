import sys

import dearpygui.dearpygui as dpg
import dearpygui.demo as demo

from typing import Any

from ksh2vox.classes.enums import DifficultySlot, GameBackground, InfVer
from ksh2vox.parser.ksh import KSHParser

SONG_INFO_FIELDS = [
    'id',
    'title',
    'title_yomigana',
    'artist',
    'artist_yomigana',
    'ascii_label',
    'min_bpm',
    'max_bpm',
    'release_date',
    'music_volume',
    'background',
    'inf_ver',
]
CHART_INFO_FIELDS = [
    'level',
    'difficulty',
    'effector',
    'illustrator',
]


def dpg_demo():
    dpg.create_context()
    dpg.create_viewport()
    dpg.setup_dearpygui()

    demo.show_demo()

    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()


class KSH2VOXApp():
    ui: dict[str, int | str]
    parser: KSHParser

    def __init__(self):
        self.ui = {}

        dpg.create_context()
        dpg.create_viewport(title='ksh-vox converter', width=600, height=800, resizable=False)
        dpg.setup_dearpygui()

        with dpg.font_registry():
            with dpg.font('resources/NotoSansJP-Regular.ttf', 20) as font:
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)

            dpg.bind_font(font)

        with dpg.window(label='ksh-vox converter') as primary_window:
            self.ui['primary_window'] = primary_window

            with dpg.group(horizontal=True):
                dpg.add_button(label='Open file...', width=150, height=40, callback=self._show_file_dialog)

                with dpg.group():
                    dpg.add_spacer(height=2)
                    self.ui['loaded_file'] = dpg.add_text('[no file loaded]')

            dpg.add_spacer(height=1)

            with dpg.table(header_row=False, show=False) as save_group:
                self.ui['save_group'] = save_group

                dpg.add_table_column(width_stretch=True)
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_fixed=True)

                with dpg.table_row():
                    dpg.add_spacer()
                    dpg.add_button(label='Save XML...', width=150, height=40)
                    dpg.add_button(label='Save VOX...', width=150, height=40)

            dpg.add_spacer(height=1)

            with dpg.file_dialog(
                width=500, height=400, show=False, callback=self._load_file, modal=True
            ) as open_dialog:
                self.ui['file_dialog'] = open_dialog

                dpg.add_file_extension('.ksh')

            with dpg.group() as info_group:
                self.ui['info_group'] = info_group

                with dpg.collapsing_header(label='Song info', show=False, default_open=True) as section_song_info:
                    self.ui['section_song_info'] = section_song_info

                    self.ui['id']              = dpg.add_input_int(label='Song ID', min_clamped=True)
                    self.ui['title']           = dpg.add_input_text(label='Song title')
                    self.ui['title_yomigana']  = dpg.add_input_text(label='Song title (yomigana)', hint='Song title in half-width katakana')
                    self.ui['artist']          = dpg.add_input_text(label='Song artist')
                    self.ui['artist_yomigana'] = dpg.add_input_text(label='Song artist (yomigana)', hint='Song artist in half-width katakana')
                    self.ui['ascii_label']     = dpg.add_input_text(label='Song label', hint='Song identifier in filesystem')
                    self.ui['min_bpm']         = dpg.add_input_float(label='Minimum BPM', min_value=0, max_value=1000, min_clamped=True, max_clamped=True, format='%.2f')
                    self.ui['max_bpm']         = dpg.add_input_float(label='Maximum BPM', min_value=0, max_value=1000, min_clamped=True, max_clamped=True, format='%.2f')
                    self.ui['release_date']    = dpg.add_input_text(label='Release date', decimal=True)
                    self.ui['music_volume']    = dpg.add_slider_int(label='Music volume', clamped=True, min_value=0, max_value=100)
                    self.ui['background']      = dpg.add_combo(list(GameBackground), label='Game background')
                    self.ui['inf_ver']         = dpg.add_combo(list(InfVer), label='Infinite version')

                    # TODO: Background preview

                with dpg.collapsing_header(label='Chart info', show=False, default_open=True) as section_chart_info:
                    self.ui['section_chart_info'] = section_chart_info

                    self.ui['level'] = dpg.add_slider_int(label='Level', clamped=True, min_value=1, max_value=20)
                    self.ui['difficulty'] = dpg.add_combo(list(DifficultySlot), label='Difficulty')
                    self.ui['effector'] = dpg.add_input_text(label='Effector')
                    self.ui['illustrator'] = dpg.add_input_text(label='Illustrator')

                with dpg.collapsing_header(label='Effect info', show=False, default_open=True) as section_effect_info:
                    self.ui['section_effect_info'] = section_effect_info

                    self.ui['effect_table'] = dpg.add_table(header_row=False)

                with dpg.collapsing_header(label='Track auto tab info', show=False, default_open=True) as section_filter_info:
                    self.ui['section_filter_info'] = section_filter_info

        with dpg.theme() as theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (23, 60, 95), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Header, (23, 60, 95), category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5, category=dpg.mvThemeCat_Core)

        dpg.bind_item_theme(primary_window, theme)
        dpg.set_primary_window(primary_window, True)

        dpg.show_viewport()
        dpg.start_dearpygui()

        dpg.destroy_context()

    def _load_file(self, sender: str | int, app_data: dict[str, Any]):
        file_path = app_data['file_path_name']
        dpg.set_value(self.ui['loaded_file'], file_path)

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            self.parser = KSHParser(f)

        for field in SONG_INFO_FIELDS:
            dpg.set_value(self.ui[field], getattr(self.parser._song_info, field))
        for field in CHART_INFO_FIELDS:
            dpg.set_value(self.ui[field], getattr(self.parser._chart_info, field))

        dpg.delete_item(self.ui['effect_table'], children_only=True)

        dpg.add_table_column(parent=self.ui['effect_table'], width_fixed=True)
        dpg.add_table_column(parent=self.ui['effect_table'], width_stretch=True, init_width_or_weight=0.0)

        for i, effect_name in enumerate(self.parser._fx_list):
            with dpg.table_row(parent=self.ui['effect_table']):
                dpg.add_text(effect_name)
                dpg.add_text(self.parser._chart_info.effect_list[i])

        dpg.show_item(self.ui['save_group'])
        dpg.show_item(self.ui['section_song_info'])
        dpg.show_item(self.ui['section_chart_info'])
        dpg.show_item(self.ui['section_effect_info'])

    def _show_file_dialog(self):
        dpg.show_item(self.ui['file_dialog'])


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'demo':
        dpg_demo()
    else:
        KSH2VOXApp()
