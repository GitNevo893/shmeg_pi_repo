#!/usr/bin/env python3
#Raspberry Pi WebRTC peer (offerer).
#This script keeps signaling simple (WebSocket JSON) and focuses on reliable 2-way audio behavior with aiortc 1.14.0.

import asyncio
import json

import websockets
from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from aiortc.sdp import candidate_from_sdp

SIGNALING_URL = "wss://shmeg1repo.onrender.com"
AUDIO_DEVICE = "sysdefault:CARD=Device"

# STUN/TURN config for NAT traversal.
config = RTCConfiguration(
    iceServers=[
        RTCIceServer(urls="stun:stun.l.google.com:19302"),
        RTCIceServer(
            urls="turn:openrelay.metered.ca:443?transport=tcp",
            username="openrelayproject",
            credential="openrelayproject",
        ),
    ]
)

pc = RTCPeerConnection(configuration=config)

# Audio input (Pi -> browser): use a stable ALSA device name.
# If the USB/input device is missing, log and continue without crashing.
player = None
try:
    player = MediaPlayer(AUDIO_DEVICE, format="alsa")
    if player.audio is not None:
        print("Audio source ready:", player.audio)
        pc.addTrack(player.audio)
    else:
        print("Audio source opened but no audio track was provided by ALSA")
except Exception as exc:
    print(f"Audio input unavailable on {AUDIO_DEVICE}: {exc}")

# Audio output (browser -> Pi): create recorder once.
# If output hardware is missing, keep the app running and just skip playback.
recorder = None
try:
    recorder = MediaRecorder(AUDIO_DEVICE, format="alsa")
    print(f"Audio output prepared on {AUDIO_DEVICE}")
except Exception as exc:
    print(f"Audio output unavailable on {AUDIO_DEVICE}: {exc}")

recording_started = False


@pc.on("track")
async def on_track(track):
    """Start playback once when the first remote audio track arrives."""
    global recording_started

    if track.kind != "audio":
        return

    print("🎵 Audio track received from browser")

    # Start recorder only once (prevents duplicate starts / state errors).
    if recording_started:
        print("Recorder already started; ignoring duplicate audio track")
        return

    if recorder is None:
        print("Recorder not available; received audio will not be played")
        return

    recording_started = True
    recorder.addTrack(track)
    await recorder.start()
    print("Audio playback started")


# Keep the required test data channel for debugging/health checks.
channel = pc.createDataChannel("test")


@channel.on("open")
def on_open():
    print("DataChannel open!!!")
    channel.send("Hello from Raspberry Pi")


@channel.on("message")
def on_message(message):
    print("From browser:", message)


@pc.on("connectionstatechange")
async def on_connectionstatechange():
    print("Connection state:", pc.connectionState)


@pc.on("iceconnectionstatechange")
async def on_iceconnectionstatechange():
    print("ICE connection state:", pc.iceConnectionState)


async def run():
    async with websockets.connect(SIGNALING_URL) as ws:
        print("Connected to signaling server")

        # ICE sender lives inside run() so it has access to this ws connection.
        @pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate is None:
                return

            sdp_text = candidate.to_sdp()
            print(f"Sending ICE candidate: {sdp_text[:60]}...")
            await ws.send(
                json.dumps(
                    {
                        "type": "ice",
                        "candidate": {
                            "candidate": sdp_text,
                            "sdpMid": candidate.sdpMid,
                            "sdpMLineIndex": candidate.sdpMLineIndex,
                        },
                    }
                )
            )

        # Pi stays as OFFERER: createOffer -> setLocalDescription -> send offer.
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        await ws.send(
            json.dumps(
                {
                    "type": pc.localDescription.type,
                    "sdp": pc.localDescription.sdp,
                }
            )
        )
        print("Sent WebRTC offer")

        # Main signaling loop.
        async for message in ws:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "answer":
                print("Received WebRTC answer")
                await pc.setRemoteDescription(
                    RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                )

            elif msg_type == "ice":
                cand = data.get("candidate", {})
                cand_sdp = cand.get("candidate")
                if not cand_sdp:
                    print("Received malformed ICE payload (missing candidate string)")
                    continue

                print(f"Received ICE candidate: {cand_sdp[:60]}...")
                rtc_candidate = candidate_from_sdp(cand_sdp)
                rtc_candidate.sdpMid = cand.get("sdpMid")
                rtc_candidate.sdpMLineIndex = cand.get("sdpMLineIndex")
                await pc.addIceCandidate(rtc_candidate)


asyncio.run(run())
