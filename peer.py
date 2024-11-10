from __future__ import annotations
import asyncio
from typing import List, Tuple

import aiortc
import aiortc.contrib.media

class PeerWrapper:
    @staticmethod
    async def create_from_offer(
        ice_servers: List[aiortc.RTCIceServer], sdp: aiortc.RTCSessionDescription, expect_tracks: int = 2
    ) -> Tuple[PeerWrapper, aiortc.RTCSessionDescription]:
        conf = aiortc.RTCConfiguration(iceServers=ice_servers)
        pc = aiortc.RTCPeerConnection(conf)
        wrapper = PeerWrapper(pc, expect_tracks)

        await pc.setRemoteDescription(sdp)
        answ = await pc.createAnswer()
        await pc.setLocalDescription(answ)

        return (wrapper, answ)

    @staticmethod
    async def create_offer(
        ice_servers: List[aiortc.RTCIceServer], tracks: List[aiortc.MediaStreamTrack]
    ) -> Tuple[PeerWrapper, aiortc.RTCSessionDescription]:
        conf = aiortc.RTCConfiguration(iceServers=ice_servers)
        pc = aiortc.RTCPeerConnection(conf)
        wrapper = PeerWrapper(pc, len(tracks))

        for i in tracks:
            await wrapper._track(i)
            pc.addTrack(i)

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        return (wrapper, offer)

    def __init__(self, pc: aiortc.RTCPeerConnection, expect_tracks: int):
        self._pc = pc
        self._pc.add_listener('connectionstatechange', self._conn_state_change)
        self._pc.add_listener('track', self._track)
        self._wait_connected = asyncio.Event()
        self._wait_tracks = asyncio.Event()
        self._expect_tracks = expect_tracks
        self._relay = None
        self._tracks = []

    @property
    def tracks(self):
        return self._tracks

    @property
    def wait_connected(self):
        return self._wait_connected.wait()

    @property
    def wait_tracks(self):
        return self._wait_tracks.wait()

    async def open(self):
        self._pc.setRemoteDescription()

    async def close(self) -> None:
        await self._pc.close()

    def proxify(self) -> List[aiortc.MediaStreamTrack]:
        if self._relay is None:
            self._relay = aiortc.contrib.media.MediaRelay()
        return [self._relay.subscribe(i) for i in self._tracks]

    async def _conn_state_change(self) -> None:
        if self._pc.connectionState == "connected":
            self._wait_connected.set()

    async def _track(self, track: aiortc.MediaStreamTrack) -> None:
        self._tracks.append(track)
        if len(self._tracks) >= self._expect_tracks:
            self._wait_tracks.set()
