from atlas.dashboard.router import router as dashboard_router
from atlas.dashboard.control_plane.router import control_plane_router
from atlas.dashboard.system_visualization.router import system_viz_router

__all__ = ["dashboard_router", "control_plane_router", "system_viz_router"]
