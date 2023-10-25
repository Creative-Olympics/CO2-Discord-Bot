import logging
import sys
from typing import Optional

import aiohttp
from firebase_admin.credentials import Certificate


class RemoteConfigClient:
    """Firebase Remote Config REST API access"""

    def __init__(self, credentials: Certificate):
        self.credentials = credentials
        if self.credentials.project_id is None:
            raise ValueError("Project ID not found in credentials")
        self.logger = logging.getLogger("cobot.rc_rest_api")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.StreamHandler(sys.stdout))
        self.rc_url: str = f"https://firebaseremoteconfig.googleapis.com/v1/projects/{self.credentials.project_id}/remoteConfig"
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def access_token(self) -> str:
        "Get the current API access token"
        access_token_info = self.credentials.get_access_token()
        return access_token_info.access_token

    @property
    def headers(self):
        "Get the headers for the API requests"
        return {
            "Authorization": "Bearer " + self.access_token,
        }

    @property
    def session(self):
        "get a valid aiohttp client session"
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def get(self):
        "Get the current Remote Config"
        self.logger.debug("Getting Remote Config")
        async with self.session.get(self.rc_url, headers=self.headers) as resp:
            if resp.status == 200:
                return await resp.json()
            self.logger.error("Error getting Remote Config: %s", resp.status)
        return None
