from __future__ import annotations
import asyncio
import logging

import aiortc
from aiohttp import web, WSMsgType
from pydantic import ValidationError

from api import HeyApi, HeyStream, HeyApiException
from peer import PeerWrapper
from wsschema import *

API_KEY = "<YOUR API KEY>"

logger = logging.getLogger(__name__)

async def ws_loop():
    await asyncio.sleep(20)

class Handler:
    _api = web.AppKey("heyapi", HeyApi)

    @classmethod
    async def heyapi(cls, app: web.Application):
        app[cls._api] = HeyApi(API_KEY)
        await app[cls._api]._session_close_all()
        yield
        await app[cls._api].close()

    def __init__(self):
        self._routes = [
            web.get('/', self._root),
            web.get('/ws', self._ws),
            web.static('/', './static', append_version=True)
        ]

    @property
    def routes(self):
        return self._routes

    async def _root(self, request: web.Request):
        return web.HTTPMovedPermanently('/index.html')

    async def _task_loop(self, heystream: HeyStream, ws: web.WebSocketResponse):
        async for wsmsg in ws:
            if wsmsg.type == WSMsgType.TEXT:
                match message_type_adapter.validate_json(wsmsg.data):
                    case TextMessage(text=text):
                        await heystream.task(text)
                    case ErrorMessage():
                        raise Exception()
                    case _:
                        raise Exception()
            else:
                raise Exception()

    async def _ws(self, request: web.Request):
        ws = web.WebSocketResponse()
        if not ws.can_prepare(request):
            return ws

        await ws.prepare(request)

        api = request.app[Handler._api]
        heystream = None
        heypeer = None
        peer = None

        try:
            heystream = await api.stream_new()
            heypeer, heyanswer = await PeerWrapper.create_from_offer(heystream.ice_servers, heystream.sdp)
            await heystream.start(heyanswer)
            await asyncio.wait_for(heypeer.wait_tracks, timeout=3)

            peer, offer = await PeerWrapper.create_offer([], heypeer.proxify())
            await ws.send_json(SDPMessage(sdp=offer).model_dump())

            answer = SDPMessage.model_validate_json(await ws.receive_str(timeout=10))
            await peer._pc.setRemoteDescription(answer.sdp)

            waiters = [
                asyncio.create_task(heypeer.wait_connected),
                asyncio.create_task(peer.wait_connected)
            ]
            await asyncio.wait(waiters, timeout=20)
            await self._task_loop(heystream, ws)
        except asyncio.TimeoutError:
            logging.exception("HeyGen peer connection timeout")
        except HeyApiException:
            logging.exception("HeyGen API error")
        except ValidationError:
            logging.exception("Protocol error")
        except Exception:
            logging.exception("Unknown error")
        finally:
            if heystream:
                await heystream.close()
            if heypeer:
                await heypeer.close()
            if peer:
                await peer.close()
            await ws.close()

        return ws

if __name__ == "__main__":
    logging.basicConfig(
        datefmt="%Y-%m-%d %H:%M:%S%z",
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        level=logging.INFO,
    )

    loop = asyncio.get_event_loop()
    # loop.set_debug(True)

    handler = Handler()
    app = web.Application()
    app.add_routes(handler.routes)
    app.cleanup_ctx.append(Handler.heyapi)

    web.run_app(app, loop=loop)