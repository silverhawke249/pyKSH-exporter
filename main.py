import sys
import time
import warnings

import dearpygui.dearpygui as dpg
import dearpygui.demo as demo

from pathlib import Path
from tkinter import filedialog
from typing import Any

from ksh2vox.classes.enums import DifficultySlot, GameBackground, InfVer
from ksh2vox.parser.ksh import KSHParser

ObjectID = int | str
SLOT_MAPPING = {
    DifficultySlot.NOVICE  : 'LI',
    DifficultySlot.ADVANCED: 'CH',
    DifficultySlot.EXHAUST : 'EX',
    DifficultySlot.INFINITE: 'IN',
    DifficultySlot.MAXIMUM : 'IN',
}
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
    ui: dict[str, ObjectID]
    reverse_ui_map: dict[ObjectID, str]

    parser: KSHParser

    save_type: str

    current_path: Path | None = None

    def __init__(self):
        self.ui = {}
        self.reverse_ui_map = {}

        warnings.simplefilter('always')
        warnings.showwarning = self.log_warning

        dpg.create_context()
        dpg.create_viewport(title='ksh-vox converter', width=600, height=800, resizable=False)
        dpg.setup_dearpygui()

        with dpg.window(label='ksh-vox converter') as primary_window:
            self.ui['primary_window'] = primary_window

            with dpg.group() as main_buttons:
                with dpg.group(horizontal=True):
                    self.ui['open_button'] = dpg.add_button(label='Open file...', callback=self.load_file)
                    self.ui['loaded_file'] = dpg.add_text('[no file loaded]')

                dpg.add_spacer(height=1)

                with dpg.group(horizontal=True) as save_group:
                    self.ui['save_group'] = save_group

                    self.ui['vox_button'] = dpg.add_button(label='Save VOX...', callback=self.export_vox, enabled=False)
                    self.ui['xml_button'] = dpg.add_button(label='Save XML...', callback=self.export_xml, enabled=False)
                    self.ui['2dx_button'] = dpg.add_button(label='Export 2DX...', callback=self.export_2dx, enabled=False)
                    self.ui['jackets_button'] = dpg.add_button(label='Export jackets...', callback=self.export_jacket, enabled=False)

            dpg.add_spacer(height=1)

            with dpg.child_window(height=533, border=False, autosize_x=True) as info_container:
                self.ui['info_container'] = info_container
                with dpg.tab_bar():
                    with dpg.tab(label='Song info') as section_song_info:
                        self.ui['section_song_info'] = section_song_info

                        self.ui['id']              = dpg.add_input_int(
                            label='Song ID', min_clamped=True, callback=self.update_and_validate)
                        self.ui['title']           = dpg.add_input_text(
                            label='Song title', callback=self.update_and_validate)
                        self.ui['title_yomigana']  = dpg.add_input_text(
                            label='Song title (yomigana)', hint='Song title in half-width katakana',
                            callback=self.update_and_validate)
                        self.ui['artist']          = dpg.add_input_text(
                            label='Song artist', callback=self.update_and_validate)
                        self.ui['artist_yomigana'] = dpg.add_input_text(
                            label='Song artist (yomigana)', hint='Song artist in half-width katakana',
                            callback=self.update_and_validate)
                        self.ui['ascii_label']     = dpg.add_input_text(
                            label='Song label', hint='Song identifier in filesystem (ASCII only)',
                            callback=self.update_and_validate)
                        self.ui['min_bpm']         = dpg.add_input_float(
                            label='Minimum BPM', min_value=0, max_value=1000, min_clamped=True, max_clamped=True,
                            format='%.2f', callback=self.update_and_validate)
                        self.ui['max_bpm']         = dpg.add_input_float(
                            label='Maximum BPM', min_value=0, max_value=1000, min_clamped=True, max_clamped=True,
                            format='%.2f', callback=self.update_and_validate)
                        self.ui['release_date']    = dpg.add_input_text(
                            label='Release date', decimal=True, callback=self.update_and_validate)
                        self.ui['music_volume']    = dpg.add_slider_int(
                            label='Music volume', clamped=True, min_value=0, max_value=100,
                            callback=self.update_and_validate)
                        self.ui['background']      = dpg.add_combo(
                            list(GameBackground), label='Game background', callback=self.update_and_validate)
                        self.ui['inf_ver']         = dpg.add_combo(
                            list(InfVer), label='Infinite version', callback=self.update_and_validate)

                        # TODO: Background preview

                    with dpg.tab(label='Chart info') as section_chart_info:
                        self.ui['section_chart_info'] = section_chart_info

                        self.ui['level'] = dpg.add_slider_int(
                            label='Level', clamped=True, min_value=1, max_value=20, callback=self.update_and_validate)
                        self.ui['difficulty'] = dpg.add_combo(
                            list(DifficultySlot), label='Difficulty', callback=self.update_and_validate)
                        self.ui['effector'] = dpg.add_input_text(
                            label='Effector', callback=self.update_and_validate)
                        self.ui['illustrator'] = dpg.add_input_text(
                            label='Illustrator', callback=self.update_and_validate)

                    with dpg.tab(label='Effects') as section_effect_info:
                        self.ui['section_effect_info'] = section_effect_info

                        dpg.add_text('Coming soon!')
                        # self.ui['effect_table'] = dpg.add_table(header_row=False, borders_innerH=True, borders_innerV=True)

                    with dpg.tab(label='Filter mapping') as section_filter_info:
                        self.ui['section_filter_info'] = section_filter_info

                        dpg.add_text('Coming soon!')
                        # self.ui['filter_mapping'] = dpg.add_table(header_row=False, borders_innerH=True, borders_innerV=True)

                    with dpg.tab(label='Track autotab') as section_autotab_info:
                        self.ui['section_autotab_info'] = section_autotab_info

                        dpg.add_text('Coming soon!')
                        # self.ui['autotab_info'] = dpg.add_table(header_row=False, borders_innerH=True, borders_innerV=True)

            # Width is viewport width - 2 * mvStyleVar_WindowPadding[0]
            # x-position is mvStyleVar_WindowPadding[1]
            # y-position is viewport height - mvStyleVar_WindowPadding[1] - self height
            with dpg.child_window(label='Logs', width=584, height=150, pos=(8, 642), horizontal_scrollbar=True) as log_window:
                self.ui['log'] = log_window

        with dpg.window(show=False, modal=True) as popup_window:
            self.ui['popup_window'] = popup_window

            self.ui['popup_text'] = dpg.add_text()
            dpg.add_button(label='OK', callback=lambda _: dpg.hide_item(popup_window))

        with dpg.font_registry():
            with dpg.font('resources/NotoSansJP-Regular.ttf', 20) as font:
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)

            dpg.bind_font(font)

        with dpg.theme() as button_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 20, 8, category=dpg.mvThemeCat_Core)

        dpg.bind_item_theme(main_buttons, button_theme)

        with dpg.theme() as log_theme:
            with dpg.theme_component(dpg.mvText):
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 4, 0, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 0, category=dpg.mvThemeCat_Core)

        dpg.bind_item_theme(log_window, log_theme)

        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (23, 60, 95), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Header, (23, 60, 95), category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5, category=dpg.mvThemeCat_Core)

        dpg.bind_item_theme(primary_window, global_theme)
        dpg.set_primary_window(primary_window, True)

        dpg.show_viewport()
        dpg.start_dearpygui()

        dpg.destroy_context()

    def log_warning(self, message, category, filename, lineno, file=None, line=None):
        self.log(f'Warning: {message}')

    def log(self, message):
        dpg.add_text(
            f'[{time.strftime("%H:%M:%S", time.localtime())}] {message}',
            parent=self.ui['log'])

        y_max = dpg.get_y_scroll_max(self.ui['log'])
        dpg.set_y_scroll(self.ui['log'], y_max)

    def get_obj_name(self, uuid: ObjectID):
        if uuid not in self.reverse_ui_map:
            for obj_name, c_uuid in self.ui.items():
                if uuid == c_uuid:
                    self.reverse_ui_map[uuid] = obj_name

        return self.reverse_ui_map[uuid]

    def popup(self, message):
        dpg.set_value(self.ui['popup_text'], message)
        dpg.show_item(self.ui['popup_window'])

    def change_button_state(self, /, enabled: bool):
        dpg.configure_item(self.ui['open_button'], enabled=enabled)
        dpg.configure_item(self.ui['vox_button'], enabled=enabled)
        dpg.configure_item(self.ui['xml_button'], enabled=enabled)
        dpg.configure_item(self.ui['2dx_button'], enabled=enabled)
        dpg.configure_item(self.ui['jackets_button'], enabled=enabled)

    def update_and_validate(self, sender: ObjectID, app_data: Any):
        if sender == self.ui['min_bpm']:
            if app_data > (value := dpg.get_value(self.ui['max_bpm'])):
                dpg.set_value(sender, value)
        elif sender == self.ui['max_bpm']:
            if app_data < (value := dpg.get_value(self.ui['min_bpm'])):
                dpg.set_value(sender, value)

        obj_name = self.get_obj_name(sender)
        if obj_name in SONG_INFO_FIELDS:
            setattr(self.parser._song_info, obj_name, self.parser._song_info.__annotations__[obj_name](app_data))
        elif obj_name in CHART_INFO_FIELDS:
            setattr(self.parser._chart_info, obj_name, self.parser._chart_info.__annotations__[obj_name](app_data))

    def load_file(self):
        self.change_button_state(enabled=False)

        file_path = filedialog.askopenfilename(
            filetypes=(
                ('K-Shoot Mania charts', '*.ksh'),
                ('All files', '*.*'),
            ),
            initialdir=self.current_path
        )
        if not file_path:
            self.change_button_state(enabled=True)
            return

        dpg.set_value(self.ui['loaded_file'], file_path)
        self.log(f'Reading "{file_path}"')

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            self.parser = KSHParser(f)

        self.current_path = self.parser._ksh_path.parent
        self.log(f'Chart loaded: {self.parser._song_info.title} / {self.parser._song_info.artist} '
                 f'({SLOT_MAPPING[self.parser._chart_info.difficulty]} {self.parser._chart_info.level})')

        for field in SONG_INFO_FIELDS:
            dpg.set_value(self.ui[field], getattr(self.parser._song_info, field))
        for field in CHART_INFO_FIELDS:
            dpg.set_value(self.ui[field], getattr(self.parser._chart_info, field))

        self.change_button_state(enabled=True)

    def save_file(self, sender: ObjectID, app_data: Any):
        path = app_data['file_path_name']

        print(path)

    def export_vox(self):
        self.save_type = 'vox'
        dpg.show_item(self.ui['directory_dialog'])

    def export_xml(self):
        self.save_type = 'xml'
        dpg.show_item(self.ui['directory_dialog'])

    def export_2dx(self):
        self.save_type = '2dx'
        dpg.show_item(self.ui['directory_dialog'])

    def export_jacket(self):
        self.save_type = 'png'
        dpg.show_item(self.ui['directory_dialog'])


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'demo':
        dpg_demo()
    else:
        KSH2VOXApp()
