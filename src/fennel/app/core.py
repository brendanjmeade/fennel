import os
import numpy as np
import pandas as pd
from pathlib import Path

from trame.app import TrameApp
from trame.decorators import change, controller
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3, html

# Import pydeck and trame-deckgl
import pydeck as pdk
from trame_deckgl.widgets import deckgl


def _load_mapbox_token():
    token = os.getenv("FENNEL_MAP_BOX_TOKEN")
    if token:
        return token
    # Fallback: read from a local .env if present
    for parent in Path(__file__).resolve().parents:
        env_file = parent / ".env"
        if env_file.is_file():
            for line in env_file.read_text().splitlines():
                if line.strip().startswith("FENNEL_MAP_BOX_TOKEN="):
                    return line.split("=", 1)[1].strip()
    return None


mapbox_access_token = _load_mapbox_token()
HAS_MAPBOX_TOKEN = bool(mapbox_access_token)


# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------

VELOCITY_SCALE = 1000
KM2M = 1.0e3
RADIUS_EARTH = 6371000

# Per-layer colors (RGBA) and per-folder line widths, mirroring the legacy viewer
TYPE_COLORS = {
    1: {
        "obs": [0, 0, 205, 255],
        "mod": [205, 0, 0, 200],
        "res": [205, 0, 205, 200],
        "rot": [0, 205, 0, 200],
        "seg": [0, 205, 205, 200],
        "tde": [205, 133, 0, 200],
        "str": [0, 128, 128, 200],
        "mog": [128, 128, 128, 200],
        "loc": [0, 0, 0, 220],
    },
    2: {
        "obs": [0, 0, 205, 255],
        "mod": [205, 0, 0, 200],
        "res": [205, 0, 205, 200],
        "rot": [0, 205, 0, 200],
        "seg": [0, 205, 205, 200],
        "tde": [205, 133, 0, 200],
        "str": [0, 102, 102, 200],
        "mog": [102, 102, 102, 200],
        "loc": [0, 0, 0, 220],
    },
}

LINE_WIDTHS = {1: 1, 2: 2}


# ---------------------------------------------------------
# Coordinate transformation utilities
# ---------------------------------------------------------

def wgs84_to_web_mercator(lon, lat):
    """Converts decimal (longitude, latitude) to Web Mercator (x, y)"""
    EARTH_RADIUS = 6378137.0  # Earth's radius (m)
    x = EARTH_RADIUS * np.deg2rad(lon)
    y = EARTH_RADIUS * np.log(np.tan((np.pi / 4.0 + np.deg2rad(lat) / 2.0)))
    return x, y


def web_mercator_to_wgs84(x, y):
    """Converts Web Mercator (x, y) to WGS84 (longitude, latitude)"""
    EARTH_RADIUS = 6378137.0  # Earth's radius (m)
    lon = np.rad2deg(x / EARTH_RADIUS)
    lat = np.rad2deg(2.0 * np.arctan(np.exp(y / EARTH_RADIUS)) - np.pi / 2.0)
    return lon, lat


# TODO: this may not be needed
def normalize_longitude_difference(start_lon, end_lon):
    """
    Normalize end longitude to be in the same 360-degree range as start longitude.
    This prevents vectors from wrapping around the world when crossing the date line.
    """
    # Calculate the difference
    diff = end_lon - start_lon

    # If the difference is > 180, we've wrapped around (going the long way)
    # Adjust by 360 to go the short way
    diff = np.where(diff > 180, diff - 360, diff)
    diff = np.where(diff < -180, diff + 360, diff)

    # Return the normalized end longitude
    return start_lon + diff


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

        # One-time registration guard
        self._ready_registered = False

        # build ui
        self._build_ui()

    def _initialize_map(self, **kwargs):
        """Initialize the map with default view"""
        self.ctrl.deck_update(self._build_deck([]))

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
        layers = []

        # Process folder 1 data
        if self.folder_1_data is not None:
            layers.extend(self._create_layers_for_folder(1, self.folder_1_data))

        # Process folder 2 data
        if self.folder_2_data is not None:
            layers.extend(self._create_layers_for_folder(2, self.folder_2_data))

        self.ctrl.deck_update(self._build_deck(layers))

    def _build_deck(self, layers):
        """Construct a Deck instance with current map settings and provided layers."""
        return pdk.Deck(
            map_provider="mapbox" if HAS_MAPBOX_TOKEN else "carto",
            map_style="mapbox://styles/mapbox/light-v9" if HAS_MAPBOX_TOKEN else pdk.map_styles.LIGHT,
            initial_view_state=pdk.ViewState(
                latitude=self.state.map_latitude,
                longitude=self.state.map_longitude,
                zoom=self.state.map_zoom,
                pitch=self.state.map_pitch,
                bearing=self.state.map_bearing,
            ),
            layers=layers,
        )

    def _create_layers_for_folder(self, folder_number, data):
        """Create DeckGL layers for a specific folder's data"""
        layers = []
        station = data["station"]
        x_station = data["x_station"]
        y_station = data["y_station"]

        # Get visibility state
        vis_keys = (
            "show_locs",
            "show_obs",
            "show_mod",
            "show_res",
            "show_rot",
            "show_seg",
            "show_tri",
            "show_str",
            "show_mog",
        )
        vis = {k: self.state[f"{k}_{folder_number}"] for k in vis_keys}

        colors = TYPE_COLORS[folder_number]
        base_width = LINE_WIDTHS[folder_number]

        def add_velocity_layer(layer_id_prefix, east_component, north_component, base_color, line_width):
            """Add base and -360 shifted velocity line layers using the same color."""
            velocity_scale = self.state.velocity_scale * VELOCITY_SCALE
            x_end = x_station + velocity_scale * east_component
            y_end = y_station + velocity_scale * north_component
            end_lon, end_lat = web_mercator_to_wgs84(x_end, y_end)
            end_lon = normalize_longitude_difference(station.lon.values, end_lon)

            base_df = pd.DataFrame({
                "start_lon": station.lon.values,
                "start_lat": station.lat.values,
                "end_lon": end_lon,
                "end_lat": end_lat,
            })

            shift_df = pd.DataFrame({
                "start_lon": station.lon.values - 360,
                "start_lat": station.lat.values,
                "end_lon": end_lon - 360,
                "end_lat": end_lat,
            })

            layers.append(pdk.Layer(
                "LineLayer",
                data=base_df,
                get_source_position=["start_lon", "start_lat"],
                get_target_position=["end_lon", "end_lat"],
                get_color=base_color,
                get_width=line_width,
                width_min_pixels=1,
                id=f"{layer_id_prefix}_{folder_number}",
            ))

            layers.append(pdk.Layer(
                "LineLayer",
                data=shift_df,
                get_source_position=["start_lon", "start_lat"],
                get_target_position=["end_lon", "end_lat"],
                get_color=base_color,
                get_width=line_width,
                width_min_pixels=1,
                id=f"{layer_id_prefix}_shift_{folder_number}",
            ))

        # Station locations (only when explicitly requested)
        if self.state[f"show_locs_{folder_number}"]:
            station_df = pd.DataFrame({
                "lon": station.lon.values,
                "lat": station.lat.values,
                "name": station.name.values,
            })

            layers.append(pdk.Layer(
                "ScatterplotLayer",
                data=station_df,
                get_position=["lon", "lat"],
                get_fill_color=colors["loc"],
                get_radius=3000,
                radius_min_pixels=2,
                radius_max_pixels=5,
                pickable=True,
                id=f"stations_{folder_number}",
            ))

        # Observed velocities
        if vis["show_obs"]:
            # Velocity data is in mm/yr, VELOCITY_SCALE converts to m/yr; Web Mercator uses meters
            add_velocity_layer(
                "obs_vel",
                station.east_vel.values,
                station.north_vel.values,
                colors["obs"],
                base_width,
            )

        # Modeled velocities
        if vis["show_mod"]:
            add_velocity_layer(
                "mod_vel",
                station.model_east_vel.values,
                station.model_north_vel.values,
                colors["mod"],
                base_width,
            )

        # Residual velocities
        if vis["show_res"]:
            add_velocity_layer(
                "res_vel",
                station.model_east_vel_residual.values,
                station.model_north_vel_residual.values,
                colors["res"],
                base_width,
            )

        # Rotation velocities
        if vis["show_rot"]:
            add_velocity_layer(
                "rot_vel",
                station.model_east_vel_rotation.values,
                station.model_north_vel_rotation.values,
                colors["rot"],
                base_width,
            )

        # Segment elastic velocities
        if vis["show_seg"]:
            add_velocity_layer(
                "seg_vel",
                station.model_east_elastic_segment.values,
                station.model_north_elastic_segment.values,
                colors["seg"],
                base_width,
            )

        # TDE velocities
        if vis["show_tri"]:
            add_velocity_layer(
                "tde_vel",
                station.model_east_vel_tde.values,
                station.model_north_vel_tde.values,
                colors["tde"],
                base_width,
            )

        # Strain rate velocities
        if vis["show_str"]:
            add_velocity_layer(
                "str_vel",
                station.model_east_vel_block_strain_rate.values,
                station.model_north_vel_block_strain_rate.values,
                colors["str"],
                base_width,
            )

        # Mogi velocities
        if vis["show_mog"]:
            add_velocity_layer(
                "mog_vel",
                station.model_east_vel_mogi.values,
                station.model_north_vel_mogi.values,
                colors["mog"],
                base_width,
            )

        # Fault segments
        show_seg_color = self.state[f"show_seg_color_{folder_number}"]
        if show_seg_color:
            segment = data["segment"]
            seg_slip_type = self.state[f"seg_slip_type_{folder_number}"]

            # Get slip values based on type (strike-slip or dip-slip)
            if seg_slip_type == "ss":
                slip_values = segment.ss_rate.values if "ss_rate" in segment.columns else np.zeros(len(segment))
            else:  # ds
                slip_values = segment.ds_rate.values if "ds_rate" in segment.columns else np.zeros(len(segment))

            # Create segment lines with color based on slip rate
            seg_lines_df = pd.DataFrame({
                "start_lon": segment.lon1.values,
                "start_lat": segment.lat1.values,
                "end_lon": segment.lon2.values,
                "end_lat": segment.lat2.values,
                "slip_rate": slip_values,
            })

            # Normalize slip rate for coloring (-100 to 100 mm/yr)
            slip_normalized = np.clip(slip_values / 100.0, -1.0, 1.0)

            # Color map: blue (negative) -> white (zero) -> red (positive)
            def slip_to_color(slip_norm):
                if slip_norm < 0:
                    # Blue to white
                    t = (slip_norm + 1.0)  # 0 to 1
                    return [int(255 * t), int(255 * t), 255, 200]
                else:
                    # White to red
                    t = slip_norm  # 0 to 1
                    return [255, int(255 * (1 - t)), int(255 * (1 - t)), 200]

            colors_array = [slip_to_color(s) for s in slip_normalized]
            seg_lines_df["color"] = colors_array

            layers.append(pdk.Layer(
                "LineLayer",
                data=seg_lines_df,
                get_source_position=["start_lon", "start_lat"],
                get_target_position=["end_lon", "end_lat"],
                get_color="color",
                get_width=3,
                width_min_pixels=2,
                pickable=True,
                id=f"segments_{folder_number}",
            ))

        return layers

    @change("velocity_scale")
    def on_velocity_scale_change(self, velocity_scale, **kwargs):
        """Update velocity vector scaling"""
        self._update_layers()

    @change(
        "show_locs_1", "show_obs_1", "show_mod_1", "show_res_1", "show_rot_1",
        "show_seg_1", "show_tri_1", "show_str_1", "show_mog_1",
        "show_seg_color_1", "seg_slip_type_1",
        "show_locs_2", "show_obs_2", "show_mod_2", "show_res_2", "show_rot_2",
        "show_seg_2", "show_tri_2", "show_str_2", "show_mog_2",
        "show_seg_color_2", "seg_slip_type_2",
    )
    def on_visibility_change(self, **kwargs):
        """Update visualization when visibility controls change"""
        self._update_layers()

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
                                if not self._ready_registered:
                                    self.server.controller.on_server_ready.add(self._initialize_map)
                                    self._ready_registered = True

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
