import logging
import os
import httpx
from typing import Any

log = logging.getLogger(__name__)

TOKEN_URL = "https://www.fflogs.com/oauth/token"
API_URL = "https://www.fflogs.com/api/v2/client"


class FFLogsClient:
    def __init__(self):
        self._http: httpx.AsyncClient | None = None
        self._token: str = ""

    async def __aenter__(self):
        self._http = httpx.AsyncClient(timeout=30)
        await self._authenticate()
        return self

    async def __aexit__(self, *_):
        if self._http:
            await self._http.aclose()

    async def _authenticate(self):
        log.info("fflogs: authenticating")
        resp = await self._http.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(os.environ["FFLOGS_CLIENT_ID"], os.environ["FFLOGS_CLIENT_SECRET"]),
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        log.info("fflogs: authenticated OK")

    async def query(self, query: str, variables: dict[str, Any] | None = None) -> dict:
        log.debug("fflogs: query vars=%s", variables)
        resp = await self._http.post(
            API_URL,
            json={"query": query, "variables": variables or {}},
            headers={"Authorization": f"Bearer {self._token}"},
        )
        resp.raise_for_status()
        body = resp.json()
        if errors := body.get("errors"):
            raise RuntimeError(f"FFLogs GraphQL error: {errors[0]['message']}")
        return body["data"]

    async def get_fights(self, report_code: str) -> list[dict]:
        data = await self.query(
            """
            query($code: String!) {
                reportData {
                    report(code: $code) {
                        fights {
                            id name startTime endTime kill fightPercentage
                        }
                    }
                }
            }
            """,
            {"code": report_code},
        )
        return data["reportData"]["report"]["fights"]

    async def get_actors(self, report_code: str) -> list[dict]:
        data = await self.query(
            """
            query($code: String!) {
                reportData {
                    report(code: $code) {
                        masterData {
                            actors(type: "Player") { id name type subType }
                        }
                    }
                }
            }
            """,
            {"code": report_code},
        )
        return data["reportData"]["report"]["masterData"]["actors"]

    async def get_events(self, report_code: str, fight_id: int, data_type: str) -> list[dict]:
        log.info("fflogs: get_events type=%s", data_type)
        # TODO: handle pagination via nextPageTimestamp
        data = await self.query(
            """
            query($code: String!, $fightIDs: [Int], $dataType: EventDataType!) {
                reportData {
                    report(code: $code) {
                        events(fightIDs: $fightIDs, dataType: $dataType, limit: 10000) {
                            data
                            nextPageTimestamp
                        }
                    }
                }
            }
            """,
            {"code": report_code, "fightIDs": [fight_id], "dataType": data_type},
        )
        return data["reportData"]["report"]["events"]["data"]
