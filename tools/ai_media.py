"""AI media generation tools — TTS, image gen, video gen, audio processing."""

import subprocess, os, json, time, hashlib, base64, uuid

TOOL_DEFS = [
    {"type": "function", "function": {"name": "tts_generate", "description": "Convert text to speech audio file. Returns audio file path for playback.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to convert to speech"}, "voice": {"type": "string", "description": "Voice name (e.g. 'en-US-AriaNeural', 'id-ID-ArdiNeural'). Default: auto-detect language"}, "rate": {"type": "string", "description": "Speech rate (e.g. '+0%', '-20%', '+50%')"}, "output": {"type": "string", "description": "Output audio file path (.mp3)"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "tts_voices", "description": "List available TTS voices for a language.", "parameters": {"type": "object", "properties": {"language": {"type": "string", "description": "Language code (e.g. 'en', 'id', 'ja'). Omit for all voices"}}, "required": []}}},
    {"type": "function", "function": {"name": "image_generate", "description": "Generate an image from a text prompt using AI. Returns image file path.", "parameters": {"type": "object", "properties": {"prompt": {"type": "string", "description": "Image description/prompt"}, "width": {"type": "integer", "description": "Image width (default 512)"}, "height": {"type": "integer", "description": "Image height (default 512)"}, "style": {"type": "string", "enum": ["realistic", "anime", "cartoon", "sketch", "pixel", "3d", "oil-painting", "watercolor"], "description": "Art style"}, "output": {"type": "string", "description": "Output image path"}}, "required": ["prompt"]}}},
    {"type": "function", "function": {"name": "image_edit", "description": "Edit an existing image — crop, resize, rotate, apply filters, add text overlay.", "parameters": {"type": "object", "properties": {"input": {"type": "string", "description": "Input image path"}, "output": {"type": "string", "description": "Output image path"}, "filter": {"type": "string", "enum": ["none", "grayscale", "sepia", "blur", "sharpen", "invert", "brightness", "contrast", "vintage", "pixelate"], "description": "Filter to apply"}, "text_overlay": {"type": "string", "description": "Text to overlay on image"}, "text_position": {"type": "string", "enum": ["top", "bottom", "center"], "description": "Text position"}, "rotate": {"type": "integer", "description": "Rotate degrees (0, 90, 180, 270)"}, "brightness": {"type": "number", "description": "Brightness factor (0.5-2.0)"}}, "required": ["input", "output"]}}},
    {"type": "function", "function": {"name": "video_generate", "description": "Generate a video from images, text, or a slideshow with transitions.", "parameters": {"type": "object", "properties": {"images": {"type": "array", "items": {"type": "string"}, "description": "Image paths for slideshow"}, "text": {"type": "string", "description": "Text to display in video"}, "duration": {"type": "integer", "description": "Duration per slide in seconds (default 3)"}, "fps": {"type": "integer", "description": "Frames per second (default 30)"}, "resolution": {"type": "string", "description": "Resolution WxH (default '1280x720')"}, "transition": {"type": "string", "enum": ["none", "fade", "dissolve", "wipe"], "description": "Transition between slides"}, "bg_color": {"type": "string", "description": "Background color hex (default '#000000')"}, "text_color": {"type": "string", "description": "Text color hex (default '#ffffff')"}, "font_size": {"type": "integer", "description": "Font size for text (default 48)"}, "output": {"type": "string", "description": "Output video path (.mp4)"}}, "required": []}}},
    {"type": "function", "function": {"name": "video_from_text", "description": "Create a video with animated text on background. Great for presentations.", "parameters": {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "string"}, "description": "Text lines to show (one per frame/slide)"}, "duration_per_line": {"type": "number", "description": "Seconds per line (default 3)"}, "bg_color": {"type": "string", "description": "Background color hex"}, "text_color": {"type": "string", "description": "Text color hex"}, "font_size": {"type": "integer", "description": "Font size (default 48)"}, "resolution": {"type": "string", "description": "Resolution (default '1280x720')"}, "output": {"type": "string", "description": "Output .mp4 path"}}, "required": ["lines", "output"]}}},
    {"type": "function", "function": {"name": "audio_generate", "description": "Generate audio tones, beeps, or simple melodies.", "parameters": {"type": "object", "properties": {"type": {"type": "string", "enum": ["tone", "beep", "sweep", "noise", "silence", "melody"], "description": "Audio type"}, "frequency": {"type": "integer", "description": "Frequency in Hz for tone (default 440)"}, "duration": {"type": "number", "description": "Duration in seconds (default 1)"}, "sample_rate": {"type": "integer", "description": "Sample rate (default 44100)"}, "output": {"type": "string", "description": "Output audio file (.wav)"}}, "required": ["type", "output"]}}},
    {"type": "function", "function": {"name": "audio_mix", "description": "Mix multiple audio files together or concatenate them.", "parameters": {"type": "object", "properties": {"files": {"type": "array", "items": {"type": "string"}, "description": "Audio files to mix/concat"}, "mode": {"type": "string", "enum": ["mix", "concat"], "description": "Mix (overlay) or concatenate (default concat)"}, "output": {"type": "string", "description": "Output audio path"}}, "required": ["files", "output"]}}},
    {"type": "function", "function": {"name": "gif_generate", "description": "Generate animated GIF from images or text.", "parameters": {"type": "object", "properties": {"images": {"type": "array", "items": {"type": "string"}, "description": "Image paths for GIF frames"}, "text": {"type": "string", "description": "Text to animate (if no images)"}, "fps": {"type": "integer", "description": "Frames per second (default 10)"}, "loop": {"type": "boolean", "description": "Loop forever (default true)"}, "output": {"type": "string", "description": "Output GIF path"}}, "required": []}}},
    {"type": "function", "function": {"name": "subtitle_generate", "description": "Generate SRT subtitle file from text with timing.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Full text to split into subtitles"}, "words_per_sub": {"type": "integer", "description": "Words per subtitle line (default 8)"}, "duration": {"type": "number", "description": "Total duration in seconds"}, "output": {"type": "string", "description": "Output .srt file path"}}, "required": ["text", "output"]}}},
    {"type": "function", "function": {"name": "sticker_generate", "description": "Generate a sticker/emoji image with text.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Sticker text"}, "emoji": {"type": "string", "description": "Emoji to include"}, "bg_color": {"type": "string", "description": "Background color hex"}, "size": {"type": "integer", "description": "Image size in pixels (default 512)"}, "shape": {"type": "string", "enum": ["circle", "square", "rounded"], "description": "Shape (default circle)"}, "output": {"type": "string", "description": "Output image path"}}, "required": ["text", "output"]}}},
    {"type": "function", "function": {"name": "thumbnail_generate", "description": "Generate a YouTube/social media thumbnail with text and gradient background.", "parameters": {"type": "object", "properties": {"title": {"type": "string", "description": "Thumbnail title text"}, "subtitle": {"type": "string", "description": "Subtitle text"}, "bg_gradient": {"type": "string", "description": "Gradient colors comma-separated (e.g. '#ff6b6b,#4ecdc4')"}, "width": {"type": "integer", "description": "Width (default 1280)"}, "height": {"type": "integer", "description": "Height (default 720)"}, "output": {"type": "string", "description": "Output image path"}}, "required": ["title", "output"]}}},
    {"type": "function", "function": {"name": "watermark_add", "description": "Add a text watermark to an image.", "parameters": {"type": "object", "properties": {"input": {"type": "string", "description": "Input image path"}, "text": {"type": "string", "description": "Watermark text"}, "opacity": {"type": "number", "description": "Opacity 0-1 (default 0.3)"}, "position": {"type": "string", "enum": ["center", "bottom-right", "bottom-left", "top-right", "top-left"], "description": "Position (default bottom-right)"}, "output": {"type": "string", "description": "Output image path"}}, "required": ["input", "text", "output"]}}},
    {"type": "function", "function": {"name": "image_collage", "description": "Create a collage from multiple images.", "parameters": {"type": "object", "properties": {"images": {"type": "array", "items": {"type": "string"}, "description": "Image paths"}, "columns": {"type": "integer", "description": "Number of columns (default 2)"}, "spacing": {"type": "integer", "description": "Spacing between images in pixels (default 10)"}, "bg_color": {"type": "string", "description": "Background color hex (default '#ffffff')"}, "output": {"type": "string", "description": "Output image path"}}, "required": ["images", "output"]}}},
    {"type": "function", "function": {"name": "barcode_generate", "description": "Generate a barcode image.", "parameters": {"type": "object", "properties": {"data": {"type": "string", "description": "Data to encode"}, "type": {"type": "string", "enum": ["code128", "code39", "ean13", "ean8", "upca"], "description": "Barcode type (default code128)"}, "output": {"type": "string", "description": "Output image path"}}, "required": ["data", "output"]}}},
]

TOOL_NAMES = [d["function"]["name"] for d in TOOL_DEFS]

_MEDIA_DIR = os.path.join(os.path.expanduser("~"), ".keyzbot", "media")


def _ensure_media_dir():
    os.makedirs(_MEDIA_DIR, exist_ok=True)
    return _MEDIA_DIR


def _gen_path(ext, prefix="media"):
    d = _ensure_media_dir()
    fname = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join(d, fname)


def execute(name, args, work_dir=None):
    try:
        if name == "tts_generate":
            text = args["text"]
            voice = args.get("voice", "")
            rate = args.get("rate", "+0%")
            output = args.get("output", _gen_path("mp3", "tts"))

            # Try edge-tts first (best quality, free)
            try:
                cmd = ["edge-tts", "--text", text, "--rate", rate, "--write-media", output]
                if voice:
                    cmd += ["--voice", voice]
                else:
                    # Auto-detect language
                    if any(c in text for c in "äöüß"):
                        cmd += ["--voice", "de-DE-KatjaNeural"]
                    elif any(ord(c) > 0x3040 and ord(c) < 0x30FF for c in text):
                        cmd += ["--voice", "ja-JP-NanamiNeural"]
                    elif any(ord(c) > 0x4E00 and ord(c) < 0x9FFF for c in text):
                        cmd += ["--voice", "zh-CN-XiaoxiaoNeural"]
                    elif any(c in "åäö" for c in text.lower()):
                        cmd += ["--voice", "sv-SE-SofieNeural"]
                    else:
                        # Default to Indonesian or English
                        id_chars = set("abcdefghijklmnopqrstuvwxyz")
                        words = text.lower().split()
                        id_indicators = {"dan", "yang", "ini", "itu", "adalah", "untuk", "dengan", "pada", "dari", "ke", "di"}
                        if any(w in id_indicators for w in words):
                            cmd += ["--voice", "id-ID-ArdiNeural"]
                        else:
                            cmd += ["--voice", "en-US-AriaNeural"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if r.returncode == 0 and os.path.exists(output):
                    return json.dumps({"type": "audio", "path": output, "format": "mp3", "text": text[:100]})
            except FileNotFoundError:
                pass

            # Fallback to gTTS
            try:
                from gtts import gTTS
                lang = "id" if any(w in text.lower().split() for w in ["dan", "yang", "ini", "itu"]) else "en"
                tts = gTTS(text=text, lang=lang)
                tts.save(output)
                return json.dumps({"type": "audio", "path": output, "format": "mp3", "text": text[:100]})
            except ImportError:
                pass

            # Fallback to espeak
            try:
                r = subprocess.run(["espeak", "-w", output, text], capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    return json.dumps({"type": "audio", "path": output, "format": "wav", "text": text[:100]})
            except FileNotFoundError:
                pass

            return "Error: No TTS engine available. Install: pip install edge-tts"

        elif name == "tts_voices":
            lang = args.get("language", "")
            try:
                cmd = ["edge-tts", "--list-voices"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                voices = []
                for line in r.stdout.split("\n"):
                    if line.startswith("Name:"):
                        vname = line.split(":", 1)[1].strip()
                        if not lang or lang in vname:
                            voices.append(vname)
                return "\n".join(voices[:50]) or f"(no voices found for '{lang}')"
            except:
                return "Error: edge-tts not installed"

        elif name == "image_generate":
            prompt = args["prompt"]
            width = args.get("width", 512)
            height = args.get("height", 512)
            style = args.get("style", "realistic")
            output = args.get("output", _gen_path("png", "imggen"))

            # Try Stable Diffusion via API (free tier)
            try:
                import requests as _req
                _s = _req.Session()
                _s.trust_env = False
                # Try Pollinations.ai (free, no API key)
                styled_prompt = f"{prompt}, {style} style" if style != "realistic" else prompt
                url = f"https://image.pollinations.ai/prompt/{_req.utils.quote(styled_prompt)}?width={width}&height={height}&nologo=true"
                resp = _s.get(url, timeout=60, stream=True)
                if resp.status_code == 200:
                    with open(output, "wb") as f:
                        for chunk in resp.iter_content(8192):
                            f.write(chunk)
                    if os.path.getsize(output) > 1000:
                        return json.dumps({"type": "image", "path": output, "prompt": prompt, "style": style, "size": f"{width}x{height}"})
            except Exception:
                pass

            # Fallback: generate a placeholder image with prompt text
            try:
                from PIL import Image, ImageDraw, ImageFont
                img = Image.new("RGB", (width, height), color=(30, 30, 40))
                draw = ImageDraw.Draw(img)
                # Draw gradient
                for y in range(height):
                    r = int(30 + (y / height) * 50)
                    g = int(30 + (y / height) * 30)
                    b = int(60 + (y / height) * 80)
                    draw.line([(0, y), (width, y)], fill=(r, g, b))
                # Draw text
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
                except:
                    font = ImageFont.load_default()
                # Wrap text
                words = prompt.split()
                lines = []
                line = ""
                for w in words:
                    test = line + " " + w if line else w
                    if len(test) > 40:
                        lines.append(line)
                        line = w
                    else:
                        line = test
                if line:
                    lines.append(line)
                y = height // 2 - len(lines) * 15
                for l in lines[:6]:
                    draw.text((width // 2, y), l, fill=(255, 255, 255), font=font, anchor="mm")
                    y += 30
                draw.text((width // 2, height - 40), f"[{style}]", fill=(150, 150, 180), font=font, anchor="mm")
                img.save(output)
                return json.dumps({"type": "image", "path": output, "prompt": prompt, "style": style, "size": f"{width}x{height}", "note": "placeholder — AI image API unavailable"})
            except ImportError:
                return "Error: Pillow not installed. Run: pip install Pillow"

        elif name == "image_edit":
            from PIL import Image, ImageFilter, ImageEnhance, ImageDraw, ImageFont
            inp = args["input"]
            output = args["output"]
            img = Image.open(inp)

            # Apply filter
            filt = args.get("filter", "none")
            if filt == "grayscale": img = img.convert("L").convert("RGB")
            elif filt == "sepia":
                gray = img.convert("L")
                img = Image.merge("RGB", (gray.point(lambda x: min(255, x + 50)), gray.point(lambda x: min(255, x + 20)), gray))
            elif filt == "blur": img = img.filter(ImageFilter.GaussianBlur(radius=5))
            elif filt == "sharpen": img = img.filter(ImageFilter.SHARPEN)
            elif filt == "invert": img = Image.frombytes(img.mode, img.size, bytes(255 - b for b in img.tobytes()))
            elif filt == "brightness":
                factor = args.get("brightness", 1.5)
                img = ImageEnhance.Brightness(img).enhance(factor)
            elif filt == "contrast": img = ImageEnhance.Contrast(img).enhance(1.5)
            elif filt == "vintage":
                img = img.convert("L").convert("RGB")
                img = ImageEnhance.Color(img).enhance(0.5)
            elif filt == "pixelate":
                small = img.resize((img.width // 10, img.height // 10))
                img = small.resize(img.size, Image.NEAREST)

            # Rotate
            if args.get("rotate"):
                img = img.rotate(args["rotate"], expand=True)

            # Text overlay
            if args.get("text_overlay"):
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
                except:
                    font = ImageFont.load_default()
                text = args["text_overlay"]
                pos = args.get("text_position", "bottom")
                bbox = draw.textbbox((0, 0), text, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                if pos == "top": xy = ((img.width - tw) // 2, 20)
                elif pos == "center": xy = ((img.width - tw) // 2, (img.height - th) // 2)
                else: xy = ((img.width - tw) // 2, img.height - th - 20)
                # Shadow
                draw.text((xy[0] + 2, xy[1] + 2), text, fill=(0, 0, 0), font=font)
                draw.text(xy, text, fill=(255, 255, 255), font=font)

            img.save(output)
            return json.dumps({"type": "image", "path": output, "filter": filt})

        elif name == "video_generate":
            images = args.get("images", [])
            text = args.get("text", "")
            duration = args.get("duration", 3)
            fps = args.get("fps", 30)
            res = args.get("resolution", "1280x720").split("x")
            w, h = int(res[0]), int(res[1])
            bg_color = args.get("bg_color", "#000000")
            text_color = args.get("text_color", "#ffffff")
            font_size = args.get("font_size", 48)
            output = args.get("output", _gen_path("mp4", "video"))

            if images:
                # Create slideshow from images
                # Create concat file for ffmpeg
                concat_file = _gen_path("txt", "concat")
                with open(concat_file, "w") as f:
                    for img_path in images:
                        f.write(f"file '{os.path.abspath(img_path)}'\n")
                        f.write(f"duration {duration}\n")
                    f.write(f"file '{os.path.abspath(images[-1])}'\n")
                cmd = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
                    "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                    output
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    return json.dumps({"type": "video", "path": output, "duration": len(images) * duration, "resolution": f"{w}x{h}"})
                return f"Error: {r.stderr[-500:]}"

            elif text:
                # Create text video using ffmpeg
                # Generate text frames with PIL then compile
                from PIL import Image, ImageDraw, ImageFont
                frames_dir = _ensure_media_dir()
                words = text.split()
                chunks = [" ".join(words[i:i+6]) for i in range(0, len(words), 6)]
                frame_files = []
                for i, chunk in enumerate(chunks[:20]):
                    img = Image.new("RGB", (w, h), color=bg_color)
                    draw = ImageDraw.Draw(img)
                    try:
                        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
                    except:
                        font = ImageFont.load_default()
                    # Center text
                    lines = []
                    line = ""
                    for word in chunk.split():
                        test = line + " " + word if line else word
                        if len(test) > 35:
                            lines.append(line)
                            line = word
                        else:
                            line = test
                    if line:
                        lines.append(line)
                    y = h // 2 - len(lines) * (font_size + 10) // 2
                    for l in lines:
                        draw.text((w // 2, y), l, fill=text_color, font=font, anchor="mm")
                        y += font_size + 10
                    frame_path = os.path.join(frames_dir, f"frame_{i:04d}.png")
                    img.save(frame_path)
                    frame_files.append(frame_path)

                # Compile frames to video
                cmd = [
                    "ffmpeg", "-y", "-framerate", str(1/duration),
                    "-i", os.path.join(frames_dir, "frame_%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                    output
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                # Cleanup frames
                for f in frame_files:
                    os.remove(f)
                if r.returncode == 0:
                    return json.dumps({"type": "video", "path": output, "duration": len(chunks) * duration, "resolution": f"{w}x{h}"})
                return f"Error: {r.stderr[-500:]}"

            return "Error: provide 'images' or 'text'"

        elif name == "video_from_text":
            lines = args["lines"]
            dur = args.get("duration_per_line", 3)
            bg_color = args.get("bg_color", "#1a1a2e")
            text_color = args.get("text_color", "#e94560")
            font_size = args.get("font_size", 48)
            res = args.get("resolution", "1280x720").split("x")
            w, h = int(res[0]), int(res[1])
            output = args["output"]

            from PIL import Image, ImageDraw, ImageFont
            frames_dir = _ensure_media_dir()
            frame_files = []
            for i, line in enumerate(lines[:50]):
                img = Image.new("RGB", (w, h), color=bg_color)
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
                except:
                    font = ImageFont.load_default()
                draw.text((w // 2, h // 2), line, fill=text_color, font=font, anchor="mm")
                frame_path = os.path.join(frames_dir, f"vft_{i:04d}.png")
                img.save(frame_path)
                frame_files.append(frame_path)

            cmd = [
                "ffmpeg", "-y", "-framerate", str(1/dur),
                "-i", os.path.join(frames_dir, "vft_%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                output
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            for f in frame_files:
                os.remove(f)
            if r.returncode == 0:
                return json.dumps({"type": "video", "path": output, "duration": len(lines) * dur, "resolution": f"{w}x{h}"})
            return f"Error: {r.stderr[-500:]}"

        elif name == "audio_generate":
            import struct, math
            atype = args["type"]
            output = args["output"]
            freq = args.get("frequency", 440)
            duration = args.get("duration", 1)
            sample_rate = args.get("sample_rate", 44100)
            n_samples = int(sample_rate * duration)

            samples = []
            if atype == "tone":
                for i in range(n_samples):
                    samples.append(int(32767 * math.sin(2 * math.pi * freq * i / sample_rate)))
            elif atype == "beep":
                for i in range(n_samples):
                    t = i / sample_rate
                    val = math.sin(2 * math.pi * freq * t) if (t % 0.5) < 0.25 else 0
                    samples.append(int(32767 * val))
            elif atype == "sweep":
                for i in range(n_samples):
                    t = i / sample_rate
                    f = freq + (2000 - freq) * (t / duration)
                    samples.append(int(32767 * math.sin(2 * math.pi * f * t)))
            elif atype == "noise":
                import random
                samples = [random.randint(-32767, 32767) for _ in range(n_samples)]
            elif atype == "silence":
                samples = [0] * n_samples
            elif atype == "melody":
                notes = [262, 294, 330, 349, 392, 440, 494, 523]  # C major scale
                note_len = n_samples // len(notes)
                for note_freq in notes:
                    for i in range(note_len):
                        samples.append(int(32767 * math.sin(2 * math.pi * note_freq * i / sample_rate)))

            # Write WAV
            import wave
            with wave.open(output, "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

            return json.dumps({"type": "audio", "path": output, "format": "wav", "duration": duration})

        elif name == "audio_mix":
            files = args["files"]
            mode = args.get("mode", "concat")
            output = args["output"]

            if mode == "concat":
                # Use ffmpeg to concatenate
                concat_file = _gen_path("txt", "aconcat")
                with open(concat_file, "w") as f:
                    for fp in files:
                        f.write(f"file '{os.path.abspath(fp)}'\n")
                cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output]
            else:
                # Mix (overlay)
                inputs = []
                for fp in files:
                    inputs += ["-i", fp]
                filter_str = "".join(f"[{i}:a]" for i in range(len(files))) + f"amix=inputs={len(files)}:duration=longest[aout]"
                cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", filter_str, "-map", "[aout]", output]

            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                return json.dumps({"type": "audio", "path": output, "mode": mode})
            return f"Error: {r.stderr[-500:]}"

        elif name == "gif_generate":
            images = args.get("images", [])
            text = args.get("text", "")
            fps = args.get("fps", 10)
            output = args.get("output", _gen_path("gif", "gif"))

            if images:
                cmd = ["ffmpeg", "-y", "-framerate", str(fps)]
                concat_file = _gen_path("txt", "gconcat")
                with open(concat_file, "w") as f:
                    for img in images:
                        f.write(f"file '{os.path.abspath(img)}'\n")
                        f.write(f"duration {1/fps}\n")
                cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-vf", "scale=480:-1", output]
            elif text:
                from PIL import Image, ImageDraw, ImageFont
                frames_dir = _ensure_media_dir()
                frame_files = []
                for i in range(min(len(text), 30)):
                    img = Image.new("RGBA", (480, 240), (30, 30, 50, 255))
                    draw = ImageDraw.Draw(img)
                    try:
                        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
                    except:
                        font = ImageFont.load_default()
                    visible = text[:i+1]
                    draw.text((240, 120), visible, fill=(255, 255, 255), font=font, anchor="mm")
                    fp = os.path.join(frames_dir, f"gf_{i:04d}.png")
                    img.save(fp)
                    frame_files.append(fp)
                cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", os.path.join(frames_dir, "gf_%04d.png"), output]
            else:
                return "Error: provide 'images' or 'text'"

            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            # Cleanup
            if text:
                for f in frame_files:
                    os.remove(f)
            if r.returncode == 0:
                return json.dumps({"type": "gif", "path": output})
            return f"Error: {r.stderr[-500:]}"

        elif name == "subtitle_generate":
            text = args["text"]
            words_per = args.get("words_per_sub", 8)
            duration = args.get("duration", 0)
            output = args["output"]

            words = text.split()
            chunks = [" ".join(words[i:i+words_per]) for i in range(0, len(words), words_per)]
            if not duration:
                duration = len(chunks) * 2.5  # ~2.5s per subtitle

            time_per = duration / len(chunks)
            lines = []
            for i, chunk in enumerate(chunks):
                start = i * time_per
                end = (i + 1) * time_per
                lines.append(f"{i+1}")
                lines.append(f"{_format_srt_time(start)} --> {_format_srt_time(end)}")
                lines.append(chunk)
                lines.append("")

            with open(output, "w") as f:
                f.write("\n".join(lines))
            return json.dumps({"type": "subtitle", "path": output, "lines": len(chunks), "duration": duration})

        elif name == "sticker_generate":
            from PIL import Image, ImageDraw, ImageFont
            text = args["text"]
            emoji = args.get("emoji", "")
            bg_color = args.get("bg_color", "#ff6b6b")
            size = args.get("size", 512)
            shape = args.get("shape", "circle")
            output = args["output"]

            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Parse bg color
            bg = bg_color.lstrip("#")
            bg_rgb = tuple(int(bg[i:i+2], 16) for i in (0, 2, 4))

            # Draw shape
            if shape == "circle":
                draw.ellipse([10, 10, size-10, size-10], fill=bg_rgb)
            elif shape == "rounded":
                draw.rounded_rectangle([10, 10, size-10, size-10], radius=40, fill=bg_rgb)
            else:
                draw.rectangle([10, 10, size-10, size-10], fill=bg_rgb)

            # Draw text
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size // 6)
                emoji_font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", size // 4)
            except:
                font = ImageFont.load_default()
                emoji_font = font

            if emoji:
                draw.text((size // 2, size // 3), emoji, fill=(255, 255, 255), font=emoji_font, anchor="mm")
                draw.text((size // 2, size * 2 // 3), text, fill=(255, 255, 255), font=font, anchor="mm")
            else:
                draw.text((size // 2, size // 2), text, fill=(255, 255, 255), font=font, anchor="mm")

            img.save(output)
            return json.dumps({"type": "image", "path": output, "kind": "sticker"})

        elif name == "thumbnail_generate":
            from PIL import Image, ImageDraw, ImageFont
            title = args["title"]
            subtitle = args.get("subtitle", "")
            gradient = args.get("bg_gradient", "#667eea,#764ba2").split(",")
            w = args.get("width", 1280)
            h = args.get("height", 720)
            output = args["output"]

            img = Image.new("RGB", (w, h))
            draw = ImageDraw.Draw(img)

            # Gradient background
            c1 = gradient[0].lstrip("#")
            c2 = gradient[1].lstrip("#") if len(gradient) > 1 else gradient[0].lstrip("#")
            r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
            r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)

            for y in range(h):
                t = y / h
                r = int(r1 + (r2 - r1) * t)
                g = int(g1 + (g2 - g1) * t)
                b = int(b1 + (b2 - b1) * t)
                draw.line([(0, y), (w, y)], fill=(r, g, b))

            try:
                title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
                sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
            except:
                title_font = ImageFont.load_default()
                sub_font = title_font

            # Title with shadow
            draw.text((w//2 + 3, h//2 - 20 + 3), title, fill=(0, 0, 0), font=title_font, anchor="mm")
            draw.text((w//2, h//2 - 20), title, fill=(255, 255, 255), font=title_font, anchor="mm")

            if subtitle:
                draw.text((w//2, h//2 + 60), subtitle, fill=(200, 200, 220), font=sub_font, anchor="mm")

            img.save(output, quality=95)
            return json.dumps({"type": "image", "path": output, "kind": "thumbnail"})

        elif name == "watermark_add":
            from PIL import Image, ImageDraw, ImageFont
            inp = args["input"]
            text = args["text"]
            opacity = args.get("opacity", 0.3)
            position = args.get("position", "bottom-right")
            output = args["output"]

            img = Image.open(inp).convert("RGBA")
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            except:
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            padding = 20

            positions = {
                "center": ((img.width - tw) // 2, (img.height - th) // 2),
                "bottom-right": (img.width - tw - padding, img.height - th - padding),
                "bottom-left": (padding, img.height - th - padding),
                "top-right": (img.width - tw - padding, padding),
                "top-left": (padding, padding),
            }
            xy = positions.get(position, positions["bottom-right"])
            alpha = int(opacity * 255)
            draw.text(xy, text, fill=(255, 255, 255, alpha), font=font)

            result = Image.alpha_composite(img, overlay).convert("RGB")
            result.save(output)
            return json.dumps({"type": "image", "path": output, "kind": "watermarked"})

        elif name == "image_collage":
            from PIL import Image
            images = args["images"]
            cols = args.get("columns", 2)
            spacing = args.get("spacing", 10)
            bg_color = args.get("bg_color", "#ffffff")
            output = args["output"]

            imgs = [Image.open(p) for p in images]
            # Resize all to same height
            target_h = min(img.height for img in imgs)
            resized = []
            for img in imgs:
                ratio = target_h / img.height
                resized.append(img.resize((int(img.width * ratio), target_h)))

            rows = (len(resized) + cols - 1) // cols
            # Calculate grid dimensions
            col_widths = []
            for c in range(cols):
                max_w = 0
                for r in range(rows):
                    idx = r * cols + c
                    if idx < len(resized):
                        max_w = max(max_w, resized[idx].width)
                col_widths.append(max_w)

            total_w = sum(col_widths) + spacing * (cols + 1)
            total_h = rows * target_h + spacing * (rows + 1)

            bg = bg_color.lstrip("#")
            bg_rgb = tuple(int(bg[i:i+2], 16) for i in (0, 2, 4))
            collage = Image.new("RGB", (total_w, total_h), bg_rgb)

            x = spacing
            for r in range(rows):
                y = spacing
                for c in range(cols):
                    idx = r * cols + c
                    if idx < len(resized):
                        collage.paste(resized[idx], (x, y))
                    x += col_widths[c] + spacing
                y += target_h + spacing

            collage.save(output)
            return json.dumps({"type": "image", "path": output, "kind": "collage", "images": len(images)})

        elif name == "barcode_generate":
            try:
                import barcode
                from barcode.writer import ImageWriter
                data = args["data"]
                btype = args.get("type", "code128")
                output = args["output"]

                bc_class = getattr(barcode, btype, barcode.code128)
                bc = bc_class(data, writer=ImageWriter())
                saved = bc.save(output.replace(".png", "").replace(".jpg", ""))
                return json.dumps({"type": "image", "path": saved, "kind": "barcode"})
            except ImportError:
                return "Error: python-barcode not installed. Run: pip install python-barcode"

        return f"Error: Unknown tool '{name}'"
    except Exception as e:
        return f"Error: {e}"


def _format_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
