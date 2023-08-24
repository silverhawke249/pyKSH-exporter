#!/usr/bin/env python
import logging
import re
import time

import dearpygui.dearpygui as dpg

from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable

from ksh2vox.classes.enums import DifficultySlot, GameBackground, InfVer
from ksh2vox.media.audio import get_2dxs
from ksh2vox.media.images import BG_WIDTH, BG_HEIGHT, GMBGHandler, get_game_backgrounds, get_jacket_images
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
YOMIGANA_VALIDATION_REGEX = re.compile('^[\uFF66-\uFF9F]+')
ENUM_REGEX = re.compile(r'\((\d+)\)')
GREY_TEXT_COLOR = 120, 120, 120, 255


class FunctionHandler(logging.Handler):
    _handler: Callable[[str], Any]

    def __init__(self, callable: Callable[[str], Any], level: int | str = 0) -> None:
        super().__init__(level)
        self._handler = callable

    def emit(self, record: logging.LogRecord) -> None:
        self._handler(self.format(record))


class KSH2VOXApp():
    ui            : dict[str, ObjectID] = dict()
    reverse_ui_map: dict[ObjectID, str] = dict()

    parser   : KSHParser
    gmbg_data: GMBGHandler

    current_path      : Path | None = None
    background_id     : int = 0
    gmbg_available    : bool = True
    gmbg_visible      : bool = False
    gmbg_visible_time : float = 0
    gmbg_images       : list[list[float]] = list()
    gmbg_image_index  : int = 0
    popup_result      : bool = False

    logger            : logging.Logger

    def __init__(self):
        self.gmbg_data = get_game_backgrounds()

        logging.basicConfig(format='[%(levelname)s %(asctime)s] %(name)s: %(message)s', level=logging.DEBUG)

        self.logger = logging.getLogger('main')

        warning_handler = FunctionHandler(self.log)
        warning_handler.setLevel(logging.WARNING)
        warning_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logging.getLogger('').addHandler(warning_handler)

        dpg.create_context()
        dpg.create_viewport(title='KSH Exporter', width=650, height=850, resizable=False)
        dpg.set_viewport_small_icon('resources/icon.ico')
        dpg.set_viewport_large_icon('resources/icon.ico')
        dpg.setup_dearpygui()

        #==================#
        # TEXTURE REGISTRY #
        #==================#

        with dpg.texture_registry():
            self.ui['gmbg_texture'] = dpg.add_dynamic_texture(
                width=BG_WIDTH, height=BG_HEIGHT, default_value=[0.0, 0.0, 0.0, 1.0] * (BG_WIDTH * BG_HEIGHT))

        #===================#
        # WINDOW/APP LAYOUT #
        #===================#

        with dpg.window(label='KSH Exporter') as self.ui['primary_window']:
            self.ui['throbber'] = dpg.add_loading_indicator(show=False, pos=(550, 20), style=1, radius=4, color=(15, 86, 135))

            with dpg.group() as main_buttons:
                with dpg.group(horizontal=True):
                    self.ui['open_button'] = dpg.add_button(label='Open file...', callback=self.load_ksh)
                    self.ui['loaded_file'] = dpg.add_text('[no file loaded]')

                dpg.add_spacer(height=1)

                with dpg.group(horizontal=True) as self.ui['save_group']:
                    self.ui['vox_button'] = dpg.add_button(label='Save VOX...', callback=self.export_vox, enabled=False)
                    self.ui['xml_button'] = dpg.add_button(label='Save XML...', callback=self.export_xml, enabled=False)
                    self.ui['2dx_button'] = dpg.add_button(label='Export 2DX...', callback=self.export_2dx, enabled=False)
                    self.ui['jackets_button'] = dpg.add_button(label='Export jackets...', callback=self.export_jacket, enabled=False)

            dpg.add_spacer(height=1)

            with dpg.child_window(height=510, width=-1, border=False) as self.ui['info_container']:
                with dpg.tab_bar():
                    with dpg.tab(label='Song info') as self.ui['section_song_info']:
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
                            label='Music volume', default_value=100, clamped=True, min_value=0, max_value=100,
                            callback=self.update_and_validate)
                        self.ui['background']      = dpg.add_combo(
                            list(GameBackground), label='Game background', default_value=GameBackground.BOOTH_BRIDGE,
                            callback=self.update_and_validate)
                        self.ui['inf_ver']         = dpg.add_combo(
                            list(InfVer), label='Infinite version', default_value=InfVer.INFINITE,
                            callback=self.update_and_validate)

                        with dpg.tooltip(self.ui['background']) as self.ui['bg_tooltip']:
                            self.ui['bg_preview'] = dpg.add_image(self.ui['gmbg_texture'])

                    with dpg.tab(label='Chart info') as self.ui['section_chart_info']:
                        self.ui['level'] = dpg.add_slider_int(
                            label='Level', clamped=True, min_value=1, max_value=20, callback=self.update_and_validate)
                        self.ui['difficulty'] = dpg.add_combo(
                            list(DifficultySlot), label='Difficulty', callback=self.update_and_validate)
                        self.ui['effector'] = dpg.add_input_text(
                            label='Effector', callback=self.update_and_validate)
                        self.ui['illustrator'] = dpg.add_input_text(
                            label='Illustrator', callback=self.update_and_validate)

                    with dpg.tab(label='Effects') as self.ui['section_effect_info']:
                        with dpg.group():
                            self.ui['effect_def_combo'] = dpg.add_combo(
                                label='Effect definition list', callback=self.load_effects)

                            with dpg.group(horizontal=True) as effect_def_buttons:
                                self.ui['effect_def_new'] = dpg.add_button(
                                    label='New', enabled=False, callback=self.add_new_effect)
                                self.ui['effect_def_update'] = dpg.add_button(
                                    label='Update', enabled=False, callback=self.update_effect)
                                self.ui['effect_def_delete'] = dpg.add_button(
                                    label='Delete', enabled=False, callback=self.delete_effect)

                        dpg.add_spacer(height=1)

                        with dpg.collapsing_header(label='Effect 1', default_open=True):
                            self.ui['effect_def_1_combo'] = dpg.add_combo(
                                label='1st effect type', callback=self.load_effect_params)
                            dpg.add_text('Parameters:')

                            with dpg.group() as self.ui['effect_def_1_params']:
                                dpg.add_text('No configurable parameters!', color=GREY_TEXT_COLOR)

                        dpg.add_spacer(height=1)

                        with dpg.collapsing_header(label='Effect 2', default_open=True):
                            self.ui['effect_def_2_combo'] = dpg.add_combo(
                                label='2nd effect type', callback=self.load_effect_params)
                            dpg.add_text('Parameters:')

                            with dpg.group() as self.ui['effect_def_2_params']:
                                dpg.add_text('No configurable parameters!', color=GREY_TEXT_COLOR)

                    with dpg.tab(label='Filter mapping') as self.ui['section_filter_info']:
                        dpg.add_text('Coming soon!')

                        # self.ui['filter_mapping'] = dpg.add_table(header_row=False, borders_innerH=True, borders_innerV=True)

                    with dpg.tab(label='Track autotab') as self.ui['section_autotab_info']:
                        dpg.add_text('Coming soon!')

                        # self.ui['autotab_info'] = dpg.add_table(header_row=False, borders_innerH=True, borders_innerV=True)

            with dpg.child_window(label='Logs', width=-1, height=-1, horizontal_scrollbar=True) as self.ui['log']:
                self.ui['log_last_line'] = 0

        #================#
        # EVENT HANDLERS #
        #================#

        with dpg.item_handler_registry() as background_handler:
            dpg.add_item_visible_handler(callback=self.change_image_texture)

        dpg.bind_item_handler_registry(self.ui['background'], background_handler)

        #===============#
        # FONT REGISTRY #
        #===============#

        with dpg.font_registry():
            with dpg.font('resources/NotoSansJP-Regular.ttf', 20) as font:
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)

            dpg.bind_font(font)

        #================#
        # THEME REGISTRY #
        #================#

        with dpg.theme() as button_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 20, 8, category=dpg.mvThemeCat_Core)

        dpg.bind_item_theme(main_buttons, button_theme)

        with dpg.theme() as sub_button_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 4, category=dpg.mvThemeCat_Core)

        dpg.bind_item_theme(effect_def_buttons, sub_button_theme)

        with dpg.theme() as log_theme:
            with dpg.theme_component(dpg.mvText):
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 4, 0, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 0, category=dpg.mvThemeCat_Core)

        dpg.bind_item_theme(self.ui['log'], log_theme)

        with dpg.theme() as primary_window_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0, category=dpg.mvThemeCat_Core)

            with dpg.theme_component(dpg.mvTab):
                dpg.add_theme_color(dpg.mvThemeCol_TabActive, (0, 119, 200, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (53, 174, 255, 255), category=dpg.mvThemeCat_Core)

            with dpg.theme_component(dpg.mvButton, enabled_state=True):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 119, 200, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (53, 174, 255, 255), category=dpg.mvThemeCat_Core)

            with dpg.theme_component(dpg.mvButton, enabled_state=False):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (100, 100, 100, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Button, (65, 65, 65, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (65, 65, 65, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (65, 65, 65, 255), category=dpg.mvThemeCat_Core)

            with dpg.theme_component(dpg.mvCollapsingHeader):
                dpg.add_theme_color(dpg.mvThemeCol_Header, (0, 119, 200, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (53, 174, 255, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (0, 119, 200, 255), category=dpg.mvThemeCat_Core)

        dpg.bind_item_theme(self.ui['primary_window'], primary_window_theme)

        #================================

        dpg.set_primary_window(self.ui['primary_window'], True)

        dpg.show_viewport()
        dpg.start_dearpygui()

        dpg.destroy_context()

    def get_obj_name(self, uuid: ObjectID):
        if uuid not in self.reverse_ui_map:
            for obj_name, c_uuid in self.ui.items():
                if uuid == c_uuid:
                    self.reverse_ui_map[uuid] = obj_name
                    break

        return self.reverse_ui_map[uuid]

    def log(self, message):
        self.ui['log_last_line'] = dpg.add_text(
            f'[{time.strftime("%H:%M:%S", time.localtime())}] {message}',
            parent=self.ui['log'], before=self.ui['log_last_line'])

    def change_image_texture(self):
        if self.gmbg_available and not dpg.get_item_configuration(self.ui['bg_tooltip'])['show']:
            dpg.show_item(self.ui['bg_tooltip'])
        elif not self.gmbg_available and dpg.get_item_configuration(self.ui['bg_tooltip'])['show']:
            dpg.hide_item(self.ui['bg_tooltip'])

        if dpg.is_item_hovered(self.ui['background']) and dpg.is_item_visible(self.ui['bg_preview']):
            if not self.gmbg_visible:
                self.gmbg_image_index = 0
                self.gmbg_images = self.gmbg_data.get_images(self.background_id)
                self.gmbg_visible = True
                self.gmbg_visible_time = time.time()
                dpg.set_value(self.ui['gmbg_texture'], self.gmbg_images[self.gmbg_image_index])
                return

            now_index = int((time.time() - self.gmbg_visible_time) / 1.5) % len(self.gmbg_images)
            if now_index == self.gmbg_image_index:
                return

            self.gmbg_image_index = now_index
            dpg.set_value(self.ui['gmbg_texture'], self.gmbg_images[self.gmbg_image_index])
        else:
            self.gmbg_visible = False

    def update_and_validate(self, sender: ObjectID, app_data: Any):
        # Validation
        if sender == self.ui['min_bpm']:
            if app_data > (value := dpg.get_value(self.ui['max_bpm'])):
                dpg.set_value(sender, value)
        elif sender == self.ui['max_bpm']:
            if app_data < (value := dpg.get_value(self.ui['min_bpm'])):
                dpg.set_value(sender, value)

        # Convert value back to enum
        if sender in [self.ui['background'], self.ui['inf_ver'], self.ui['difficulty']]:
            regex_match = ENUM_REGEX.search(app_data)
            if regex_match is not None:
                app_data = int(regex_match.group(1))

        # Update background preview
        if sender == self.ui['background']:
            self.background_id = app_data
            self.gmbg_available = self.gmbg_data.has_image(self.background_id)

        # Update parser state
        try:
            obj_name = self.get_obj_name(sender)
            if obj_name in SONG_INFO_FIELDS:
                setattr(self.parser.song_info, obj_name, self.parser.song_info.__annotations__[obj_name](app_data))
            elif obj_name in CHART_INFO_FIELDS:
                setattr(self.parser.chart_info, obj_name, self.parser.chart_info.__annotations__[obj_name](app_data))
        except AttributeError:
            pass

    def populate_effects_list(self, list_index: int = 0):
        ...

    def load_effects(self, sender: ObjectID):
        ...

    def load_effect_params(self, sender: ObjectID):
        ...

    def update_effect_def_button_state(self):
        button_state = bool(self.parser.chart_info.effect_list)
        dpg.configure_item(self.ui['effect_def_update'], enabled=button_state)
        dpg.configure_item(self.ui['effect_def_delete'], enabled=button_state)

    def add_new_effect(self):
        ...

    def update_effect(self):
        ...

    def delete_effect(self):
        ...

    def load_ksh(self):
        with disable_buttons(self), show_throbber(self):
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

            self.current_path = self.parser.ksh_path.parent
            self.log(f'Chart loaded: {self.parser.song_info.title} / {self.parser.song_info.artist} '
                    f'({SLOT_MAPPING[self.parser.chart_info.difficulty]} {self.parser.chart_info.level})')

            for field in SONG_INFO_FIELDS:
                dpg.set_value(self.ui[field], getattr(self.parser.song_info, field))
            for field in CHART_INFO_FIELDS:
                dpg.set_value(self.ui[field], getattr(self.parser.chart_info, field))

            self.background_id = self.parser.song_info.background.value
            self.gmbg_available = self.gmbg_data.has_image(self.background_id)

        # Main buttons
        dpg.configure_item(self.ui['vox_button'], enabled=True)
        dpg.configure_item(self.ui['xml_button'], enabled=True)
        dpg.configure_item(self.ui['2dx_button'], enabled=True)
        dpg.configure_item(self.ui['jackets_button'], enabled=True)

        # Effect definition buttons
        dpg.configure_item(self.ui['effect_def_new'], enabled=True)
        self.update_effect_def_button_state()

    def validate_metadata(self):
        title_check = YOMIGANA_VALIDATION_REGEX.match(self.parser.song_info.title_yomigana)
        if title_check is None:
            self.logger.warning('Title yomigana is not a valid yomigana string or is empty')

        artist_check = YOMIGANA_VALIDATION_REGEX.match(self.parser.song_info.artist_yomigana)
        if artist_check is None:
            self.logger.warning('Artist yomigana is not a valid yomigana string or is empty')

        if not (self.parser.song_info.ascii_label and self.parser.song_info.ascii_label.isascii()):
            self.logger.warning('ASCII label is not an ASCII string or is empty')

        try:
            time.strptime(self.parser.song_info.release_date, '%Y%m%d')
        except ValueError:
            self.logger.warning('Release date is not a valid YYYYMMDD date string')

    def export_vox(self):
        with disable_buttons(self), show_throbber(self):
            file_name = (f'{self.parser.song_info.id:04}_{self.parser.song_info.ascii_label}_'
                         f'{self.parser.chart_info.difficulty.to_shorthand()}.vox')
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
            file_name = Path(file_path).name

            self.log(f'Writing to "{file_path}"...')
            self.current_path = Path(file_path).parent
            with open(file_path, 'w') as f:
                self.parser.write_vox(f)

            self.log(f'File saved: {file_name}')

    def export_xml(self):
        with disable_buttons(self), show_throbber(self):
            self.validate_metadata()

            file_name = (f'{self.parser.song_info.id:04}_{self.parser.song_info.ascii_label}_'
                         f'{self.parser.chart_info.difficulty.to_shorthand()}.xml')
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
            file_name = Path(file_path).name

            self.log(f'Writing to "{file_path}"...')
            self.current_path = Path(file_path).parent
            with open(file_path, 'w') as f:
                self.parser.write_xml(f)

            self.log(f'File saved: {file_name}')

    def export_2dx(self):
        with disable_buttons(self), show_throbber(self):
            audio_path = (self.parser.ksh_path.parent / self.parser.chart_info.music_path).resolve()
            if not audio_path.exists():
                self.log(f'Cannot open "{audio_path}".')
                self.show_popup(f'Cannot open "{audio_path}".')
                return

            song_label = f'{self.parser.song_info.id:04}_{self.parser.song_info.ascii_label}'
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
                title='Save song\'s 2DX file',
            )
            if not song_file_path:
                return None
            song_file_name = Path(song_file_path).name

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
                title='Save preview\'s 2DX file',
            )
            if not preview_file_path:
                return None
            preview_file_name = Path(preview_file_path).name

            self.log('Converting audio to 2DX format...')
            song_bytes, preview_bytes = get_2dxs(
                audio_path, song_label, self.parser.chart_info.preview_start, self.parser.chart_info.music_offset)

            self.log(f'Writing to "{song_file_path}"...')
            with open(song_file_path, 'wb') as f:
                f.write(song_bytes)
            self.log(f'File saved: {song_file_name}')

            self.log(f'Writing to "{preview_file_path}"...')
            with open(preview_file_path, 'wb') as f:
                f.write(preview_bytes)
            self.log(f'File saved: {preview_file_name}')

    def export_jacket(self):
        with disable_buttons(self), show_throbber(self):
            jacket_path = (self.parser.ksh_path.parent / self.parser.chart_info.jacket_path).resolve()
            if not jacket_path.exists():
                self.log(f'Cannot open "{jacket_path}".')
                self.show_popup(f'Cannot open "{jacket_path}".')
                return

            jacket_r_file_name = f'jk_{self.parser.song_info.id:04}_{self.parser.chart_info.difficulty.value}.png'
            jacket_b_file_name = f'jk_{self.parser.song_info.id:04}_{self.parser.chart_info.difficulty.value}_b.png'
            jacket_s_file_name = f'jk_{self.parser.song_info.id:04}_{self.parser.chart_info.difficulty.value}_s.png'

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
            jacket_r_file_name = Path(jacket_r_file_path).name

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
            jacket_b_file_name = Path(jacket_b_file_path).name

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
            jacket_s_file_name = Path(jacket_s_file_path).name

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

    def __init__(self, app: KSH2VOXApp):
        self.app = app
        self.buttons = [
            # Main buttons
            'open_button', 'vox_button', 'xml_button', '2dx_button', 'jackets_button',
            # Effect definition buttons
            'effect_def_new', 'effect_def_update', 'effect_def_delete',
        ]
        self.button_state = {}

    def __enter__(self):
        for button in self.buttons:
            self.button_state[button] = dpg.get_item_configuration(self.app.ui[button])['enabled']
            dpg.configure_item(self.app.ui[button], enabled=False)

    def __exit__(self, *args, **kwargs):
        for button, state in self.button_state.items():
            dpg.configure_item(self.app.ui[button], enabled=state)


class show_throbber():
    app: KSH2VOXApp

    def __init__(self, app: KSH2VOXApp):
        self.app = app

    def __enter__(self):
        dpg.show_item(self.app.ui['throbber'])

    def __exit__(self, *args, **kwargs):
        dpg.hide_item(self.app.ui['throbber'])


if __name__ == '__main__':
    KSH2VOXApp()
