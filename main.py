import sys

import dearpygui.dearpygui as dpg
import dearpygui.demo as demo

from enum import Enum
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


class AlignmentType(Enum):
    HORIZONTAL = 0
    VERTICAL = 1
    BOTH = 2


def dpg_demo():
    dpg.create_context()
    dpg.create_viewport()
    dpg.setup_dearpygui()

    demo.show_demo()

    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()


# Taken from my1e5/dpg-examples repo
def auto_align(item, alignment_type: AlignmentType, x_align: float = 0.5, y_align: float = 0.5):
    def _center_h(_s, _d, data):
        parent = dpg.get_item_parent(data[0])
        parent_width = dpg.get_item_width(parent)
        width = dpg.get_item_width(data[0])
        new_x = (parent_width // 2 - width // 2) * data[1] * 2
        dpg.set_item_pos(data[0], [new_x, dpg.get_item_pos(data[0])[1]])

    def _center_v(_s, _d, data):
        print(data)
        parent = dpg.get_item_parent(data[0])
        # while dpg.get_item_info(parent)['type'] != "mvAppItemType::mvWindowAppItem":
        #     parent = dpg.get_item_parent(parent)
        parent_height = dpg.get_item_height(parent)
        height = dpg.get_item_height(data[0])
        new_y = (parent_height // 2 - height // 2) * data[1] * 2
        dpg.set_item_pos(data[0], [dpg.get_item_pos(data[0])[0], new_y])

    with dpg.item_handler_registry() as handler:
        if alignment_type == AlignmentType.HORIZONTAL:
            # horizontal only alignment
            dpg.add_item_visible_handler(callback=_center_h, user_data=[item, x_align])
        elif alignment_type == AlignmentType.VERTICAL:
            # vertical only alignment
            dpg.add_item_visible_handler(callback=_center_v, user_data=[item, y_align])
        elif alignment_type == AlignmentType.BOTH:
            # both horizontal and vertical alignment
            dpg.add_item_visible_handler(callback=_center_h, user_data=[item, x_align])
            dpg.add_item_visible_handler(callback=_center_v, user_data=[item, y_align])

    dpg.bind_item_handler_registry(item, handler)


class KSH2VOXApp():
    ui: dict[str, ObjectID]
    reverse_ui_map: dict[ObjectID, str]
    parser: KSHParser

    def __init__(self):
        self.ui = {}
        self.reverse_ui_map = {}

        dpg.create_context()
        dpg.create_viewport(title='ksh-vox converter', width=600, height=800, resizable=False, decorated=False)
        dpg.setup_dearpygui()

        with dpg.window(label='ksh-vox converter') as primary_window:
            self.ui['primary_window'] = primary_window

            with dpg.menu_bar() as menu_bar:
                self.ui['menu_bar'] = menu_bar

                with dpg.menu(label='File'):
                    dpg.add_menu_item(label='Close', callback=dpg.stop_dearpygui)

            with dpg.group(horizontal=True):
                dpg.add_button(label='Open file...', width=150, height=40, callback=self.show_file_dialog)
                self.ui['loaded_file'] = dpg.add_text('[no file loaded]')
                auto_align(self.ui['loaded_file'], AlignmentType.VERTICAL)

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

                    self.ui['autotab_info'] = dpg.add_table(header_row=False, borders_innerH=True, borders_innerV=True)

                with dpg.collapsing_header(
                    label='Track auto tab settings', show=False, default_open=True) as section_autotab_info:
                    self.ui['section_autotab_info'] = section_autotab_info

                    self.ui['autotab_info'] = dpg.add_table(header_row=False, borders_innerH=True, borders_innerV=True)

        with dpg.theme() as theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (23, 60, 95), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Header, (23, 60, 95), category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5, category=dpg.mvThemeCat_Core)

        with dpg.font_registry():
            with dpg.font('resources/NotoSansJP-Regular.ttf', 20) as font:
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)

            dpg.bind_font(font)

        with dpg.handler_registry():
            dpg.add_mouse_drag_handler(button=0, threshold=0, callback=self.menu_bar_drag)

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

    def menu_bar_drag(self, sender: ObjectID, app_data: Any):
        if not dpg.is_mouse_button_down(0):
            return

        menu_bar_height = dpg.get_item_height(self.ui['menu_bar'])
        if dpg.get_mouse_pos()[1] > menu_bar_height:
            return

        pos_x, pos_y = dpg.get_viewport_pos()
        _, delta_x, delta_y = app_data
        dpg.set_viewport_pos([pos_x + delta_x, pos_y + delta_y])

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

        dpg.delete_item(self.ui['effect_table'], children_only=True)
        dpg.hide_item(self.ui['effect_table'])

        dpg.add_table_column(parent=self.ui['effect_table'], width_fixed=True)
        dpg.add_table_column(parent=self.ui['effect_table'], width_stretch=True, init_width_or_weight=0.0)

        for i, effect_name in enumerate(self.parser._fx_list):
            with dpg.table_row(parent=self.ui['effect_table']):
                with dpg.group(horizontal=True):
                    effect_name = dpg.add_text(effect_name)
                    auto_align(effect_name, AlignmentType.VERTICAL)

                with dpg.group():
                    dpg.add_text(self.parser._chart_info.effect_list[i].effect1)
                    dpg.add_text(self.parser._chart_info.effect_list[i].effect2)

        dpg.show_item(self.ui['save_group'])
        dpg.show_item(self.ui['section_song_info'])
        dpg.show_item(self.ui['section_chart_info'])
        dpg.show_item(self.ui['section_effect_info'])
        dpg.show_item(self.ui['effect_table'])

    def show_file_dialog(self):
        dpg.show_item(self.ui['file_dialog'])


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'demo':
        dpg_demo()
    else:
        KSH2VOXApp()
