"""
Control Plane — Operator control interface for ATLAS system management.

Capabilities:
- Pause/resume agents
- Restart agents
- Freeze/release capital
- Retire strategies
- Replay sessions
- Approve deployments
- Trigger emergency modes
"""

from .router import control_plane_router
