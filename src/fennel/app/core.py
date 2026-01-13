import numpy as np
import pandas as pd
from pathlib import Path

from trame.app import TrameApp
from trame.decorators import change, controller
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, html


# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------

VELOCITY_SCALE = 1000
KM2M = 1.0e3
RADIUS_EARTH = 6371000


# ---------------------------------------------------------
# Coordinate transformation utilities
# ---------------------------------------------------------

def wgs84_to_web_mercator(lon, lat):
    """Converts decimal (longitude, latitude) to Web Mercator (x, y)"""
    EARTH_RADIUS = 6378137.0  # Earth's radius (m)
    x = EARTH_RADIUS * np.deg2rad(lon)
    y = EARTH_RADIUS * np.log(np.tan((np.pi / 4.0 + np.deg2rad(lat) / 2.0)))
    return x, y


def wrap2360(lon):
    """Wrap longitude to 0-360 range"""
    lon[np.where(lon < 0.0)] += 360.0
    return lon


# ---------------------------------------------------------
# Main Trame App class
# ---------------------------------------------------------

class MyTrameApp(TrameApp):
    def __init__(self, server=None):
        super().__init__(server, client_type="vue3")

        # --hot-reload arg optional logic
        if self.server.hot_reload:
            self.server.controller.on_server_reload.add(self._build_ui)

        # Initialize state variables
        self.state.trame__title = "Earthquake Data Viewer"
        self.state.velocity_scale = 1
        self.state.folder_1_path = "---"
        self.state.folder_2_path = "---"

        # Data storage
        self.folder_1_data = None
        self.folder_2_data = None

        # Visibility controls for folder 1
        self.state.show_locs_1 = False
        self.state.show_obs_1 = False
        self.state.show_mod_1 = False
        self.state.show_res_1 = False
        self.state.show_rot_1 = False
        self.state.show_seg_1 = False
        self.state.show_tri_1 = False
        self.state.show_str_1 = False
        self.state.show_mog_1 = False
        self.state.show_res_mag_1 = False
        self.state.show_seg_color_1 = False
        self.state.seg_slip_type_1 = "ss"
        self.state.show_tde_1 = False
        self.state.tde_slip_type_1 = "ss"
        self.state.show_fault_proj_1 = False

        # Visibility controls for folder 2
        self.state.show_locs_2 = False
        self.state.show_obs_2 = False
        self.state.show_mod_2 = False
        self.state.show_res_2 = False
        self.state.show_rot_2 = False
        self.state.show_seg_2 = False
        self.state.show_tri_2 = False
        self.state.show_str_2 = False
        self.state.show_mog_2 = False
        self.state.show_res_mag_2 = False
        self.state.show_seg_color_2 = False
        self.state.seg_slip_type_2 = "ss"
        self.state.show_tde_2 = False
        self.state.tde_slip_type_2 = "ss"
        self.state.show_fault_proj_2 = False

        # Shared controls
        self.state.show_res_compare = False

        # build ui
        self._build_ui()

    @controller.set("load_folder_1")
    def load_folder_1(self):
        """Load data from folder 1"""
        # TODO: Implement file dialog and data loading
        print("Load folder 1 clicked")
        pass

    @controller.set("load_folder_2")
    def load_folder_2(self):
        """Load data from folder 2"""
        # TODO: Implement file dialog and data loading
        print("Load folder 2 clicked")
        pass

    @change("velocity_scale")
    def on_velocity_scale_change(self, velocity_scale, **kwargs):
        """Update velocity vector scaling"""
        print(f"Velocity scale changed to: {velocity_scale}")
        # TODO: Update visualization

    def _build_ui(self, *args, **kwargs):
        with SinglePageLayout(self.server) as self.ui:
            # Toolbar
            self.ui.title.set_text("Earthquake Data Viewer")

            # Main content - recreating Panel GridSpec layout
            with self.ui.content:
                with vuetify3.VContainer(fluid=True, classes="pa-0 fill-height", style="max-height: 700px;"):
                    # Main grid: 2 control columns + 1 large map area
                    with vuetify3.VRow(classes="fill-height", no_gutters=True):

                        # LEFT COLUMN - Folder 1 Controls (grid col 0, rows 0-6)
                        with vuetify3.VCol(cols=1, classes="pa-2 d-flex flex-column", style="overflow-y: auto;"):
                            # Row 0-1: Load button and velocity controls
                            vuetify3.VBtn(
                                "load",
                                click=self.load_folder_1,
                                color="success",
                                block=True,
                                size="small",
                            )
                            html.Div("{{ folder_1_path }}", classes="text-caption mt-1 mb-2", style="font-size: 0.7rem;")

                            # Velocity checkboxes
                            vuetify3.VCheckbox(
                                v_model="show_locs_1",
                                label="locs",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_obs_1",
                                label="obs",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_mod_1",
                                label="mod",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_res_1",
                                label="res",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_rot_1",
                                label="rot",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_seg_1",
                                label="seg",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_tri_1",
                                label="tri",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_str_1",
                                label="str",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_mog_1",
                                label="mog",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_res_mag_1",
                                label="res mag",
                                hide_details=True,
                                density="compact",
                            )

                            vuetify3.VDivider(classes="my-2")

                            # Row 5: Residual comparison and velocity scale
                            vuetify3.VCheckbox(
                                v_model="show_res_compare",
                                label="res compare",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VSlider(
                                v_model=("velocity_scale", 1),
                                label="vel scale",
                                min=0,
                                max=50,
                                step=1,
                                thumb_label=True,
                                density="compact",
                                hide_details=True,
                            )

                            vuetify3.VDivider(classes="my-2")

                            # Row 6: Segment/TDE color controls
                            vuetify3.VCheckbox(
                                v_model="show_seg_color_1",
                                label="slip",
                                hide_details=True,
                                density="compact",
                            )
                            with vuetify3.VBtnToggle(
                                v_model="seg_slip_type_1",
                                mandatory=True,
                                density="compact",
                                divided=True,
                            ):
                                vuetify3.VBtn("ss", value="ss", size="x-small")
                                vuetify3.VBtn("ds", value="ds", size="x-small")

                            vuetify3.VCheckbox(
                                v_model="show_tde_1",
                                label="tde",
                                hide_details=True,
                                density="compact",
                            )
                            with vuetify3.VBtnToggle(
                                v_model="tde_slip_type_1",
                                mandatory=True,
                                density="compact",
                                divided=True,
                            ):
                                vuetify3.VBtn("ss", value="ss", size="x-small")
                                vuetify3.VBtn("ds", value="ds", size="x-small")

                            vuetify3.VCheckbox(
                                v_model="show_fault_proj_1",
                                label="fault proj",
                                hide_details=True,
                                density="compact",
                            )

                        # MIDDLE COLUMN - Folder 2 Controls (grid col 1, rows 0-6)
                        with vuetify3.VCol(cols=1, classes="pa-2 d-flex flex-column", style="overflow-y: auto;"):
                            # Row 0-1: Load button and velocity controls
                            vuetify3.VBtn(
                                "load",
                                click=self.load_folder_2,
                                color="success",
                                block=True,
                                size="small",
                            )
                            html.Div("{{ folder_2_path }}", classes="text-caption mt-1 mb-2", style="font-size: 0.7rem;")

                            # Velocity checkboxes
                            vuetify3.VCheckbox(
                                v_model="show_locs_2",
                                label="locs",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_obs_2",
                                label="obs",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_mod_2",
                                label="mod",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_res_2",
                                label="res",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_rot_2",
                                label="rot",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_seg_2",
                                label="seg",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_tri_2",
                                label="tri",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_str_2",
                                label="str",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_mog_2",
                                label="mog",
                                hide_details=True,
                                density="compact",
                            )
                            vuetify3.VCheckbox(
                                v_model="show_res_mag_2",
                                label="res mag",
                                hide_details=True,
                                density="compact",
                            )

                            vuetify3.VDivider(classes="my-2")

                            # Row 6: Segment/TDE color controls
                            vuetify3.VCheckbox(
                                v_model="show_seg_color_2",
                                label="slip",
                                hide_details=True,
                                density="compact",
                            )
                            with vuetify3.VBtnToggle(
                                v_model="seg_slip_type_2",
                                mandatory=True,
                                density="compact",
                                divided=True,
                            ):
                                vuetify3.VBtn("ss", value="ss", size="x-small")
                                vuetify3.VBtn("ds", value="ds", size="x-small")

                            vuetify3.VCheckbox(
                                v_model="show_tde_2",
                                label="tde",
                                hide_details=True,
                                density="compact",
                            )
                            with vuetify3.VBtnToggle(
                                v_model="tde_slip_type_2",
                                mandatory=True,
                                density="compact",
                                divided=True,
                            ):
                                vuetify3.VBtn("ss", value="ss", size="x-small")
                                vuetify3.VBtn("ds", value="ds", size="x-small")

                            vuetify3.VCheckbox(
                                v_model="show_fault_proj_2",
                                label="fault proj",
                                hide_details=True,
                                density="compact",
                            )

                        # RIGHT LARGE AREA - Map and Colorbars (grid cols 2-10, rows 0-8)
                        with vuetify3.VCol(cols=10, classes="pa-0 d-flex flex-column"):
                            # Main map area (rows 0-8)
                            with vuetify3.VCard(classes="flex-grow-1", style="min-height: 0;"):
                                html.Div(
                                    "Map visualization will go here",
                                    style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background-color: #f5f5f5;",
                                )

                            # Colorbar area (row 8)
                            with vuetify3.VCard(classes="pa-2", height="50", flat=True):
                                html.Div(
                                    "Color bars will go here",
                                    style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 0.8rem;",
                                )
