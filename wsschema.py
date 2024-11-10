from typing import Annotated, List, Literal, Optional, Union

import aiortc
from pydantic import BaseModel, Field, TypeAdapter


class SDPMessage(BaseModel):
    type: Literal['sdp'] = 'sdp'
    sdp: aiortc.RTCSessionDescription
    ice_servers: Optional[List[aiortc.RTCIceServer]] = None


class TextMessage(BaseModel):
    type: Literal['text'] = 'text'
    text: str


class ErrorMessage(BaseModel):
    type: Literal['error'] = 'error'
    message: str


Message = Annotated[Union[SDPMessage, TextMessage, ErrorMessage], Field(discriminator='type')]
message_type_adapter = TypeAdapter(Message)
