import numpy as np
import pandas as pd
from pathlib import Path
import sys

from trame.app import TrameApp
from trame.decorators import change, controller
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, html

# Import pydeck and trame-deckgl
import pydeck as pdk
from trame_deckgl.widgets import deckgl

# Import mapbox token
try:
    mapbox_token_path = Path(__file__).parent.parent.parent.parent / "result_viewer" / "mapbox_token.py"
    sys.path.insert(0, str(mapbox_token_path.parent))
    from mapbox_token import mapbox_access_token
    HAS_MAPBOX_TOKEN = mapbox_access_token and mapbox_access_token != "INSERT_TOKEN_HERE"
except ImportError:
    mapbox_access_token = None
    HAS_MAPBOX_TOKEN = False


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


def sph2cart(lon, lat, radius):
    """Convert spherical coordinates to Cartesian"""
    lon_rad = np.deg2rad(lon)
    lat_rad = np.deg2rad(lat)
    x = radius * np.cos(lat_rad) * np.cos(lon_rad)
    y = radius * np.cos(lat_rad) * np.sin(lon_rad)
    z = radius * np.sin(lat_rad)
    return x, y, z


def cart2sph(x, y, z):
    """Convert Cartesian coordinates to spherical"""
    azimuth = np.arctan2(y, x)
    elevation = np.arctan2(z, np.sqrt(x**2 + y**2))
    r = np.sqrt(x**2 + y**2 + z**2)
    return azimuth, elevation, r


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

        # Map state
        self.state.map_latitude = 37.0
        self.state.map_longitude = -122.0
        self.state.map_zoom = 6
        self.state.map_pitch = 0
        self.state.map_bearing = 0

        # build ui
        self._build_ui()

    def _initialize_map(self, **kwargs):
        """Initialize the map with default view"""
        deck = pdk.Deck(
            map_provider="mapbox" if HAS_MAPBOX_TOKEN else "carto",
            map_style="mapbox://styles/mapbox/light-v9" if HAS_MAPBOX_TOKEN else pdk.map_styles.LIGHT,
            initial_view_state=pdk.ViewState(
                latitude=self.state.map_latitude,
                longitude=self.state.map_longitude,
                zoom=self.state.map_zoom,
                pitch=self.state.map_pitch,
                bearing=self.state.map_bearing,
            ),
            layers=[],
        )
        self.ctrl.deck_update(deck)

    def _load_data(self, folder_number):
        """Load earthquake data from a folder"""
        # TODO: Replace with proper folder selection dialog
        # Hardcoded path for now
        base_path = Path(__file__).parent.parent.parent.parent / "result_viewer"
        folder_name = base_path / "0000000157"

        # Update folder display
        folder_path_var = f"folder_{folder_number}_path"
        self.state[folder_path_var] = folder_name.name

        # Read CSV files
        station = pd.read_csv(folder_name / "model_station.csv")
        segment = pd.read_csv(folder_name / "model_segment.csv")
        meshes = pd.read_csv(folder_name / "model_meshes.csv")

        # Calculate residual magnitude
        resmag = np.sqrt(
            np.power(station.model_east_vel_residual, 2)
            + np.power(station.model_north_vel_residual, 2)
        )

        # Convert station coordinates to Web Mercator
        lon_station = station.lon.values
        lat_station = station.lat.values
        x_station, y_station = wgs84_to_web_mercator(lon_station, lat_station)

        # Convert segment coordinates to Web Mercator
        lon1_seg = segment.lon1.values
        lat1_seg = segment.lat1.values
        lon2_seg = segment.lon2.values
        lat2_seg = segment.lat2.values
        x1_seg, y1_seg = wgs84_to_web_mercator(lon1_seg, lat1_seg)
        x2_seg, y2_seg = wgs84_to_web_mercator(lon2_seg, lat2_seg)

        # Process meshes (TDE)
        lon1_mesh = meshes["lon1"].values.copy()
        lat1_mesh = meshes["lat1"].values
        dep1_mesh = meshes["dep1"].values
        lon2_mesh = meshes["lon2"].values.copy()
        lat2_mesh = meshes["lat2"].values
        dep2_mesh = meshes["dep2"].values
        lon3_mesh = meshes["lon3"].values.copy()
        lat3_mesh = meshes["lat3"].values
        dep3_mesh = meshes["dep3"].values
        mesh_idx = meshes["mesh_idx"].values

        # Wrap longitude to 0-360
        lon1_mesh[lon1_mesh < 0] += 360
        lon2_mesh[lon2_mesh < 0] += 360
        lon3_mesh[lon3_mesh < 0] += 360

        # Calculate element geometry for steep dipping meshes
        tri_leg1 = np.transpose([
            np.deg2rad(lon2_mesh - lon1_mesh),
            np.deg2rad(lat2_mesh - lat1_mesh),
            (1 + KM2M * dep2_mesh / RADIUS_EARTH) - (1 + KM2M * dep1_mesh / RADIUS_EARTH),
        ])
        tri_leg2 = np.transpose([
            np.deg2rad(lon3_mesh - lon1_mesh),
            np.deg2rad(lat3_mesh - lat1_mesh),
            (1 + KM2M * dep3_mesh / RADIUS_EARTH) - (1 + KM2M * dep1_mesh / RADIUS_EARTH),
        ])
        norm_vec = np.cross(tri_leg1, tri_leg2)
        tri_area = np.linalg.norm(norm_vec, axis=1)
        azimuth, elevation, r = cart2sph(norm_vec[:, 0], norm_vec[:, 1], norm_vec[:, 2])
        strike = wrap2360(-np.rad2deg(azimuth))
        dip = 90 - np.rad2deg(elevation)
        dip[dip > 90] = 180.0 - dip[dip > 90]

        # Project steeply dipping meshes
        mesh_list = np.unique(mesh_idx)
        proj_mesh_flag = np.zeros_like(mesh_list)
        for i in mesh_list:
            this_mesh_els = mesh_idx == i
            this_mesh_dip = np.mean(dip[this_mesh_els])
            if this_mesh_dip > 75:
                proj_mesh_flag[i] = 1
                dip_dir = np.mean(np.deg2rad(strike[this_mesh_els] + 90))
                lon1_mesh[this_mesh_els] += np.sin(dip_dir) * np.rad2deg(
                    np.abs(KM2M * dep1_mesh[this_mesh_els] / RADIUS_EARTH)
                )
                lat1_mesh[this_mesh_els] += np.cos(dip_dir) * np.rad2deg(
                    np.abs(KM2M * dep1_mesh[this_mesh_els] / RADIUS_EARTH)
                )
                lon2_mesh[this_mesh_els] += np.sin(dip_dir) * np.rad2deg(
                    np.abs(KM2M * dep2_mesh[this_mesh_els] / RADIUS_EARTH)
                )
                lat2_mesh[this_mesh_els] += np.cos(dip_dir) * np.rad2deg(
                    np.abs(KM2M * dep2_mesh[this_mesh_els] / RADIUS_EARTH)
                )
                lon3_mesh[this_mesh_els] += np.sin(dip_dir) * np.rad2deg(
                    np.abs(KM2M * dep3_mesh[this_mesh_els] / RADIUS_EARTH)
                )
                lat3_mesh[this_mesh_els] += np.cos(dip_dir) * np.rad2deg(
                    np.abs(KM2M * dep3_mesh[this_mesh_els] / RADIUS_EARTH)
                )

        x1_mesh, y1_mesh = wgs84_to_web_mercator(lon1_mesh, lat1_mesh)
        x2_mesh, y2_mesh = wgs84_to_web_mercator(lon2_mesh, lat2_mesh)
        x3_mesh, y3_mesh = wgs84_to_web_mercator(lon3_mesh, lat3_mesh)

        # Store data
        data = {
            "station": station,
            "segment": segment,
            "meshes": meshes,
            "resmag": resmag,
            "x_station": x_station,
            "y_station": y_station,
            "x1_seg": x1_seg,
            "y1_seg": y1_seg,
            "x2_seg": x2_seg,
            "y2_seg": y2_seg,
            "x1_mesh": x1_mesh,
            "y1_mesh": y1_mesh,
            "x2_mesh": x2_mesh,
            "y2_mesh": y2_mesh,
            "x3_mesh": x3_mesh,
            "y3_mesh": y3_mesh,
        }

        if folder_number == 1:
            self.folder_1_data = data
        else:
            self.folder_2_data = data

        # Update visualization
        self._update_layers()

        print(f"Loaded data from {folder_name}")

    @controller.set("load_folder_1")
    def load_folder_1(self):
        """Load data from folder 1"""
        self._load_data(1)

    @controller.set("load_folder_2")
    def load_folder_2(self):
        """Load data from folder 2"""
        self._load_data(2)

    def _update_layers(self):
        """Update DeckGL layers based on loaded data and visibility controls"""
        # TODO: Implement layer creation and updates
        # This will be implemented in the next phase
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
                            with vuetify3.VCard(classes="flex-grow-1", style="min-height: 0; position: relative;"):
                                # DeckGL Map
                                deck_map = deckgl.Deck(
                                    mapbox_api_key=mapbox_access_token if HAS_MAPBOX_TOKEN else "",
                                    style="width: 100%; height: 100%;",
                                    classes="fill-height",
                                )
                                self.ctrl.deck_update = deck_map.update

                                # Initialize map after UI is built
                                self.server.controller.on_server_ready.add(self._initialize_map)

                            # Colorbar area (row 8)
                            with vuetify3.VCard(classes="pa-2 d-flex justify-space-around align-center", height="50", flat=True):
                                # Slip rate colorbar placeholder
                                html.Div(
                                    "Slip rate (mm/yr): -100 ←→ +100",
                                    style="font-size: 0.75rem; color: #666;",
                                )
                                # Residual magnitude colorbar placeholder
                                html.Div(
                                    "Resid. mag. (mm/yr): 0 → 5",
                                    style="font-size: 0.75rem; color: #666;",
                                )
                                # Residual diff colorbar placeholder
                                html.Div(
                                    "Resid. diff. (mm/yr): -5 ←→ +5",
                                    style="font-size: 0.75rem; color: #666;",
                                )
