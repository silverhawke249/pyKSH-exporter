import re
import sys
import time
import warnings

import dearpygui.dearpygui as dpg
import dearpygui.demo as demo

from pathlib import Path
from tkinter import filedialog
from typing import Any

from ksh2vox.classes.enums import DifficultySlot, GameBackground, InfVer
from ksh2vox.media.audio import get_2dxs
from ksh2vox.media.images import get_jacket_images
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
ENUM_REGEX = re.compile(r'\((\d+)\)')


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

    current_path: Path | None = None
    popup_result: bool = False

    def __init__(self):
        self.ui = {}
        self.reverse_ui_map = {}

        warnings.simplefilter('always')
        warnings.showwarning = self.log_warning

        dpg.create_context()
        dpg.create_viewport(title='ksh-vox converter', width=650, height=850, resizable=False)
        dpg.setup_dearpygui()

        with dpg.window(label='ksh-vox converter') as primary_window:
            self.ui['primary_window'] = primary_window

            with dpg.group() as main_buttons:
                with dpg.group(horizontal=True):
                    self.ui['open_button'] = dpg.add_button(label='Open file...', callback=self.load_ksh)
                    self.ui['loaded_file'] = dpg.add_text('[no file loaded]')

                dpg.add_spacer(height=1)

                with dpg.group(horizontal=True) as save_group:
                    self.ui['save_group'] = save_group

                    self.ui['vox_button'] = dpg.add_button(label='Save VOX...', callback=self.export_vox, enabled=False)
                    self.ui['xml_button'] = dpg.add_button(label='Save XML...', callback=self.export_xml, enabled=False)
                    self.ui['2dx_button'] = dpg.add_button(label='Export 2DX...', callback=self.export_2dx, enabled=False)
                    self.ui['jackets_button'] = dpg.add_button(label='Export jackets...', callback=self.export_jacket, enabled=False)

            dpg.add_spacer(height=1)

            with dpg.child_window(height=510, width=-1, border=False) as info_container:
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

            with dpg.child_window(label='Logs', width=-1, height=-1, horizontal_scrollbar=True) as log_window:
                self.ui['log'] = log_window

        with dpg.window(
            label='Error', show=False, autosize=True, no_move=True, no_close=True, modal=True
        ) as popup_window:
            self.ui['popup_window'] = popup_window
            self.ui['popup_text'] = dpg.add_text()

            with dpg.table(header_row=False):
                dpg.add_table_column(width_stretch=True)
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)

                with dpg.table_row():
                    dpg.add_spacer()

                    with dpg.group(horizontal=True):
                        dpg.add_button(label='OK', user_data=True, callback=self.hide_popup)

                    dpg.add_spacer()

        with dpg.item_handler_registry() as popup_handler:
            dpg.add_item_resize_handler(callback=self.reposition_popup)

        dpg.bind_item_handler_registry(popup_window, popup_handler)

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

        with dpg.theme() as primary_window_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0, category=dpg.mvThemeCat_Core)

            with dpg.theme_component(dpg.mvButton, enabled_state=True):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (23, 60, 95), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Header, (23, 60, 95), category=dpg.mvThemeCat_Core)

            with dpg.theme_component(dpg.mvButton, enabled_state=False):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (100, 100, 100), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (100, 100, 100), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (100, 100, 100), category=dpg.mvThemeCat_Core)

        with dpg.theme() as sub_window_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 5, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Border, (15, 86, 135), category=dpg.mvThemeCat_Core)

            with dpg.theme_component(dpg.mvButton, enabled_state=True):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (23, 60, 95), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Header, (23, 60, 95), category=dpg.mvThemeCat_Core)

            with dpg.theme_component(dpg.mvButton, enabled_state=False):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (100, 100, 100), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (100, 100, 100), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (100, 100, 100), category=dpg.mvThemeCat_Core)

        dpg.bind_item_theme(primary_window, primary_window_theme)
        dpg.bind_item_theme(popup_window, sub_window_theme)
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

    def show_popup(self, message):
        dpg.set_value(self.ui['popup_text'], message)
        dpg.show_item(self.ui['popup_window'])

    def reposition_popup(self):
        ww, wh = dpg.get_item_rect_size(self.ui['popup_window'])
        vw, vh = dpg.get_viewport_width(), dpg.get_viewport_height()
        dpg.set_item_pos(self.ui['popup_window'], [(vw - ww) // 2, (vh - wh) // 2])

    def hide_popup(self, sender: ObjectID, app_data, user_data: bool):
        self.popup_result = user_data
        dpg.hide_item(self.ui['popup_window'])

    def update_and_validate(self, sender: ObjectID, app_data: Any):
        if sender == self.ui['min_bpm']:
            if app_data > (value := dpg.get_value(self.ui['max_bpm'])):
                dpg.set_value(sender, value)
        elif sender == self.ui['max_bpm']:
            if app_data < (value := dpg.get_value(self.ui['min_bpm'])):
                dpg.set_value(sender, value)

        if sender in [self.ui['background'], self.ui['inf_ver'], self.ui['difficulty']]:
            regex_match = ENUM_REGEX.search(app_data)
            if regex_match is not None:
                app_data = int(regex_match.group(1))

        obj_name = self.get_obj_name(sender)
        if obj_name in SONG_INFO_FIELDS:
            setattr(self.parser._song_info, obj_name, self.parser._song_info.__annotations__[obj_name](app_data))
        elif obj_name in CHART_INFO_FIELDS:
            setattr(self.parser._chart_info, obj_name, self.parser._chart_info.__annotations__[obj_name](app_data))

    def load_ksh(self):
        with disable_buttons(self):
            file_path = filedialog.askopenfilename(
                filetypes=(
                    ('K-Shoot Mania charts', '*.ksh'),
                    ('All files', '*'),
                ),
                initialdir=self.current_path,
                title='Open KSH file',
            )
            if not file_path:
                return

            dpg.set_value(self.ui['loaded_file'], file_path)
            self.log(f'Reading from "{file_path}"...')

            with open(file_path, 'r', encoding='utf-8-sig') as f:
                self.parser = KSHParser(f)

            self.current_path = self.parser._ksh_path.parent
            self.log(f'Chart loaded: {self.parser._song_info.title} / {self.parser._song_info.artist} '
                    f'({SLOT_MAPPING[self.parser._chart_info.difficulty]} {self.parser._chart_info.level})')

            for field in SONG_INFO_FIELDS:
                dpg.set_value(self.ui[field], getattr(self.parser._song_info, field))
            for field in CHART_INFO_FIELDS:
                dpg.set_value(self.ui[field], getattr(self.parser._chart_info, field))

        dpg.configure_item(self.ui['vox_button'], enabled=True)
        dpg.configure_item(self.ui['xml_button'], enabled=True)
        dpg.configure_item(self.ui['2dx_button'], enabled=True)
        dpg.configure_item(self.ui['jackets_button'], enabled=True)

    def export_vox(self):
        with disable_buttons(self):
            file_name = (f'{self.parser._song_info.id}_{self.parser._song_info.ascii_label}_'
                         f'{self.parser._chart_info.difficulty.to_shorthand()}.vox')
            file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension='vox',
                filetypes=(
                    ('VOX files', '*.vox'),
                    ('All files', '*'),
                ),
                initialdir=self.current_path,
                initialfile=file_name,
                title='Export VOX file',
            )
            if not file_path:
                return None

            self.log(f'Writing to "{file_path}"...')
            self.current_path = Path(file_path).parent
            with open(file_path, 'w') as f:
                self.parser.write_vox(f)

            self.log(f'File saved: {file_name}')

    def export_xml(self):
        with disable_buttons(self):
            file_name = (f'{self.parser._song_info.id}_{self.parser._song_info.ascii_label}_'
                         f'{self.parser._chart_info.difficulty.to_shorthand()}.xml')
            file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension='xml',
                filetypes=(
                    ('XML files', '*.xml'),
                    ('All files', '*'),
                ),
                initialdir=self.current_path,
                initialfile=file_name,
                title='Export XML file',
            )
            if not file_path:
                return None

            self.log(f'Writing to "{file_path}"...')
            self.current_path = Path(file_path).parent
            with open(file_path, 'w') as f:
                self.parser.write_xml(f)

            self.log(f'File saved: {file_name}')

    def export_2dx(self):
        with disable_buttons(self):
            audio_path = (self.parser._ksh_path.parent / self.parser._chart_info.music_path).resolve()
            if not audio_path.exists():
                self.log(f'Cannot open "{audio_path}".')
                self.show_popup(f'Cannot open "{audio_path}".')
                return

            song_label = f'{self.parser._song_info.id}_{self.parser._song_info.ascii_label}'
            song_file_name = f'{song_label}.2dx'
            song_file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension='2dx',
                filetypes=(
                    ('2DX files', '*.2dx'),
                    ('All files', '*'),
                ),
                initialdir=self.current_path,
                initialfile=song_file_name,
                title='Save song 2DX file',
            )
            if not song_file_path:
                return None

            preview_file_name = f'{song_label}_pre.2dx'
            preview_file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension='2dx',
                filetypes=(
                    ('2DX files', '*.2dx'),
                    ('All files', '*'),
                ),
                initialdir=self.current_path,
                initialfile=preview_file_name,
                title='Save preview 2DX file',
            )
            if not preview_file_path:
                return None

            self.log('Converting audio to 2DX format...')
            song_bytes, preview_bytes = get_2dxs(audio_path, song_label, self.parser._chart_info.preview_start)

            self.log(f'Writing to "{song_file_path}"...')
            with open(song_file_path, 'wb') as f:
                f.write(song_bytes)
            self.log(f'File saved: {song_file_name}')

            self.log(f'Writing to "{preview_file_path}"...')
            with open(preview_file_path, 'wb') as f:
                f.write(preview_bytes)
            self.log(f'File saved: {preview_file_name}')

    def export_jacket(self):
        with disable_buttons(self):
            jacket_path = (self.parser._ksh_path.parent / self.parser._chart_info.jacket_path).resolve()
            if not jacket_path.exists():
                self.log(f'Cannot open "{jacket_path}".')
                self.show_popup(f'Cannot open "{jacket_path}".')
                return

            jacket_r_file_name = f'jk_{self.parser._song_info.id}_1.png'
            jacket_b_file_name = f'jk_{self.parser._song_info.id}_1_b.png'
            jacket_s_file_name = f'jk_{self.parser._song_info.id}_1_s.png'

            jacket_r_file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension='png',
                filetypes=(
                    ('PNG images', '*.png'),
                    ('All files', '*'),
                ),
                initialdir=self.current_path,
                initialfile=jacket_r_file_name,
                title='Save regular jacket image',
            )
            if not jacket_r_file_path:
                return None

            jacket_b_file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension='png',
                filetypes=(
                    ('PNG images', '*.png'),
                    ('All files', '*'),
                ),
                initialdir=self.current_path,
                initialfile=jacket_b_file_name,
                title='Save large jacket image',
            )
            if not jacket_b_file_path:
                return None

            jacket_s_file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension='png',
                filetypes=(
                    ('PNG images', '*.png'),
                    ('All files', '*'),
                ),
                initialdir=self.current_path,
                initialfile=jacket_s_file_name,
                title='Save small jacket image',
            )
            if not jacket_s_file_path:
                return None

            self.log('Resizing jacket image...')
            jk_r_bytes, jk_b_bytes, jk_s_bytes = get_jacket_images(jacket_path)

            self.log(f'Writing to "{jacket_r_file_path}"...')
            with open(jacket_r_file_path, 'wb') as f:
                f.write(jk_r_bytes)
            self.log(f'File saved: {jacket_r_file_name}')

            self.log(f'Writing to "{jacket_b_file_path}"...')
            with open(jacket_b_file_path, 'wb') as f:
                f.write(jk_b_bytes)
            self.log(f'File saved: {jacket_b_file_name}')

            self.log(f'Writing to "{jacket_s_file_path}"...')
            with open(jacket_s_file_path, 'wb') as f:
                f.write(jk_s_bytes)
            self.log(f'File saved: {jacket_s_file_name}')


class disable_buttons():
    app: KSH2VOXApp
    buttons: list[str]
    button_state: dict[str, bool]

    def __init__(self, app):
        self.app = app
        self.buttons = ['open_button', 'vox_button', 'xml_button', '2dx_button', 'jackets_button']
        self.button_state = {}

    def __enter__(self):
        for button in self.buttons:
            self.button_state[button] = dpg.get_item_configuration(self.app.ui[button])['enabled']
            dpg.configure_item(self.app.ui[button], enabled=False)

    def __exit__(self, *args, **kwargs):
        for button, state in self.button_state.items():
            dpg.configure_item(self.app.ui[button], enabled=state)


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'demo':
        dpg_demo()
    else:
        KSH2VOXApp()
