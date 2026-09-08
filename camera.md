# FaceTime HD camera

On this MacBookPro13,2, restoring production T1 firmware also restored the
camera. It is a USB UVC camera behind iBridge, supported by the installed
kernel's `uvcvideo` driver. No additional camera driver or firmware installation
was needed. This model does not use the PCIe `facetimehd`/`bcwc_pcie` driver
found in some other Macs. See the upstream
[model-specific camera notes](https://github.com/Dunedan/mbp-2016-linux#facetime-hd-camera).

## Verified on 2026-09-08

- MacBookPro13,2, Omarchy 4.0.2, kernel 7.1.9-arch1-2.
- Production iBridge `05ac:8600`, USB configuration 1.
- `/dev/video0`: video capture; `/dev/video1` is the associated secondary node.
- `uvcvideo` exposes MJPEG at 1280×720 and 640×480, up to 30 fps.
- FFmpeg decoded 90 frames at 1280×720 and 30 fps in approximately three seconds,
  returning status 0 with no decoding errors. Frames were discarded immediately;
  no camera images or recordings were saved.
- The owner confirmed the camera works in OBS after the capture test.
- Cold boot and suspend/resume have not yet been tested.

## Use in OBS

Add **Video Capture Device (V4L2)** under Sources, then choose **iBridge: FaceTime
HD Camera**. If manual settings are needed, choose MJPEG, 1280×720 and 30 fps.
The device name may be truncated in the picker. Select the video capture node,
which was `/dev/video0` during this test; numbering can change with other cameras.
Close other camera applications if the device is busy.

## Repeat the capture check

With `v4l2-ctl` and `ffmpeg` installed, run as the logged-in desktop user:

```bash
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --all --list-formats-ext
timeout 20s ffmpeg -hide_banner -nostdin -loglevel info \
  -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 \
  -i /dev/video0 -frames:v 90 -an -f null -
```

The last command activates the camera briefly and discards decoded frames.
Expect `frame=90`, about 30 fps and successful exit. This checks frame delivery
and decoding; use a local preview to assess the picture.

## Persistence

Camera availability depends on the T1 booting production firmware. The existing
[EFI staging and driver setup](driver/README.md) supplies that configuration;
uvcvideo binds automatically when the camera enumerates. No separate camera
startup service was added. If it disappears after a reboot, first check whether
the T1 returned to recovery mode and follow the activation documentation.
