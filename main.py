import sys

import dearpygui.dearpygui as dpg
import dearpygui.demo as demo

from typing import Any

from ksh2vox.classes.enums import DifficultySlot, GameBackground, InfVer
from ksh2vox.parser.ksh import KSHParser

ObjectID = int | str
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
    is_dragging_menu: bool = False

    def __init__(self):
        self.ui = {}
        self.reverse_ui_map = {}

        dpg.create_context()
        dpg.create_viewport(title='ksh-vox converter', width=600, height=800, resizable=False)
        dpg.setup_dearpygui()

        with dpg.window(label='ksh-vox converter') as primary_window:
            self.ui['primary_window'] = primary_window

            with dpg.group() as main_buttons:
                with dpg.group(horizontal=True):
                    dpg.add_button(label='Open file...', callback=self.show_file_dialog)
                    self.ui['loaded_file'] = dpg.add_text('[no file loaded]')

                dpg.add_spacer(height=1)

                with dpg.table(header_row=False, show=False) as save_group:
                    self.ui['save_group'] = save_group

                    dpg.add_table_column(width_stretch=True)
                    dpg.add_table_column(width_fixed=True)

                    with dpg.table_row():
                        dpg.add_spacer()

                        with dpg.group(horizontal=True):
                            dpg.add_button(label='Save VOX...')
                            dpg.add_button(label='Save XML...')
                            dpg.add_button(label='Export 2DX...')
                            dpg.add_button(label='Export jackets...')

            dpg.add_spacer(height=1)

            with dpg.file_dialog(
                width=500, height=400, show=False, callback=self.load_file, modal=True
            ) as open_dialog:
                self.ui['file_dialog'] = open_dialog

                dpg.add_file_extension('.ksh')

            with dpg.group() as info_group:
                self.ui['info_group'] = info_group

                with dpg.collapsing_header(label='Song info', show=False, default_open=True) as section_song_info:
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

                with dpg.collapsing_header(label='Chart info', show=False, default_open=True) as section_chart_info:
                    self.ui['section_chart_info'] = section_chart_info

                    self.ui['level'] = dpg.add_slider_int(
                        label='Level', clamped=True, min_value=1, max_value=20, callback=self.update_and_validate)
                    self.ui['difficulty'] = dpg.add_combo(
                        list(DifficultySlot), label='Difficulty', callback=self.update_and_validate)
                    self.ui['effector'] = dpg.add_input_text(
                        label='Effector', callback=self.update_and_validate)
                    self.ui['illustrator'] = dpg.add_input_text(
                        label='Illustrator', callback=self.update_and_validate)

                with dpg.collapsing_header(
                    label='Effect settings', show=False, default_open=True) as section_effect_info:
                    self.ui['section_effect_info'] = section_effect_info

                    self.ui['effect_table'] = dpg.add_table(header_row=False, borders_innerH=True, borders_innerV=True)

                with dpg.collapsing_header(
                    label='Filter effect mapping', show=False, default_open=True) as section_filter_info:
                    self.ui['section_filter_info'] = section_filter_info

                    self.ui['filter_mapping'] = dpg.add_table(header_row=False, borders_innerH=True, borders_innerV=True)

                with dpg.collapsing_header(
                    label='Track auto tab settings', show=False, default_open=True) as section_autotab_info:
                    self.ui['section_autotab_info'] = section_autotab_info

                    self.ui['autotab_info'] = dpg.add_table(header_row=False, borders_innerH=True, borders_innerV=True)

        with dpg.font_registry():
            with dpg.font('resources/NotoSansJP-Regular.ttf', 20) as font:
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)

            dpg.bind_font(font)

        with dpg.theme() as button_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 20, 10)

        dpg.bind_item_theme(main_buttons, button_theme)

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

    def get_obj_name(self, uuid: ObjectID):
        if uuid not in self.reverse_ui_map:
            for obj_name, c_uuid in self.ui.items():
                if uuid == c_uuid:
                    self.reverse_ui_map[uuid] = obj_name

        return self.reverse_ui_map[uuid]

    def menu_bar_click(self):
        menu_bar_height = dpg.get_item_height(self.ui['menu_bar'])
        print(menu_bar_height)
        self.is_dragging_menu = dpg.get_mouse_pos()[1] <= menu_bar_height

    def menu_bar_drag(self, sender: ObjectID, app_data: Any):
        if not self.is_dragging_menu:
            return

        pos_x, pos_y = dpg.get_viewport_pos()
        if pos_x == pos_y == 0:
            return
        _, delta_x, delta_y = app_data
        pos_x += int(delta_x)
        pos_y += int(delta_y)
        dpg.set_viewport_pos([pos_x, pos_y])

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

        print(self.parser._song_info)

    def load_file(self, sender: ObjectID, app_data: Any):
        file_path = app_data['file_path_name']
        dpg.set_value(self.ui['loaded_file'], file_path)

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            self.parser = KSHParser(f)

        for field in SONG_INFO_FIELDS:
            dpg.set_value(self.ui[field], getattr(self.parser._song_info, field))
        for field in CHART_INFO_FIELDS:
            dpg.set_value(self.ui[field], getattr(self.parser._chart_info, field))

        # Show effect list
        dpg.delete_item(self.ui['effect_table'], children_only=True)

        dpg.add_table_column(parent=self.ui['effect_table'], width_fixed=True)
        dpg.add_table_column(parent=self.ui['effect_table'], width_stretch=True, init_width_or_weight=0.0)
        dpg.add_table_column(parent=self.ui['effect_table'], width_fixed=True)

        # Change to actual effect list
        for i, effect_entry in enumerate(self.parser._chart_info.effect_list):
            with dpg.table_row(parent=self.ui['effect_table']):
                with dpg.table_cell():
                    dpg.add_text(i + 1)
                    dpg.add_button(label='\u00D7')

                with dpg.table_cell():
                    dpg.add_text(effect_entry.effect1)
                    dpg.add_text(effect_entry.effect2)

                with dpg.table_cell():
                    dpg.add_button(label='  Edit  ')
                    dpg.add_button(label='  Edit  ')

        # Show custom filter mapping
        dpg.delete_item(self.ui['filter_mapping'], children_only=True)

        dpg.add_table_column(parent=self.ui['filter_mapping'], width_fixed=True)
        dpg.add_table_column(parent=self.ui['filter_mapping'], width_stretch=True, init_width_or_weight=0.0)

        for filter_name, effect_index in self.parser._filter_to_effect.items():
            with dpg.table_row(parent=self.ui['filter_mapping']):
                dpg.add_text(filter_name)
                dpg.add_input_int(default_value=effect_index + 1, min_value=1, min_clamped=True)

        dpg.show_item(self.ui['save_group'])
        dpg.show_item(self.ui['section_song_info'])
        dpg.show_item(self.ui['section_chart_info'])
        dpg.show_item(self.ui['section_effect_info'])
        dpg.show_item(self.ui['section_filter_info'])

    def show_file_dialog(self):
        dpg.show_item(self.ui['file_dialog'])


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'demo':
        dpg_demo()
    else:
        KSH2VOXApp()
