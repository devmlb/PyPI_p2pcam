from typing import Iterable
from p2pcam import LanDevice
from p2pcam import LanScanner
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import time
import os


def format_devices(devices: Iterable[LanDevice]) -> str:
    lines = []
    for device in devices:
        state = "online" if device.online else f"status={device.status}"
        lines.append(
            f"{device.device_id} type={device.device_type} hkid={device.hkid} "
            f"channels={device.channel_count} audio={device.audio_type} {state}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Discover HeKai LAN devices")

    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument(
        "--video",
        action="store_true",
        help="Start video stream on first discovered camera",
    )
    parser.add_argument(
        "--outdir", default="frames", help="Directory to save video frames"
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Maximum number of frames to capture (0 = unlimited)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start an HTTP MJPEG server to expose the stream",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for the HTTP MJPEG server (default: 8080)",
    )
    parser.add_argument(
        "--vertical-flip",
        action="store_true",
        help="Vertically flip the video stream",
    )
    parser.add_argument(
        "--horizontal-flip",
        action="store_true",
        help="Horizontally flip the video stream",
    )
    parser.add_argument(
        "--add-timestamp",
        action="store_true",
        help="Add date related text to the video stream",
    )

    args = parser.parse_args()

    scanner = LanScanner(encoding=args.encoding)
    found = scanner.refresh(timeout=args.timeout)

    print("Found devices:")
    print(format_devices(found))

    if args.video and found:
        from p2pcam import LanVideoClient

        # The IP address is stored in the ip attribute
        target = found[0]
        ip = target.ip or target.device_id.split(":")[0]
        print(f"\nStarting video stream from {ip} (HKID: {target.hkid})...")

        server = None
        if args.serve:
            from p2pcam import MJPEGServer

            server = MJPEGServer(port=args.port)
            server.start()
        else:
            os.makedirs(args.outdir, exist_ok=True)

        count = 0
        try:
            with LanVideoClient(camera_ip=ip, hkid=target.hkid) as client:
                for raw_frame in client.stream(timeout=10.0):
                    count += 1

                    try:
                        input_frame = Image.open(BytesIO(raw_frame))
                        output_frame = BytesIO()
                        # Image flips
                        if args.vertical_flip:
                            input_frame = input_frame.transpose(Image.FLIP_TOP_BOTTOM)
                        if args.horizontal_flip:
                            input_frame = input_frame.transpose(Image.FLIP_LEFT_RIGHT)
                        # Timestamp
                        if args.add_timestamp:
                            draw = ImageDraw.Draw(input_frame)
                            try:
                                font = ImageFont.truetype("arial.ttf", 15)
                            except:
                                font = ImageFont.load_default()
                            draw.text(
                                (10, 10),
                                time.strftime("%Y-%m-%d  %H:%M:%S"),
                                font=font,
                                fill=(255, 255, 255),
                                stroke_width=1,
                                stroke_fill=(0, 0, 0),
                            )
                        input_frame.save(output_frame, format="JPEG")
                        frame = output_frame.getvalue()

                        if server:
                            server.update_frame(frame)
                            if count % 30 == 0:
                                print(f"Streamed {count} frames...")
                        else:
                            path = os.path.join(args.outdir, f"frame_{count:04d}.jpg")
                            with open(path, "wb") as f:
                                f.write(frame)
                            print(
                                f"Captured frame {count} to {path} ({len(frame)} bytes)"
                            )

                        if args.max_frames > 0 and count >= args.max_frames:
                            break
                    except:
                        # Simply ignore the frame as I observed that some frames may be corrupted
                        continue

        except KeyboardInterrupt:
            print("\nStreaming stopped by user.")
        finally:
            if server:
                server.stop()

        if not server:
            print(f"Captured {count} frames in total.")
