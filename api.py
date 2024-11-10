from __future__ import annotations
import asyncio
import logging
from typing import Dict, Type

import aiohttp
from pydantic import ValidationError

from schema import *

DEFAULT_SERVER_URL = "https://api.heygen.com"

logger = logging.getLogger(__name__)

class HeyApiException(Exception):
    pass


class HeyStream:
    def __init__(self, api: HeyApi, data: SessionData):
        self._api = api
        self._data = data

    @property
    def ice_servers(self):
        return self._data.ice_servers2

    @property
    def session_id(self):
        return self._data.session_id

    @property
    def sdp(self):
        return self._data.sdp

    async def start(self, sdp: aiortc.RTCSessionDescription):
        await self._api.stream_start(self._data.session_id, sdp)

    async def task(self, text: str):
        await self._api.stream_task(self._data.session_id, text)

    async def close(self):
        await self._api.stream_stop(self._data.session_id)


class HeyApi:
    def __init__(self, api_key: str, limit: int = 1, url: str = DEFAULT_SERVER_URL):
        self._api_key = api_key
        self._limit = limit
        self._url = url
        self._available = asyncio.Semaphore(limit)
        self._streams: Dict[str, HeyStream] = dict()
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Api-Key': self._api_key,
        }
        self._client = aiohttp.ClientSession(headers=headers)

    async def stream_new(self, immediately: bool = True, **kwargs) -> HeyStream:
        if immediately and self._available.locked():
            raise HeyApiException() # TODO: add a description

        await self._available.acquire()

        resp = await self._api_streaming_new(**kwargs)
        if resp is None or resp.data is None:
            raise HeyApiException()

        stream = HeyStream(self, resp.data)
        self._streams[resp.data.session_id] = stream
        return stream

    async def stream_start(self, session_id: str, sdp: aiortc.RTCSessionDescription):
        if session_id not in self._streams:
            raise HeyApiException()

        resp = await self._api_streaming_start(session_id=session_id, sdp=sdp)
        if resp is None:
            raise HeyApiException()

    async def stream_stop(self, session_id: str):
        if session_id not in self._streams:
            raise HeyApiException()

        resp = await self._api_streaming_stop(session_id=session_id)
        if resp is None:
            raise HeyApiException()

        self._streams.pop(session_id)
        self._available.release()

    async def stream_task(self, session_id: str, text: str):
        if session_id not in self._streams:
            raise HeyApiException()

        resp = await self._api_streaming_task(session_id=session_id, text=text)
        if resp is None:
            raise HeyApiException()

    async def close(self):
        # TODO: close opened streams
        if len(self._streams):
            logger.warning("closing API manager while %d streams are open", len(self._streams))

        await self._client.close()

    async def _session_close_all(self):
        resp = await self._api_streaming_list()
        if resp:
            coros = [
                self._api_streaming_stop(session_id=i.session_id)
                for i in resp.data.sessions if i.session_id not in self._streams
            ]

            asyncio.gather(*coros)

    async def _get(self, method: str, response_cls: Type[BaseModel]) -> Optional[BaseModel]:
        url = f"{self._url}/v1/{method}"

        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            return response_cls.model_validate_json(await resp.read())
        except aiohttp.ClientResponseError:
            logger.exception("%s method returned an error", method)
        except ValidationError:
            logger.exception("%s method returned unexpected data", method)
        except Exception:
            logger.exception("%s method failed with unexpected exception", method)

        return None

    async def _post(
            self, method: str, response_cls: Type[BaseModel], data: BaseModel
    ) -> Optional[BaseModel]:
        url = f"{self._url}/v1/{method}"

        try:
            resp = await self._client.post(url, json=data.model_dump())
            resp.raise_for_status()
            return response_cls.model_validate_json(await resp.read())
        except aiohttp.ClientResponseError:
            logger.exception("%s method returned an error", method)
        except ValidationError:
            logger.exception("%s method returned unexpected data", method)
        except Exception:
            logger.exception("%s method failed with unexpected exception", method)

        return None

    async def _api_streaming_new(self, **kwargs) -> Optional[APIStreamingNewResponse]:
        req = APIStreamingNewRequest(**kwargs)
        return await self._post("streaming.new", APIStreamingNewResponse, req)

    async def _api_streaming_start(self, **kwargs) -> Optional[APIStreamingStartResponse]:
        req = APIStreamingStartRequest(**kwargs)
        return await self._post("streaming.start", APIStreamingStartResponse, req)

    async def _api_streaming_stop(self, **kwargs) -> Optional[APIStreamingStopResponse]:
        req = APIStreamingStopRequest(**kwargs)
        return await self._post("streaming.stop", APIStreamingStopResponse, req)

    async def _api_streaming_list(self) -> Optional[APIStreamingListResponse]:
        return await self._get("streaming.list", APIStreamingListResponse)

    async def _api_streaming_task(self, **kwargs) -> Optional[APIStreamingTaskResponse]:
        req = APIStreamingTaskRequest(**kwargs)
        return await self._post("streaming.task", APIStreamingTaskResponse, req)
