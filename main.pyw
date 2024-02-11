#!/usr/bin/env python
import logging
import re
import time

import dearpygui.dearpygui as dpg

from dataclasses import Field
from enum import Enum
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable

from exporter.audio import get_2dxs
from exporter.images import BG_WIDTH, BG_HEIGHT, GMBGHandler, get_game_backgrounds, get_jacket_images
from sdvxparser.classes.effects import Effect, EffectEntry, FXType, enum_to_effect
from sdvxparser.classes.enums import DifficultySlot, GameBackground, InfVer
from sdvxparser.classes.filters import AutoTabEntry, AutoTabSetting
from sdvxparser.classes.time import TimePoint
from sdvxparser.parser.base import SongChartContainer
from sdvxparser.parser.ksh import KSHParser

ObjectID = int | str
# fmt: off
SLOT_MAPPING = {
    DifficultySlot.NOVICE  : "LI",
    DifficultySlot.ADVANCED: "CH",
    DifficultySlot.EXHAUST : "EX",
    DifficultySlot.INFINITE: "IN",
    DifficultySlot.MAXIMUM : "IN",
}
# fmt: on
SONG_INFO_FIELDS = [
    "id",
    "title",
    "title_yomigana",
    "artist",
    "artist_yomigana",
    "ascii_label",
    "min_bpm",
    "max_bpm",
    "release_date",
    "music_volume",
    "background",
    "inf_ver",
]
CHART_INFO_FIELDS = [
    "level",
    "difficulty",
    "effector",
    "illustrator",
]
YOMIGANA_VALIDATION_REGEX = re.compile("^[\uFF66-\uFF9F]+")
ENUM_REGEX = re.compile(r"\((\d+)\)")
GREY_TEXT_COLOR = 120, 120, 120, 255


class FunctionHandler(logging.Handler):
    _handler: Callable[[str], Any]

    def __init__(self, callable: Callable[[str], Any], level: int | str = 0) -> None:
        super().__init__(level)
        self._handler = callable

    def emit(self, record: logging.LogRecord) -> None:
        self._handler(self.format(record))


class KSH2VOXApp:
    ui: dict[str, ObjectID] = dict()
    reverse_ui_map: dict[ObjectID, str] = dict()

    song_chart_data: SongChartContainer
    gmbg_data: GMBGHandler

    current_path: Path | None = None
    background_id: int = 0
    gmbg_available: bool = True
    gmbg_visible: bool = False
    gmbg_visible_time: float = 0
    gmbg_images: list[list[float]] = list()
    gmbg_image_index: int = 0
    popup_result: bool = False

    current_file_path: Path
    effect_params: dict[ObjectID, dict[str, ObjectID]]
    autotab_list: dict[ObjectID, TimePoint]

    logger: logging.Logger

    def __init__(self):
        self.gmbg_data = get_game_backgrounds()
        self.effect_params = {}

        logging.basicConfig(format="[%(levelname)s %(asctime)s] %(name)s: %(message)s", level=logging.DEBUG)

        self.logger = logging.getLogger("main")

        warning_handler = FunctionHandler(self.log)
        warning_handler.setLevel(logging.WARNING)
        warning_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logging.getLogger("").addHandler(warning_handler)

        dpg.create_context()
        dpg.create_viewport(title="KSH Exporter", width=650, height=850, resizable=False)
        dpg.set_viewport_small_icon("resources/icon.ico")
        dpg.set_viewport_large_icon("resources/icon.ico")
        dpg.setup_dearpygui()

        # ================ #
        # TEXTURE REGISTRY #
        # ================ #

        with dpg.texture_registry():
            self.ui["gmbg_texture"] = dpg.add_dynamic_texture(
                width=BG_WIDTH, height=BG_HEIGHT, default_value=[0.0, 0.0, 0.0, 1.0] * (BG_WIDTH * BG_HEIGHT)
            )

        # ================= #
        # WINDOW/APP LAYOUT #
        # ================= #

        with dpg.window(label="KSH Exporter") as self.ui["primary_window"]:
            self.ui["throbber"] = dpg.add_loading_indicator(
                show=False, pos=(550, 20), style=1, radius=4, color=(15, 86, 135)
            )

            with dpg.group() as main_buttons:
                with dpg.group(horizontal=True):
                    self.ui["open_button"] = dpg.add_button(label="Open file...", callback=self.load_ksh)
                    self.ui["loaded_file"] = dpg.add_text("[no file loaded]")

                dpg.add_spacer(height=1)

                with dpg.group(horizontal=True) as self.ui["save_group"]:
                    self.ui["vox_button"] = dpg.add_button(label="Save VOX...", callback=self.export_vox, enabled=False)
                    self.ui["xml_button"] = dpg.add_button(label="Save XML...", callback=self.export_xml, enabled=False)
                    self.ui["2dx_button"] = dpg.add_button(
                        label="Export 2DX...", callback=self.export_2dx, enabled=False
                    )
                    self.ui["jackets_button"] = dpg.add_button(
                        label="Export jackets...", callback=self.export_jacket, enabled=False
                    )

            dpg.add_spacer(height=1)

            with dpg.child_window(height=510, width=-1, border=False) as self.ui["info_container"]:
                with dpg.tab_bar(show=False) as self.ui["inner_info_container"]:
                    with dpg.tab(label="Song info") as self.ui["section_song_info"]:
                        self.ui["id"] = dpg.add_input_int(
                            label="Song ID", min_clamped=True, callback=self.update_and_validate
                        )
                        self.ui["title"] = dpg.add_input_text(label="Song title", callback=self.update_and_validate)
                        self.ui["title_yomigana"] = dpg.add_input_text(
                            label="Song title (yomigana)",
                            hint="Song title in half-width katakana",
                            callback=self.update_and_validate,
                        )
                        self.ui["artist"] = dpg.add_input_text(label="Song artist", callback=self.update_and_validate)
                        self.ui["artist_yomigana"] = dpg.add_input_text(
                            label="Song artist (yomigana)",
                            hint="Song artist in half-width katakana",
                            callback=self.update_and_validate,
                        )
                        self.ui["ascii_label"] = dpg.add_input_text(
                            label="Song label",
                            hint="Song identifier in filesystem (ASCII only)",
                            callback=self.update_and_validate,
                        )
                        self.ui["min_bpm"] = dpg.add_input_float(
                            label="Minimum BPM",
                            min_value=0,
                            max_value=1000,
                            min_clamped=True,
                            max_clamped=True,
                            format="%.2f",
                            callback=self.update_and_validate,
                        )
                        self.ui["max_bpm"] = dpg.add_input_float(
                            label="Maximum BPM",
                            min_value=0,
                            max_value=1000,
                            min_clamped=True,
                            max_clamped=True,
                            format="%.2f",
                            callback=self.update_and_validate,
                        )
                        self.ui["release_date"] = dpg.add_input_text(
                            label="Release date", decimal=True, callback=self.update_and_validate
                        )
                        self.ui["music_volume"] = dpg.add_slider_int(
                            label="Music volume",
                            default_value=100,
                            clamped=True,
                            min_value=0,
                            max_value=100,
                            callback=self.update_and_validate,
                        )
                        self.ui["background"] = dpg.add_combo(
                            list(str(gmbg) for gmbg in GameBackground),
                            label="Game background",
                            default_value=str(GameBackground.BOOTH_BRIDGE),
                            callback=self.update_and_validate,
                        )
                        self.ui["inf_ver"] = dpg.add_combo(
                            list(str(inf) for inf in InfVer),
                            label="Infinite version",
                            default_value=str(InfVer.INFINITE),
                            callback=self.update_and_validate,
                        )

                        with dpg.tooltip(self.ui["background"]) as self.ui["bg_tooltip"]:
                            self.ui["bg_preview"] = dpg.add_image(self.ui["gmbg_texture"])

                    with dpg.tab(label="Chart info") as self.ui["section_chart_info"]:
                        self.ui["level"] = dpg.add_slider_int(
                            label="Level", clamped=True, min_value=1, max_value=20, callback=self.update_and_validate
                        )
                        self.ui["difficulty"] = dpg.add_combo(
                            list(str(diff) for diff in DifficultySlot),
                            label="Difficulty",
                            callback=self.update_and_validate,
                        )
                        self.ui["effector"] = dpg.add_input_text(label="Effector", callback=self.update_and_validate)
                        self.ui["illustrator"] = dpg.add_input_text(
                            label="Illustrator", callback=self.update_and_validate
                        )

                    with dpg.tab(label="Effects") as self.ui["section_effect_info"]:
                        with dpg.group() as self.ui["section_effect_group"]:
                            self.ui["effect_def_combo"] = dpg.add_combo(
                                label="Effect definition list", callback=self.load_effects
                            )

                            with dpg.group(horizontal=True) as effect_def_buttons:
                                self.ui["effect_def_new"] = dpg.add_button(label="New", callback=self.add_new_effect)
                                self.ui["effect_def_update"] = dpg.add_button(
                                    label="Update", callback=self.update_effect
                                )
                                self.ui["effect_def_delete"] = dpg.add_button(
                                    label="Delete", callback=self.delete_effect
                                )

                            dpg.add_spacer(height=1)

                            with dpg.collapsing_header(label="Effect 1", default_open=True):
                                self.ui["effect_def_1_combo"] = dpg.add_combo(
                                    label="1st effect type", callback=self.load_effect_params
                                )
                                self.effect_params[self.ui["effect_def_1_combo"]] = {}
                                dpg.add_text("Parameters:")

                                with dpg.group() as self.ui["effect_def_1_params"]:
                                    dpg.add_text("No configurable parameters!", color=GREY_TEXT_COLOR)

                            dpg.add_spacer(height=1)

                            with dpg.collapsing_header(label="Effect 2", default_open=True):
                                self.ui["effect_def_2_combo"] = dpg.add_combo(
                                    label="2nd effect type", callback=self.load_effect_params
                                )
                                self.effect_params[self.ui["effect_def_2_combo"]] = {}
                                dpg.add_text("Parameters:")

                                with dpg.group() as self.ui["effect_def_2_params"]:
                                    dpg.add_text("No configurable parameters!", color=GREY_TEXT_COLOR)

                    with dpg.tab(label="Laser effects") as self.ui["section_laser_effect_info"]:
                        with dpg.group() as self.ui["section_laser_effect_group"]:
                            pass

                    with dpg.tab(label="Autotab params") as self.ui["section_autotab_info"]:
                        with dpg.group() as self.ui["section_autotab_group"]:
                            self.ui["autotab_effect_combo"] = dpg.add_combo(
                                label="Effect list", callback=self.update_autotab_params
                            )

                            dpg.add_spacer(height=1)

                            with dpg.group():
                                self.ui["autotab_effect_1_param_combo"] = dpg.add_combo(
                                    label="1st effect param", callback=self.update_autotab_param_settings
                                )

                                with dpg.group() as self.ui["autotab_effect_1_param_setting"]:
                                    dpg.add_text("No configurable parameters!", color=GREY_TEXT_COLOR)

                            dpg.add_spacer(height=1)

                            with dpg.group():
                                self.ui["autotab_effect_2_param_combo"] = dpg.add_combo(
                                    label="2nd effect param", callback=self.update_autotab_param_settings
                                )

                                with dpg.group() as self.ui["autotab_effect_2_param_setting"]:
                                    dpg.add_text("No configurable parameters!", color=GREY_TEXT_COLOR)

            with dpg.child_window(label="Logs", width=-1, height=-1, horizontal_scrollbar=True) as self.ui["log"]:
                self.ui["log_last_line"] = 0

        # ============== #
        # EVENT HANDLERS #
        # ============== #

        with dpg.item_handler_registry() as background_handler:
            dpg.add_item_visible_handler(callback=self.change_image_texture)

        dpg.bind_item_handler_registry(self.ui["background"], background_handler)

        # ============= #
        # FONT REGISTRY #
        # ============= #

        with dpg.font_registry():
            with dpg.font("resources/NotoSansJP-Regular.ttf", 20) as font:
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)

            dpg.bind_font(font)

        # ============== #
        # THEME REGISTRY #
        # ============== #

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

        dpg.bind_item_theme(self.ui["log"], log_theme)

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

        dpg.bind_item_theme(self.ui["primary_window"], primary_window_theme)

        # ================================

        dpg.set_primary_window(self.ui["primary_window"], True)

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
        self.ui["log_last_line"] = dpg.add_text(
            f'[{time.strftime("%H:%M:%S", time.localtime())}] {message}',
            parent=self.ui["log"],
            before=self.ui["log_last_line"],
        )

    def change_image_texture(self):
        if self.gmbg_available and not dpg.get_item_configuration(self.ui["bg_tooltip"])["show"]:
            dpg.show_item(self.ui["bg_tooltip"])
        elif not self.gmbg_available and dpg.get_item_configuration(self.ui["bg_tooltip"])["show"]:
            dpg.hide_item(self.ui["bg_tooltip"])

        if dpg.is_item_hovered(self.ui["background"]) and dpg.is_item_visible(self.ui["bg_preview"]):
            if not self.gmbg_visible:
                self.gmbg_image_index = 0
                self.gmbg_images = self.gmbg_data.get_images(self.background_id)
                self.gmbg_visible = True
                self.gmbg_visible_time = time.time()
                dpg.set_value(self.ui["gmbg_texture"], self.gmbg_images[self.gmbg_image_index])
                return

            now_index = int((time.time() - self.gmbg_visible_time) / 1.5) % len(self.gmbg_images)
            if now_index == self.gmbg_image_index:
                return

            self.gmbg_image_index = now_index
            dpg.set_value(self.ui["gmbg_texture"], self.gmbg_images[self.gmbg_image_index])
        else:
            self.gmbg_visible = False

    def get_combo_index(self, obj: ObjectID) -> int:
        item_config: dict = dpg.get_item_configuration(obj)
        item_list: list = item_config["items"]
        choice_index: int = item_list.index(dpg.get_value(obj))

        return choice_index

    def update_and_validate(self, sender: ObjectID, app_data: Any):
        # Validation
        if sender == self.ui["min_bpm"]:
            if app_data > (value := dpg.get_value(self.ui["max_bpm"])):
                dpg.set_value(sender, value)
        elif sender == self.ui["max_bpm"]:
            if app_data < (value := dpg.get_value(self.ui["min_bpm"])):
                dpg.set_value(sender, value)

        # Convert value back to enum
        if sender in [self.ui["background"], self.ui["inf_ver"], self.ui["difficulty"]]:
            regex_match = ENUM_REGEX.search(app_data)
            if regex_match is not None:
                app_data = int(regex_match.group(1))

        # Update background preview
        if sender == self.ui["background"]:
            self.background_id = app_data
            self.gmbg_available = self.gmbg_data.has_image(self.background_id)

        # Update parser state
        try:
            obj_name = self.get_obj_name(sender)
            if obj_name in SONG_INFO_FIELDS:
                setattr(
                    self.song_chart_data.song_info,
                    obj_name,
                    self.song_chart_data.song_info.__annotations__[obj_name](app_data),
                )
            elif obj_name in CHART_INFO_FIELDS:
                setattr(
                    self.song_chart_data.chart_info,
                    obj_name,
                    self.song_chart_data.chart_info.__annotations__[obj_name](app_data),
                )
        except AttributeError:
            pass

    def populate_effects_list(self, list_index: int = 0):
        effect_list = [f"FX {i + 1}: {fx}" for i, fx in enumerate(self.song_chart_data.chart_info.effect_list)]
        dpg.configure_item(self.ui["effect_def_combo"], items=effect_list)
        dpg.set_value(self.ui["effect_def_combo"], effect_list[list_index])

        self.load_effects(self.ui["effect_def_combo"])
        self.load_effect_params(self.ui["effect_def_1_combo"])
        self.load_effect_params(self.ui["effect_def_2_combo"])

        self.update_effect_def_button_state()

    def load_effects(self, sender: ObjectID):
        choice_index = self.get_combo_index(sender)
        current_effect = self.song_chart_data.chart_info.effect_list[choice_index]

        dpg.set_value(self.ui["effect_def_1_combo"], current_effect.effect1.effect_name)
        dpg.set_value(self.ui["effect_def_2_combo"], current_effect.effect2.effect_name)

        self.load_effect_params(self.ui["effect_def_1_combo"])
        self.load_effect_params(self.ui["effect_def_2_combo"])

    def load_effect_params(self, sender: ObjectID):
        effect_index = self.get_combo_index(self.ui["effect_def_combo"])
        choice_index = self.get_combo_index(sender)

        target: ObjectID | None = None
        if sender == self.ui["effect_def_1_combo"]:
            target = self.ui["effect_def_1_params"]
            reference_fx = self.song_chart_data.chart_info.effect_list[effect_index].effect1
        elif sender == self.ui["effect_def_2_combo"]:
            target = self.ui["effect_def_2_params"]
            reference_fx = self.song_chart_data.chart_info.effect_list[effect_index].effect2
        else:
            return

        self.effect_params[sender] = {}
        dpg.delete_item(target, children_only=True)

        effect_type = FXType(choice_index)
        if effect_type == FXType.NO_EFFECT:
            dpg.add_text("No configurable parameters!", parent=target, color=GREY_TEXT_COLOR)
            return

        if effect_type != reference_fx.effect_index:
            reference_fx = enum_to_effect(effect_type)()

        # Dataclass field magic for inspection
        params: dict[str, Field] = reference_fx.__dataclass_fields__
        for param_name, field_data in params.items():
            display_param_name = param_name.replace("_", " ")
            if field_data.type == float:
                obj_id = dpg.add_input_float(
                    label=display_param_name,
                    parent=target,
                    default_value=getattr(reference_fx, param_name),
                    format="%.2f",
                    step=0.01,
                )
            elif field_data.type == int:
                obj_id = dpg.add_input_int(
                    label=display_param_name, parent=target, default_value=getattr(reference_fx, param_name)
                )
            elif issubclass(field_data.type, Enum):
                obj_id = dpg.add_combo(
                    label=display_param_name,
                    parent=target,
                    default_value=getattr(reference_fx, param_name),
                    items=list(str(enum) for enum in field_data.type),
                )
            else:
                continue
            self.effect_params[sender][param_name] = obj_id

    def update_effect_def_button_state(self) -> None:
        button_state = bool(self.song_chart_data.chart_info.effect_list)
        dpg.configure_item(self.ui["effect_def_update"], enabled=button_state)
        dpg.configure_item(self.ui["effect_def_delete"], enabled=button_state)

    def add_new_effect(self) -> None:
        effect_index = self.get_combo_index(self.ui["effect_def_combo"])
        for autotab_info in self.song_chart_data.chart_info.autotab_infos.values():
            if autotab_info.which < effect_index:
                continue
            autotab_info.which += 1

        autotab_index = self.get_combo_index(self.ui["autotab_effect_combo"])
        if autotab_index >= effect_index:
            autotab_index += 1
        for autotab_setting in self.song_chart_data.chart_info.autotab_list:
            if autotab_setting.effect1.effect_index < effect_index:
                continue
            autotab_setting.effect1.effect_index += 1
            autotab_setting.effect2.effect_index += 1

        self.song_chart_data.chart_info.effect_list.insert(effect_index, EffectEntry())
        self.song_chart_data.chart_info.autotab_list.insert(effect_index, AutoTabEntry(effect_index))

        self.populate_effects_list(effect_index)
        self.update_laser_effect_combo_box()
        self.populate_track_autotab_list(autotab_index)

    def update_effect(self) -> None:
        effect_index = self.get_combo_index(self.ui["effect_def_combo"])
        effect_1_index = self.get_combo_index(self.ui["effect_def_1_combo"])
        effect_2_index = self.get_combo_index(self.ui["effect_def_2_combo"])

        effect_1 = enum_to_effect(FXType(effect_1_index))()
        effect_2 = enum_to_effect(FXType(effect_2_index))()

        pairs: list[tuple[Effect, str]] = [(effect_1, "effect_def_1_combo"), (effect_2, "effect_def_2_combo")]
        for effect_obj, ui_key in pairs:
            for param_name, obj_id in self.effect_params[self.ui[ui_key]].items():
                field_data: Field = effect_obj.__dataclass_fields__[param_name]
                param_value = dpg.get_value(obj_id)
                param_type = field_data.type
                # If it's an enum, it needs to be converted to the underlying value
                if issubclass(param_type, Enum):
                    param_value = self.get_combo_index(obj_id)
                setattr(effect_obj, param_name, param_type(param_value))

        self.song_chart_data.chart_info.effect_list[effect_index] = EffectEntry(effect_1, effect_2)
        self.song_chart_data.chart_info.autotab_list[effect_index] = AutoTabEntry(effect_index)

        self.populate_effects_list(effect_index)
        self.update_laser_effect_combo_box()
        self.populate_track_autotab_list(self.get_combo_index(self.ui["autotab_effect_combo"]))

    def delete_effect(self) -> None:
        effect_index = self.get_combo_index(self.ui["effect_def_combo"])
        for timept, autotab_info in self.song_chart_data.chart_info.autotab_infos.items():
            if autotab_info.which < effect_index:
                continue
            if autotab_info.which == effect_index:
                timept_str = self.song_chart_data.chart_info.timepoint_to_vox(timept)
                self.logger.warning(f"effect corresponding to laser effect at {timept_str} was deleted")
            autotab_info.which -= 1

        autotab_index = self.get_combo_index(self.ui["autotab_effect_combo"])
        if autotab_index >= effect_index:
            autotab_index -= 1
        for autotab_setting in self.song_chart_data.chart_info.autotab_list:
            if autotab_setting.effect1.effect_index < effect_index:
                continue
            autotab_setting.effect1.effect_index -= 1
            autotab_setting.effect2.effect_index -= 1

        self.song_chart_data.chart_info.effect_list.pop(effect_index)
        self.song_chart_data.chart_info.autotab_list.pop(effect_index)

        # Don't allow effect list to be empty
        if not self.song_chart_data.chart_info.effect_list:
            self.song_chart_data.chart_info.effect_list.append(EffectEntry())
            self.song_chart_data.chart_info.autotab_list.pop(effect_index)

        if effect_index == len(self.song_chart_data.chart_info.effect_list):
            effect_index -= 1

        self.populate_effects_list(effect_index)
        self.update_laser_effect_combo_box()
        self.populate_track_autotab_list(autotab_index)

    def populate_laser_effect_list(self) -> None:
        parent = self.ui["section_laser_effect_group"]

        self.autotab_list = {}
        dpg.delete_item(parent, children_only=True)

        dpg.add_text("Laser effects used in chart:", parent=parent)
        for timept, autotab_info in self.song_chart_data.chart_info.autotab_infos.items():
            start_timept = self.song_chart_data.chart_info.timepoint_to_vox(timept)
            end_timept = self.song_chart_data.chart_info.timepoint_to_vox(
                self.song_chart_data.chart_info.add_duration(timept, autotab_info.duration)
            )
            self.autotab_list[
                dpg.add_combo(
                    label=f"{start_timept} ~ {end_timept}",
                    parent=parent,
                    callback=self.update_autotab_value,
                )
            ] = timept

        if not self.song_chart_data.chart_info.autotab_infos:
            dpg.add_text("Laser effects are not used in this chart!", parent=parent, color=GREY_TEXT_COLOR)

        self.update_laser_effect_combo_box()

    def update_laser_effect_combo_box(self) -> None:
        combo_items = [f"FX {i + 1}: {fx}" for i, fx in enumerate(self.song_chart_data.chart_info.effect_list)]

        for obj_id, timept in self.autotab_list.items():
            dpg.configure_item(obj_id, items=combo_items)
            dpg.set_value(obj_id, combo_items[self.song_chart_data.chart_info.autotab_infos[timept].which])

    def update_autotab_value(self, sender: ObjectID) -> None:
        filter_name = dpg.get_item_label(sender)
        if filter_name is None:
            return

        effect_index = self.get_combo_index(sender)
        timept = self.autotab_list[sender]
        self.song_chart_data.chart_info.autotab_infos[timept].which = effect_index

    def populate_track_autotab_list(self, list_index: int = 0) -> None:
        effect_list = [f"FX {i + 1}: {fx}" for i, fx in enumerate(self.song_chart_data.chart_info.effect_list)]
        dpg.configure_item(self.ui["autotab_effect_combo"], items=effect_list)
        dpg.set_value(self.ui["autotab_effect_combo"], effect_list[list_index])

        self.update_autotab_params()

    def update_autotab_params(self):
        effect_index = self.get_combo_index(self.ui["autotab_effect_combo"])
        effect_entry = self.song_chart_data.chart_info.effect_list[effect_index]
        autotab_params = self.song_chart_data.chart_info.autotab_list[effect_index]

        param_list = ["(none)"]
        param_list += effect_entry.effect1.__dataclass_fields__.keys()
        dpg.configure_item(
            self.ui["autotab_effect_1_param_combo"],
            items=param_list,
            label=f"1st effect ({effect_entry.effect1.effect_name}) param",
        )
        dpg.set_value(self.ui["autotab_effect_1_param_combo"], param_list[autotab_params.effect1.param_index])

        param_list = ["(none)"]
        param_list += effect_entry.effect2.__dataclass_fields__.keys()
        dpg.configure_item(
            self.ui["autotab_effect_2_param_combo"],
            items=param_list,
            label=f"2nd effect ({effect_entry.effect2.effect_name}) param",
        )
        dpg.set_value(self.ui["autotab_effect_2_param_combo"], param_list[autotab_params.effect2.param_index])

        self.update_autotab_param_settings()

    def update_autotab_param_settings(self, sender: ObjectID | None = None):
        effect_index = self.get_combo_index(self.ui["autotab_effect_combo"])

        for i in range(1, 3):
            combo_id = self.ui[f"autotab_effect_{i}_param_combo"]
            parent = self.ui[f"autotab_effect_{i}_param_setting"]
            param_name = dpg.get_value(combo_id)
            autotab_setting: AutoTabSetting = getattr(
                self.song_chart_data.chart_info.autotab_list[effect_index], f"effect{i}"
            )
            effect: Effect = getattr(self.song_chart_data.chart_info.effect_list[effect_index], f"effect{i}")

            if sender is not None and sender != combo_id:
                continue

            dpg.delete_item(parent, children_only=True)

            combo_index = self.get_combo_index(combo_id)
            if combo_index == 0:
                dpg.add_text("No configurable parameters!", parent=parent, color=GREY_TEXT_COLOR)
            else:
                if sender is not None:
                    autotab_setting.param_index = combo_index
                    autotab_setting.min_value = getattr(effect, param_name)
                    autotab_setting.max_value = getattr(effect, param_name)
                param_value = (autotab_setting.min_value, autotab_setting.max_value)

                dpg.add_input_floatx(
                    label="Param range",
                    parent=parent,
                    default_value=param_value,
                    format="%.2f",
                    size=2,
                    callback=self.update_chart_autotab_values,
                    user_data=i,
                )

    def update_chart_autotab_values(self, sender: ObjectID, app_data: tuple[float, float], user_data: int):
        effect_index = self.get_combo_index(self.ui["autotab_effect_combo"])
        autotab_setting: AutoTabSetting = getattr(
            self.song_chart_data.chart_info.autotab_list[effect_index], f"effect{user_data}"
        )

        min_value, max_value, *_ = app_data
        autotab_setting.min_value = min_value
        autotab_setting.max_value = max_value

    def load_ksh(self):
        with disable_buttons(self), show_throbber(self):
            file_path_str = filedialog.askopenfilename(
                filetypes=(
                    ("K-Shoot Mania charts", "*.ksh"),
                    ("All files", "*"),
                ),
                initialdir=self.current_path,
                title="Open KSH file",
            )
            if not file_path_str:
                return

            self.current_file_path = Path(file_path_str)
            dpg.set_value(self.ui["loaded_file"], self.current_file_path)
            self.log(f'Reading from "{self.current_file_path}"...')

            with self.current_file_path.open("r", encoding="utf-8-sig") as f:
                self.song_chart_data = KSHParser().parse(f)

            self.current_path = self.current_file_path.parent
            self.log(
                f"Chart loaded: {self.song_chart_data.song_info.title} / {self.song_chart_data.song_info.artist} "
                f"({SLOT_MAPPING[self.song_chart_data.chart_info.difficulty]} {self.song_chart_data.chart_info.level})"
            )

            for field in SONG_INFO_FIELDS:
                dpg.set_value(self.ui[field], getattr(self.song_chart_data.song_info, field))
            for field in CHART_INFO_FIELDS:
                dpg.set_value(self.ui[field], getattr(self.song_chart_data.chart_info, field))

            dpg.configure_item(self.ui["effect_def_1_combo"], items=list(FXType))
            dpg.configure_item(self.ui["effect_def_2_combo"], items=list(FXType))

            self.populate_effects_list()
            self.populate_laser_effect_list()
            self.populate_track_autotab_list()

            self.background_id = self.song_chart_data.song_info.background.value
            self.gmbg_available = self.gmbg_data.has_image(self.background_id)

        # Remove placeholder text and show hidden parts
        dpg.show_item(self.ui["inner_info_container"])

        # Main buttons
        dpg.configure_item(self.ui["vox_button"], enabled=True)
        dpg.configure_item(self.ui["xml_button"], enabled=True)
        dpg.configure_item(self.ui["2dx_button"], enabled=True)
        dpg.configure_item(self.ui["jackets_button"], enabled=True)

        # Effect definition buttons
        self.update_effect_def_button_state()

    def validate_metadata(self):
        title_check = YOMIGANA_VALIDATION_REGEX.match(self.song_chart_data.song_info.title_yomigana)
        if title_check is None:
            self.logger.warning("Title yomigana is not a valid yomigana string or is empty")

        artist_check = YOMIGANA_VALIDATION_REGEX.match(self.song_chart_data.song_info.artist_yomigana)
        if artist_check is None:
            self.logger.warning("Artist yomigana is not a valid yomigana string or is empty")

        if not (self.song_chart_data.song_info.ascii_label and self.song_chart_data.song_info.ascii_label.isascii()):
            self.logger.warning("ASCII label is not an ASCII string or is empty")

        try:
            time.strptime(self.song_chart_data.song_info.release_date, "%Y%m%d")
        except ValueError:
            self.logger.warning("Release date is not a valid YYYYMMDD date string")

    def export_vox(self):
        with disable_buttons(self), show_throbber(self):
            file_name = (
                f"{self.song_chart_data.song_info.id:04}_{self.song_chart_data.song_info.ascii_label}_"
                f"{self.song_chart_data.chart_info.difficulty.to_shorthand()}.vox"
            )
            file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension="vox",
                filetypes=(
                    ("VOX files", "*.vox"),
                    ("All files", "*"),
                ),
                initialdir=self.current_path,
                initialfile=file_name,
                title="Export VOX file",
            )
            if not file_path:
                return None
            file_name = Path(file_path).name

            self.log(f'Writing to "{file_path}"...')
            self.current_path = Path(file_path).parent
            with open(file_path, "w") as f:
                self.song_chart_data.write_vox(f)

            self.log(f"File saved: {file_name}")

    def export_xml(self):
        with disable_buttons(self), show_throbber(self):
            self.validate_metadata()

            file_name = (
                f"{self.song_chart_data.song_info.id:04}_{self.song_chart_data.song_info.ascii_label}_"
                f"{self.song_chart_data.chart_info.difficulty.to_shorthand()}.xml"
            )
            file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension="xml",
                filetypes=(
                    ("XML files", "*.xml"),
                    ("All files", "*"),
                ),
                initialdir=self.current_path,
                initialfile=file_name,
                title="Export XML file",
            )
            if not file_path:
                return None
            file_name = Path(file_path).name

            self.log(f'Writing to "{file_path}"...')
            self.current_path = Path(file_path).parent
            with open(file_path, "w") as f:
                self.song_chart_data.write_xml(f)

            self.log(f"File saved: {file_name}")

    def export_2dx(self):
        with disable_buttons(self), show_throbber(self):
            audio_paths = []
            audio_path = (self.current_file_path.parent / self.song_chart_data.chart_info.music_path).resolve()
            if not audio_path.exists():
                self.log(f'Cannot open "{audio_path}".')
                return
            audio_paths.append(audio_path)

            effect_path = None
            if self.song_chart_data.chart_info.effected_path:
                effect_path = (self.current_file_path.parent / self.song_chart_data.chart_info.effected_path).resolve()
                if not effect_path.exists():
                    self.log(f'Cannot open "{effect_path}".')
                    return
                audio_paths.append(effect_path)

            song_label = f"{self.song_chart_data.song_info.id:04}_{self.song_chart_data.song_info.ascii_label}"
            song_file_name = f"{song_label}.2dx"
            song_file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension="2dx",
                filetypes=(
                    ("2DX files", "*.2dx"),
                    ("All files", "*"),
                ),
                initialdir=self.current_path,
                initialfile=song_file_name,
                title="Save song's 2DX file",
            )
            if not song_file_path:
                return None
            song_file_name = Path(song_file_path).name

            preview_file_name = f"{song_label}_pre.2dx"
            preview_file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension="2dx",
                filetypes=(
                    ("2DX files", "*.2dx"),
                    ("All files", "*"),
                ),
                initialdir=self.current_path,
                initialfile=preview_file_name,
                title="Save preview's 2DX file",
            )
            if not preview_file_path:
                return None
            preview_file_name = Path(preview_file_path).name

            self.log("Converting audio to 2DX format...")
            song_bytes, preview_bytes = get_2dxs(
                audio_paths,
                song_label,
                self.song_chart_data.chart_info.preview_start,
                self.song_chart_data.chart_info.music_offset,
            )

            self.log(f'Writing to "{song_file_path}"...')
            with open(song_file_path, "wb") as f:
                f.write(song_bytes)
            self.log(f"File saved: {song_file_name}")

            self.log(f'Writing to "{preview_file_path}"...')
            with open(preview_file_path, "wb") as f:
                f.write(preview_bytes)
            self.log(f"File saved: {preview_file_name}")

    def export_jacket(self):
        with disable_buttons(self), show_throbber(self):
            jacket_path = (self.current_file_path.parent / self.song_chart_data.chart_info.jacket_path).resolve()
            if not jacket_path.exists():
                self.log(f'Cannot open "{jacket_path}".')
                return

            jacket_r_file_name = (
                f"jk_{self.song_chart_data.song_info.id:04}_{self.song_chart_data.chart_info.difficulty.value}.png"
            )
            jacket_b_file_name = (
                f"jk_{self.song_chart_data.song_info.id:04}_{self.song_chart_data.chart_info.difficulty.value}_b.png"
            )
            jacket_s_file_name = (
                f"jk_{self.song_chart_data.song_info.id:04}_{self.song_chart_data.chart_info.difficulty.value}_s.png"
            )

            jacket_r_file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension="png",
                filetypes=(
                    ("PNG images", "*.png"),
                    ("All files", "*"),
                ),
                initialdir=self.current_path,
                initialfile=jacket_r_file_name,
                title="Save regular jacket image",
            )
            if not jacket_r_file_path:
                return None
            jacket_r_file_name = Path(jacket_r_file_path).name

            jacket_b_file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension="png",
                filetypes=(
                    ("PNG images", "*.png"),
                    ("All files", "*"),
                ),
                initialdir=self.current_path,
                initialfile=jacket_b_file_name,
                title="Save large jacket image",
            )
            if not jacket_b_file_path:
                return None
            jacket_b_file_name = Path(jacket_b_file_path).name

            jacket_s_file_path = filedialog.asksaveasfilename(
                confirmoverwrite=True,
                defaultextension="png",
                filetypes=(
                    ("PNG images", "*.png"),
                    ("All files", "*"),
                ),
                initialdir=self.current_path,
                initialfile=jacket_s_file_name,
                title="Save small jacket image",
            )
            if not jacket_s_file_path:
                return None
            jacket_s_file_name = Path(jacket_s_file_path).name

            self.log("Resizing jacket image...")
            jk_r_bytes, jk_b_bytes, jk_s_bytes = get_jacket_images(jacket_path)

            self.log(f'Writing to "{jacket_r_file_path}"...')
            with open(jacket_r_file_path, "wb") as f:
                f.write(jk_r_bytes)
            self.log(f"File saved: {jacket_r_file_name}")

            self.log(f'Writing to "{jacket_b_file_path}"...')
            with open(jacket_b_file_path, "wb") as f:
                f.write(jk_b_bytes)
            self.log(f"File saved: {jacket_b_file_name}")

            self.log(f'Writing to "{jacket_s_file_path}"...')
            with open(jacket_s_file_path, "wb") as f:
                f.write(jk_s_bytes)
            self.log(f"File saved: {jacket_s_file_name}")


class disable_buttons:
    app: KSH2VOXApp
    buttons: list[str]
    button_state: dict[str, bool]

    def __init__(self, app: KSH2VOXApp):
        self.app = app
        # fmt: off
        self.buttons = [
            # Main buttons
            "open_button", "vox_button", "xml_button", "2dx_button", "jackets_button",
            # Effect definition buttons
            "effect_def_new",
            "effect_def_update",
            "effect_def_delete",
        ]
        # fmt: on
        self.button_state = {}

    def __enter__(self):
        for button in self.buttons:
            self.button_state[button] = dpg.get_item_configuration(self.app.ui[button])["enabled"]
            dpg.configure_item(self.app.ui[button], enabled=False)

    def __exit__(self, *args, **kwargs):
        for button, state in self.button_state.items():
            dpg.configure_item(self.app.ui[button], enabled=state)


class show_throbber:
    app: KSH2VOXApp

    def __init__(self, app: KSH2VOXApp):
        self.app = app

    def __enter__(self):
        dpg.show_item(self.app.ui["throbber"])

    def __exit__(self, *args, **kwargs):
        dpg.hide_item(self.app.ui["throbber"])


if __name__ == "__main__":
    KSH2VOXApp()
