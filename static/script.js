var badgeStatus = "unknown";
var connButtonAction = "connect";
var pc = null;
var socket = null;

const buttonConnect = document.getElementById('button-connect');
buttonConnect.addEventListener("click", (event) => {
    if (connButtonAction == "connect")
        wsConnect();
    else {
        socket.close();
        pc.close();
    }
});

const messageBox = document.getElementById('message-box');
messageBox.addEventListener("submit", (event) => {
    event.preventDefault();
    message = messageBox.elements['message-text'].value;
    messageBox.reset();

    if (socket) {
        socket.send(JSON.stringify({type: 'text', text: message}));
    }
});

const videoElement = document.getElementById('remote-video');

function setBadgeStatus(status) {
    const badge = document.getElementById("badge-status");
    const statuses = {
        "connected": ["Connected", "text-bg-success"],
        "connecting": ["Connecting", "text-bg-warning"],
        "disconnected": ["Disconnected", "text-bg-danger"],
        "unknown": ["Unknown", "text-bg-light"],
    };

    if (statuses.hasOwnProperty(status)) {
        badgeStatus = status;
        var newStatus = statuses[status];
        badge.textContent = newStatus[0];
        badge.className = badge.className.replace(/text-bg-\S+/, newStatus[1]);
    }
}

function setConnButtonAction(action) {
    const button = document.getElementById("button-connect");
    const actions = {
        "connect": ["Connect", "btn-primary"],
        "disconnect": ["Disconnect", "btn-danger"],
    };

    if (actions.hasOwnProperty(action)) {
        connButtonAction = action;
        var newAction = actions[action];
        button.textContent = newAction[0];
        button.className = button.className.replace(/btn-\S+/, newAction[1]);
    }
}

function pcCreate(sdp) {
    pc = new RTCPeerConnection({iceServers: [{urls: "stun:stun.l.google.com:19302"}]});

    pc.addEventListener("connectionstatechange", () => {
        console.log("RTC: new connection state ", pc.connectionState);
        if (pc.connectionState == "connected") {
            setBadgeStatus("connected");
        }
    });

    pc.addEventListener("icecandidate", (e) => {
        console.log("RTC: new ICE candidate ", e.candidate);
    });

    pc.addEventListener("icecandidateerror", (e) => {
        console.log("RTC: ICE candidate error ", e);
    });

    pc.addEventListener("iceconnectionstatechange", () => {
        console.log("RTC: new ICE connection state ", pc.iceConnectionState);
    });

    pc.addEventListener("icegatheringstatechange", () => {
        console.log("RTC: new ICE gathering state ", pc.iceGatheringState);
        if (pc.iceGatheringState == "complete") {
            socket.send(JSON.stringify({type: "sdp", sdp: pc.localDescription}));
        }
    });

    pc.addEventListener("negotiationneeded", () => {
        console.log("RTC: negotiation needed")
    })

    pc.addEventListener("signalingstatechange", () => {
        console.log("RTC: new signaling state ", pc.signalingState);
        if (pc.signalingState == "closed") {
            pc.close();
        }
    });

    pc.addEventListener("track", (e) => {
        console.log("RTC: new track ", e.track.kind);
        if (e.track.kind == "video") {
            videoElement.srcObject = e.streams[0];
            videoElement.play();
        }
    });

    pc.setRemoteDescription(sdp).then(async function() {
        answ = await pc.createAnswer();
        pc.setLocalDescription(answ);
    });
}

function wsConnect() {
    socket = new WebSocket("ws://localhost:8080/ws");

    setBadgeStatus("connecting");
    setConnButtonAction("disconnect");

    socket.addEventListener("close", (event) => {
        console.log("WebSocket connection closed");
        setBadgeStatus("disconnected");
        setConnButtonAction("connect");
        socket = null;
    });

    socket.addEventListener("error", (event) => {
        console.log("WebSocket error: ", event.data);
        socket.close();
    });

    socket.addEventListener("message", wsHandleMsg);
}

function wsHandleMsgOffer(sdp) {
    pcCreate(sdp);
}

function wsHandleMsg(event) {
    console.log("Message from server: ", event.data);

    try {
        msg = JSON.parse(event.data);
        switch (msg.type) {
            case "sdp":
                wsHandleMsgOffer(msg.sdp);
                break;
        }
    } catch (e) {
        console.log(e);
    }
}