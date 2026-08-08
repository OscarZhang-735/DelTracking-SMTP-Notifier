import asyncio
import os

import pytest

from app.integrations.nextsls import NextSlsClient


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_NEXTSLS_TEST") != "1",
    reason="set RUN_LIVE_NEXTSLS_TEST=1 to call the real provider",
)
def test_real_tracking_number_returns_a_shipment_with_traces() -> None:
    app_id = os.environ["TRACKING_APP_ID"]
    tracking_number = os.getenv("NEXTSLS_TEST_NUMBER", "1024658760")

    async def scenario() -> None:
        async with NextSlsClient(app_id) as client:
            response = await client.track(tracking_number)

        assert response.shipment.client_reference
        assert len(response.shipment.traces) >= 1

    asyncio.run(scenario())
