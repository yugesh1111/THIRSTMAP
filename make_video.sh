#!/usr/bin/env bash
# Record the captioned demo walkthrough and encode it: MP4 for the submission, a short GIF teaser for the README.
set -euo pipefail
cd "$(dirname "$0")"
node make_video.js docs/demo/index.html docs/video
ffmpeg -y -loglevel error -i docs/video/thirstmap_demo.webm -c:v libx264 -preset slow -crf 27 -pix_fmt yuv420p \
       -movflags +faststart docs/video/thirstmap_demo.mp4
# teaser: the twin moment (pair figure), 12 s, 640 px, 8 fps
ffmpeg -y -loglevel error -ss 44 -t 12 -i docs/video/thirstmap_demo.webm \
       -vf "fps=8,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer" \
       docs/video/teaser.gif
rm -f docs/video/thirstmap_demo.webm
ls -la docs/video
