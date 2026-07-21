# P2PCam

Classes to retrieve camera images from cameras using the p2p protocol

First of all i just wrote it to work as a class, the original connection and retrieval process has been made by [Jheyman](https://github.com/jheyman/) in his [videosurveillance script](https://github.com/jheyman/videosurveillance/).
I rewrote it to run as a class instead of an application.

So i had this [chinese camera](https://nl.aliexpress.com/item/Phone-monitor-P2P-Free-DDNS-Ontop-RT8633-HD-1-4-CMOS-1-0MP-Network-IP-Camera/990524792.html) laying around, it had this feature that you could access it from outside your home without the need for port forwarding. However after a couple of years this brand dissappeared and with it their services so i couldn't connect to it outside of my own network using [this app](https://play.google.com/store/apps/details?id=x.p2p.cam).

Which made owning this camera quite useless. But i had since gotten into Home Asssistant and got the idea to get it working in there since my instance ran locally so it should be able to access the camera.

## Quick start

You can use the cli.py script to quickly test your camera.

```bash
# Detect cameras on your local network
python3 cli.py

# Detect a camera on your network, connect to it and save 10 JPEG frames in the frames folder
python3 cli.py --video --max-frames 10 --outdir frames/

# Detect a camera on your network, connect to it and start an HTTP MJPEG server on port 8080
python3 cli.py --video --serve --port 8080

# If you want to use image transformations first install pillow
pip install pillow
# Then you can append --vertical-flip, --horizontal-flip or --add-timestamp to any command
```

## API

### LanScanner

#### `refresh(timeout: float = 3.0) -> list[LanDevice]`

Broadcasts a LAN refresh packet, waits for camera responses, and returns the discovered devices sorted by device ID and HKID.

### LanVideoClient

#### `stream(timeout: float = 60.0) -> Iterator[bytes]`

Opens the UDP session, performs the full camera handshake, and yields complete JPEG frames as they become available.

#### `close() -> None`

Stops the stream and closes the UDP socket. Call this when you want to end the session without waiting for the generator to finish.

### MJPEGServer

#### `update_frame(frame: bytes) -> None`

Replaces the currently broadcast frame and notifies all connected HTTP clients waiting on the next image.

#### `start() -> None`

Starts the threaded HTTP server and exposes the MJPEG stream on `/stream`.

#### `stop() -> None`

Stops the HTTP server cleanly and closes its socket.


