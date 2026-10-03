"""Plugin marker for Orac Gateway discovery."""
# Author: Clive Bostock
# Date: 28-Sep-2026
# Description: Provides the on-demand marker required by the plugin manifest.


class OracGatewayPlugin:
    """Identify the gateway while its work remains in the managed service."""

    def handle(self, _request: object) -> dict[str, str]:
        """Reject direct dialogue execution in favour of the HTTP service."""
        return {
            "status": "unsupported",
            "message": "Orac Gateway is available through its managed HTTP service.",
        }
