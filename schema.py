from enum import Enum
from typing import List, Literal, Optional, Union

import aiortc
from pydantic import BaseModel


class SessionQuality(str, Enum):
    LOW    = 'low'    # 360p
    MEDIUM = 'medium' # 480p
    HIGH   = 'high'   # 720p


class SessionEncoding(str, Enum):
    H264 = 'H264'
    VP8  = 'VP8'


class Emotion(str, Enum):
    EXCITED     = 'Excited'
    SERIOUS     = 'Serious'
    FRIENDLY    = 'Friendly'
    SOOTHING    = 'Soothing'
    BROADCASTER = 'Broadcaster'


class VoiceSettings(BaseModel):
    voice_id: Optional[str] = None
    rate: Optional[float] = None
    emotion: Optional[Emotion] = None


class ICEServer(BaseModel):
    urls: Union[List[str], str]
    username: Optional[str] = None
    credential: Optional[str] = None
    credentialType: Optional[str] = None


class BaseResponse(BaseModel):
    code: int
    message: str


class APIStreamingNewRequest(BaseModel):
    avatar_id: Optional[str] = None
    disable_idle_timeout: Optional[bool] = None
    knowledge_base: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    quality: SessionQuality = SessionQuality.LOW
    version: Optional[str] = None
    video_encoding: Optional[SessionEncoding] = None
    voice: Optional[VoiceSettings] = None


class SessionData(BaseModel):
    access_token: Optional[str]
    ice_servers: Optional[List[str]]
    ice_servers2: List[ICEServer]
    is_paid: bool
    sdp: aiortc.RTCSessionDescription
    session_duration_limit: int
    session_id: str
    url: Optional[str]


class APIStreamingNewResponse(BaseResponse):
    data: Optional[SessionData] = None


class APIStreamingStartRequest(BaseModel):
    session_id: str
    sdp: aiortc.RTCSessionDescription


class APIStreamingStartResponse(BaseResponse):
    pass


class SessionListEntry(BaseModel):
    session_id: str
    status: str
    created_at: int


class SessionListData(BaseModel):
    sessions: List[SessionListEntry]


class APIStreamingListResponse(BaseResponse):
    data: SessionListData


class APIStreamingStopRequest(BaseModel):
    session_id: str


class APIStreamingStopResponse(BaseResponse):
    data: None


class APIStreamingTaskRequest(BaseModel):
    session_id: str
    text: str
    task_mode: Union[Literal['sync'], Literal['async']] = 'async'
    task_type: Union[Literal['repeat'], Literal['chat']] = 'repeat'


class TaskData(BaseModel):
    task_id: str
    duration_ms: float


class APIStreamingTaskResponse(BaseResponse):
    data: TaskData
