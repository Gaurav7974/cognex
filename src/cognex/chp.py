# CHP protocol

import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from .models import StateUnit


class ChannelProtocol:

    def __init__(self):
        self._lock = threading.Lock()
        self.active_channels: Dict[
            str, Dict[str, Any]
        ] = {}
        self.create_visual_projectionions: Dict[
            str, Dict[str, Any]
        ] = {}

    def create_channel(
        self, unit_id: str, source_agent: str, target_agent: str
    ) -> str:
        channel_key = f"ent_{unit_id}_{source_agent}_{target_agent}_{len(self.active_channels)}"

        with self._lock:
            self.active_channels[channel_key] = {
                "unit_id": unit_id,
                "state": "established",
                "agents": [source_agent, target_agent],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "transferred_data": None,
            }

        return channel_key

    def transfer_via_channel(
        self, channel_key: str, unit_data: Dict[str, Any]
    ) -> bool:
        with self._lock:
            if channel_key in self.active_channels:
                entanglement = self.active_channels[channel_key]
                if entanglement["state"] == "established":
                    entanglement["transferred_data"] = unit_data
                    entanglement["state"] = "transferred"
                    return True
        return False

    def get_channel(self, channel_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entanglement = self.active_channels.get(channel_key)
            if entanglement is None:
                return None
            return dict(entanglement)

    def generate_state_view(self, unit: StateUnit) -> Dict[str, Any]:
        projection_key = f"holo_{unit.unit_id}"

        projection = {
            "unit_id": unit.unit_id,
            "what": unit.content,
            "why": unit.rationale,
            "scope": unit.scope,
            "confidence": unit.confidence,
            "tags": unit.tags,
        }

        with self._lock:
            self.create_visual_projectionions[projection_key] = projection
        return projection


    def validate_handoff(self, channel_key: str) -> bool:
        with self._lock:
            if channel_key in self.active_channels:
                entanglement = self.active_channels[channel_key]
                return (
                    entanglement.get("transferred_data") is not None
                    and entanglement["state"] == "transferred"
                )
        return False
