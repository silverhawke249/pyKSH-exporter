import dearpygui.dearpygui as dpg
import dearpygui.demo as demo

from ksh2vox.classes.enums import DifficultySlot, GameBackground, InfVer
from ksh2vox.parser.ksh import KSHParser

UI_ELEMENTS: dict[str, str | int] = {}
PARSER_OBJ : KSHParser
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


def do_nothing() -> None:
    pass


def parse_file(sender: str | int, app_data) -> None:
    file_path = app_data['file_path_name']
    dpg.set_value(UI_ELEMENTS['loaded_file'], file_path)

    with open(file_path, 'r', encoding='utf-8-sig') as f:
        PARSER_OBJ = KSHParser(f)

    for field in SONG_INFO_FIELDS:
        dpg.set_value(UI_ELEMENTS[field], getattr(PARSER_OBJ._song_info, field))
    for field in CHART_INFO_FIELDS:
        dpg.set_value(UI_ELEMENTS[field], getattr(PARSER_OBJ._chart_info, field))

    dpg.show_item(UI_ELEMENTS['section_song_info'])
    dpg.show_item(UI_ELEMENTS['section_chart_info'])


def open_file_dialog(sender: str | int):
    dpg.show_item(UI_ELEMENTS['file_dialog'])


def main() -> None:
    dpg.create_context()
    dpg.create_viewport(title='ksh-vox converter', width=600, height=800, resizable=False)
    dpg.setup_dearpygui()

    with dpg.font_registry():
        with dpg.font('NotoSansJP-Regular.ttf', 20) as font:
            dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
            dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)

        dpg.bind_font(font)

    with dpg.window() as primary_window:
        UI_ELEMENTS['primary_window'] = primary_window

        with dpg.group(horizontal=True):
            dpg.add_button(label='Open file...', callback=open_file_dialog)
            UI_ELEMENTS['loaded_file'] = dpg.add_text('[no file loaded]')

        with dpg.file_dialog(
            width=500, height=400, show=False, callback=parse_file, cancel_callback=do_nothing
        ) as open_dialog:
            UI_ELEMENTS['file_dialog'] = open_dialog

            dpg.add_file_extension('.ksh')

        with dpg.group() as info_group:
            UI_ELEMENTS['info_group'] = info_group

            with dpg.collapsing_header(label='Song info', show=False, default_open=True) as section_song_info:
                UI_ELEMENTS['section_song_info'] = section_song_info

                UI_ELEMENTS['id']              = dpg.add_input_int(label='Song ID', min_clamped=True)
                UI_ELEMENTS['title']           = dpg.add_input_text(label='Song title')
                UI_ELEMENTS['title_yomigana']  = dpg.add_input_text(label='Song title (yomigana)', hint='Song title in half-width katakana')
                UI_ELEMENTS['artist']          = dpg.add_input_text(label='Song artist')
                UI_ELEMENTS['artist_yomigana'] = dpg.add_input_text(label='Song artist (yomigana)', hint='Song artist in half-width katakana')
                UI_ELEMENTS['ascii_label']     = dpg.add_input_text(label='Song label', hint='Song identifier in filesystem')
                UI_ELEMENTS['min_bpm']         = dpg.add_input_float(label='Minimum BPM', min_value=0, max_value=1000, min_clamped=True, max_clamped=True, format='%.2f')
                UI_ELEMENTS['max_bpm']         = dpg.add_input_float(label='Maximum BPM', min_value=0, max_value=1000, min_clamped=True, max_clamped=True, format='%.2f')
                UI_ELEMENTS['release_date']    = dpg.add_input_text(label='Release date', decimal=True)
                UI_ELEMENTS['music_volume']    = dpg.add_slider_int(label='Music volume', clamped=True, min_value=0, max_value=100)
                UI_ELEMENTS['background']      = dpg.add_combo(list(GameBackground), label='Game background')
                UI_ELEMENTS['inf_ver']         = dpg.add_combo(list(InfVer), label='Infinite version')

                # TODO: Background preview

            with dpg.collapsing_header(label='Chart info', show=False, default_open=True) as section_chart_info:
                UI_ELEMENTS['section_chart_info'] = section_chart_info

                UI_ELEMENTS['level'] = dpg.add_slider_int(label='Level', clamped=True, min_value=1, max_value=20)
                UI_ELEMENTS['difficulty'] = dpg.add_combo(list(DifficultySlot), label='Difficulty')
                UI_ELEMENTS['effector'] = dpg.add_input_text(label='Effector')
                UI_ELEMENTS['illustrator'] = dpg.add_input_text(label='Illustrator')

            with dpg.collapsing_header(label='Effect info', show=False, default_open=True) as section_effect_info:
                UI_ELEMENTS['section_effect_info'] = section_effect_info

            with dpg.collapsing_header(label='Track auto tab info', show=False, default_open=True) as section_filter_info:
                UI_ELEMENTS['section_filter_info'] = section_filter_info

    dpg.set_primary_window(primary_window, True)

    print(UI_ELEMENTS)

    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()


if __name__ == '__main__':
    main()

"""
with open(sys.argv[1], 'r', encoding='utf-8-sig') as f:
    parser = KSHParser(f)

    with open('test.xml', 'w') as f:
        parser.write_xml(f)

    with open('test.vox', 'w') as f:
        parser.write_vox(f)
"""
