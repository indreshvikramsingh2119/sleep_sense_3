"""
Live-capture strip: YouTube-style playback for the EXISTING pyqtgraph charts, with no second renderer.

 - The live charts stay the single source of truth (curves, digits, event boxes, colours, fonts).
 - While playing, each chart's plot area is covered by an opaque StripCanvas. Every frame it only blits
   pre-captured bitmap tiles at an offset taken from a wall clock (cost ~constant, independent of speed/data).
 - Tiles are produced by driving the live charts to a page offset and grabbing the middle part of their plot area.
   Work is spread over frames with a per-tick time budget, so no frame is blocked for long.
 - If anything is not ready the canvas keeps showing the last good picture instead of blanking.
"""
import os, time, math
import numpy as np
from PyQt5.QtCore import Qt, QRect, QPointF
from PyQt5.QtGui import QPainter, QPixmap, QColor, QImage
from PyQt5.QtWidgets import QWidget


class Clock:
    def __init__(self):
        self.pos0, self.t0, self.speed, self.playing = 0.0, time.perf_counter(), 1.0, False
    def now(self):
        return self.pos0 + ((time.perf_counter() - self.t0) * self.speed if self.playing else 0.0)
    def seek(self, pos): self.pos0, self.t0 = float(pos), time.perf_counter()
    def set_speed(self, s): self.pos0, self.t0, self.speed = self.now(), time.perf_counter(), float(s)
    def play(self): self.pos0, self.t0, self.playing = self.now(), time.perf_counter(), True
    def pause(self): self.pos0, self.playing = self.now(), False


class StripCanvas(QWidget):
    """Opaque widget laid over one chart's plot area. Paints a snapshot while buffering, tiles while running."""
    def __init__(self, strip, index, parent):
        super().__init__(parent)
        self.strip, self.index = strip, index
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    def paintEvent(self, _):
        p = QPainter(self)
        self.strip.paint_panel(p, self.index, self.width(), self.height())
        p.end()

    # While playing, the live chart under this canvas shows a different time than the canvas does. Swallow all
    # mouse input here so a click can never select / edit / delete an invisible event; pause to interact.
    def mousePressEvent(self, e): e.accept()
    def mouseReleaseEvent(self, e): e.accept()
    def mouseDoubleClickEvent(self, e): e.accept()
    def mouseMoveEvent(self, e): e.accept()
    def wheelEvent(self, e): e.accept()
    def contextMenuEvent(self, e): e.accept()


class LiveCaptureStrip:
    def __init__(self, panels, drive, window_s=60.0, max_offset=None, budget_ms=7.0, smooth=False):
        """
        panels : list of (live_widget, geom_callable)  -> geom() = (x_origin, width, y, height) of the ViewBox in the widget's own
                 coordinates; width is the EXACT pixel width of the [0, window_s] view range (float), x_origin the column of time 0
        drive  : callable(offset_s)  -> make ALL live charts show [offset, offset+window_s] exactly (lean/playing render)
        """
        self.panels, self.drive, self.window_s, self.max_offset = panels, drive, float(window_s), max_offset
        self.budget_ms, self.smooth = budget_ms, smooth
        geometries = [geom() for _widget, geom in panels]
        self.Wfs = [float(geometry[1]) for geometry in geometries]
        self.Ws = [int(round(width)) for width in self.Wfs]
        self.Hs = [g()[3] for _, g in panels]
        self.ppxs = [width / self.window_s for width in self.Wfs]
        # Every chart covers the same time interval but its ViewBox width can
        # differ because its left-axis labels have a different width.  Keep one
        # common half-window tile duration and calculate pixels independently
        # for every panel; using panel 0's width for Airflow caused broken joins.
        self.tile_s = self.window_s / 2.0
        self.tile_pxs = [int(round(self.tile_s * ppx)) for ppx in self.ppxs]
        # Backwards-compatible aliases used only for profiling/debug output.
        self.Wf, self.W = self.Wfs[0], self.Ws[0]
        self.ppx, self.tile_px = self.ppxs[0], self.tile_pxs[0]
        # Always capture source context on both sides of a tile. Even with
        # integer (non-smooth) blitting, pyqtgraph needs neighbouring samples
        # to rasterize a curve that crosses the tile edge without clipping its
        # endpoint. paint_panel clips each tile to its own interval, so these
        # extra source pixels never create overlap or double-darkening.
        self.margin = 12
        self.tiles = {}                                  # (panel, k) -> QPixmap
        self.tile_left_margin = {}                       # actual captured left overlap (can be 0 at recording boundaries)
        self.snap = [None] * len(panels)
        self.clock = Clock()
        self.canvases, self.state = [], "idle"
        self._cur = None                                 # (k, next_panel_index) while a page is being captured
        self.misses = 0
        self.rebuffers = 0                               # times playback had to wait for tiles (YouTube-style rebuffering)
        self.rebuffer_ms = 0.0
        self._rebuf_t0 = None
        self.pump_ms = []                                # per-tick time spent capturing
        self.hold_offset = 0.0
        self._sig = None
        self._profile = os.environ.get("PSG_PROFILE", "0") not in ("0", "", "false", "False")
        self._session_t0 = None
        self._page_active_ms = None
        self._page_drive_ms = 0.0
        self._page_grab_ms = 0.0
        self.page_ms, self.drive_ms, self.grab_ms = [], [], []
        self.buffer_ms = []
        self._buffer_t0 = None
        self.seeks = 0
        self._profile_reported = False
        self.grid = [None] * len(panels)                 # fixed grid picture per panel (transparent, only the grid lines)
        self.reuse_ok, self.reuse_miss = None, (0.0, 0.0)  # result of verify_reuse() (None = tiles were not reused)

    @staticmethod
    def _hide_live_overlays(widget):
        """The live event boxes are placed in viewport coordinates, so their top edge pokes a few px above the plot area
        and would show above the canvas as a thin static line. They are already baked into the tiles: hide the live ones."""
        for overlay in (getattr(widget, "selection_overlays", None) or ()):
            try:
                overlay.hide()
            except Exception:
                pass

    @staticmethod
    def _capture_grid(widget, rect):
        """Everything the axes draw INSIDE the plot area (vertical grid lines + tick marks) as one transparent picture.
        It is made from the live chart with every plot item hidden, so only the axis marks are left, and it is drawn on
        top of the scrolling tiles. Tiles are captured without the axes, so grid and ticks stay at fixed positions like
        in the live chart instead of scrolling with the data. Returns None if the result does not look like axis marks
        (then the tiles keep their own marks)."""
        hidden = []
        try:
            for item in list(getattr(widget.getPlotItem().vb, "addedItems", None) or ()):
                try:
                    if item.isVisible():
                        item.setVisible(False)
                        hidden.append(item)
                except Exception:
                    pass
            LiveCaptureStrip._hide_live_overlays(widget)
            grabbed = widget.grab(rect)
            source_dpr = float(grabbed.devicePixelRatioF())
            image = grabbed.toImage()
        except Exception:
            return None
        finally:
            for item in hidden:
                try:
                    item.setVisible(True)
                except Exception:
                    pass
        try:
            gray = image.convertToFormat(image.Format_Grayscale8)
            pointer = gray.constBits()
            pointer.setsize(gray.byteCount())
            pixels = np.frombuffer(pointer, np.uint8).reshape(gray.height(), gray.bytesPerLine())[:, : gray.width()]
            pixels = pixels.astype(np.float32)
            background = np.maximum(pixels.max(axis=1, keepdims=True), 1.0)        # per-row background level
            alpha = np.clip(255.0 * (1.0 - pixels / background), 0.0, 255.0).astype(np.uint8)
            if not alpha.any() or float(alpha.mean()) > 8.0:
                return None                                                          # nothing there, or wide dark areas (not axis marks)
            alpha = np.ascontiguousarray(alpha)
            alpha_image = type(image)(alpha.data, gray.width(), gray.height(), gray.width(), image.Format_Grayscale8).copy()
            overlay = type(image)(gray.width(), gray.height(), image.Format_ARGB32_Premultiplied)
            overlay.fill(Qt.black)
            overlay.setAlphaChannel(alpha_image)
            picture = QPixmap.fromImage(overlay)
            # QRect and all strip coordinates are logical pixels.  Keep the
            # pixmap's native DPR so Qt maps its physical pixels back to those
            # same logical coordinates (especially at Windows 125%/150%).
            picture.setDevicePixelRatio(source_dpr)
            return picture
        except Exception:
            return None

    def _grab_tile(self, i, widget, rect):
        """Tile picture WITHOUT the axes (grid lines and tick marks are drawn separately at fixed positions)."""
        axes = []
        if self.grid[i] is not None:
            try:
                plot_item = widget.getPlotItem()
                for name in ("bottom", "left", "top", "right"):
                    axis = plot_item.getAxis(name)
                    axes.append((axis, axis.opacity()))
                    axis.setOpacity(0.0)
            except Exception:
                pass
        try:
            picture = widget.grab(rect)
        finally:
            for axis, opacity in axes:
                try:
                    axis.setOpacity(opacity)
                except Exception:
                    pass
        if self.grid[i] is None:
            return picture
        try:
            # The fixed axes/grid must be painted behind the waveform, just as
            # pyqtgraph paints them in the live view. Turn the tile's white
            # plot background transparent while retaining antialiased curves,
            # labels and event boxes as foreground pixels.
            image = picture.toImage()
            image = image.convertToFormat(image.Format_RGBA8888)
            pointer = image.bits()
            pointer.setsize(image.byteCount())
            rgba = np.frombuffer(pointer, np.uint8).reshape(
                image.height(), image.bytesPerLine() // 4, 4
            )[:, : image.width()].copy()
            observed = rgba[:, :, :3].astype(np.float32)
            coverage = 255.0 - observed.min(axis=2)
            visible = coverage >= 2.0
            scale = np.maximum(coverage / 255.0, 1.0 / 255.0)
            foreground = (
                observed - 255.0 * (1.0 - scale[:, :, None])
            ) / scale[:, :, None]
            rgba[:, :, :3] = np.clip(foreground, 0.0, 255.0).astype(np.uint8)
            rgba[:, :, 3] = np.where(visible, coverage, 0.0).astype(np.uint8)
            rgba = np.ascontiguousarray(rgba)
            transparent = type(image)(
                rgba.data,
                image.width(),
                image.height(),
                image.width() * 4,
                image.Format_RGBA8888,
            ).copy()
            result = QPixmap.fromImage(transparent)
            result.setDevicePixelRatio(float(picture.devicePixelRatioF()))
            return result
        except Exception:
            return picture

    # ---------- reuse of tiles across Pause -> Play -------------------------------------------
    def export_tiles(self):
        """Complete tiles (every panel present) of this session, to offer to the next strip of the same content."""
        n = len(self.panels)
        complete = {k for (_i, k) in self.tiles if all((i, k) in self.tiles for i in range(n))}
        return {
            "tiles": {key: pm for key, pm in self.tiles.items() if key[1] in complete},
            "margins": {key: m for key, m in self.tile_left_margin.items() if key[1] in complete},
            "window_s": self.window_s,
            "signature": self._sig,
        }

    def adopt(self, exported):
        """Take over tiles of an earlier session (call right after start()).  Returns how many tiles were taken;
        0 when window / geometry differ.  Nothing is trusted yet: the caller must run verify_reuse()."""
        if not exported or not exported.get("tiles"):
            return 0
        if abs(float(exported["window_s"]) - self.window_s) > 1e-9 or exported["signature"] != self._sig:
            return 0
        self.tiles.update(exported["tiles"])
        self.tile_left_margin.update(exported["margins"])
        return len({k for (_i, k) in exported["tiles"]})

    @staticmethod
    def _ink(image, block=4):
        """Coarse 'where is anything drawn' mask of a QImage (non-white pixels, OR-pooled in block x block cells)."""
        image = image.convertToFormat(QImage.Format_RGB32)
        pointer = image.constBits()
        pointer.setsize(image.byteCount())
        rows = np.frombuffer(pointer, np.uint8).reshape(image.height(), image.bytesPerLine() // 4, 4)[:, : image.width(), :3]
        ink = (255 - rows.min(axis=2)) >= 12
        h = (ink.shape[0] // block) * block
        w = (ink.shape[1] // block) * block
        return ink[:h, :w].reshape(h // block, block, w // block, block).any(axis=(1, 3))

    @staticmethod
    def _dilate(mask):
        out = mask.copy()
        out[1:, :] |= mask[:-1, :]; out[:-1, :] |= mask[1:, :]
        tmp = out.copy()
        out[:, 1:] |= tmp[:, :-1]; out[:, :-1] |= tmp[:, 1:]
        return out

    def verify_reuse(self, max_global=0.06, max_local=0.10, chunks=12):
        """Compare what the adopted tiles WOULD show at the start position with the live snapshot taken a moment ago
        (the picture the user is looking at right now).  Different events / scale / data show up as ink on one side
        only: either spread over the panel (global share) or piled up in one stretch of it (local share, which is
        how a deleted / added / moved event box looks).  Sub-pixel placement noise stays far below both limits.
        Returns (ok, worst_global, worst_local).  On failure every adopted tile is dropped, so the normal
        page-by-page build takes over."""
        worst_global = worst_local = 0.0
        ok = True
        try:
            if not self._covered(self.position()):
                ok = False; worst_global = worst_local = 1.0     # partial coverage: not worth trusting
            else:
                saved_state = self.state
                self.state = "running"                          # paint_panel draws tiles, not the snapshot
                try:
                    for i in range(len(self.panels)):
                        snap = self.snap[i]
                        if snap is None:
                            ok = False; break
                        dpr = float(snap.devicePixelRatioF())
                        img = QImage(snap.width(), snap.height(), QImage.Format_RGB32)
                        img.setDevicePixelRatio(dpr)
                        img.fill(Qt.white)
                        p = QPainter(img)
                        self.paint_panel(p, i, int(round(snap.width() / dpr)), int(round(snap.height() / dpr)))
                        p.end()
                        a = self._ink(snap.toImage()); b = self._ink(img)
                        if a.shape != b.shape:
                            ok = False; worst_global = worst_local = 1.0; break
                        miss = (a & ~self._dilate(b)) | (b & ~self._dilate(a))
                        worst_global = max(worst_global, float(miss.sum()) / max(int((a | b).sum()), 1))
                        for part in np.array_split(np.arange(miss.shape[1]), int(chunks)):
                            if part.size:
                                worst_local = max(worst_local, float(miss[:, part].sum()) / miss[:, part].size)
                        if worst_global > max_global or worst_local > max_local:
                            ok = False; break
                finally:
                    self.state = saved_state
        except Exception:
            ok = False; worst_global = worst_local = 1.0
        if not ok:
            self.tiles.clear(); self.tile_left_margin.clear()
        self.reuse_ok, self.reuse_miss = ok, (worst_global, worst_local)
        return ok, worst_global, worst_local

    # ---------- lifecycle ------------------------------------------------------------------
    def start(self, pos):
        """Cover the charts with a snapshot of what is on screen NOW (live charts must be showing offset == pos)."""
        self._session_t0 = time.perf_counter()
        self._buffer_t0 = self._session_t0
        self.hold_offset = float(pos)
        self._sig = self.signature()
        for i, (w, geom) in enumerate(self.panels):
            ox, wd, y, h = geom()
            panel_width = self.Ws[i]
            self.snap[i] = w.grab(QRect(int(round(ox)), y, panel_width, h))
            self.grid[i] = self._capture_grid(w, QRect(int(round(ox)), y, panel_width, h))
            self._hide_live_overlays(w)
            c = StripCanvas(self, i, w.parent())
            c.setGeometry(w.x() + int(round(ox)), w.y() + y, panel_width, h)
            c.show(); c.raise_(); self.canvases.append(c)
        self.clock.seek(pos); self.clock.speed = self.clock.speed; self.clock.playing = False
        self.state = "buffering"

    def seek(self, pos):
        """External jump while playing (event click, slider arrows). Live charts must already show offset == pos.
        Tiles stay valid (they are keyed by absolute time); only the half-captured page and the snapshot are redone."""
        if self._cur is not None:
            k = self._cur[0]
            for i in range(len(self.panels)):
                self.tiles.pop((i, k), None)
                self.tile_left_margin.pop((i, k), None)
            self._cur = None
        self._page_active_ms = None
        self._page_drive_ms = 0.0
        self._page_grab_ms = 0.0
        self.seeks += 1
        self._buffer_t0 = time.perf_counter()
        self.hold_offset = float(pos)
        for i, (w, geom) in enumerate(self.panels):
            ox, wd, y, h = geom()
            self.snap[i] = w.grab(QRect(int(round(ox)), y, self.Ws[i], h))
            self._hide_live_overlays(w)
        self.clock.seek(pos); self.clock.playing = False
        self.state = "buffering"

    def stop(self):
        """Return the final position; live charts are untouched here (caller refreshes them, then we hide the canvases)."""
        pos = self.position(); self.clock.pause()
        return pos

    def release(self):
        self._report_profile()
        if self.rebuffers and not self._profile:
            pass
        for c in self.canvases:
            c.hide(); c.setParent(None); c.deleteLater()
        self.canvases, self.state, self._cur = [], "idle", None

    @staticmethod
    def _summary(values):
        if not values:
            return "n=0"
        ordered = sorted(float(value) for value in values)
        p95 = ordered[max(0, int(math.ceil(0.95 * len(ordered))) - 1)]
        return (
            f"n={len(ordered)} avg={sum(ordered) / len(ordered):.1f}ms "
            f"p95={p95:.1f}ms max={ordered[-1]:.1f}ms"
        )

    def _report_profile(self):
        if not self._profile or self._profile_reported:
            return
        self._profile_reported = True
        elapsed = 0.0 if self._session_t0 is None else time.perf_counter() - self._session_t0
        pass

    def signature(self):
        sig = []
        for _, geom in self.panels:
            ox, wd, y, h = geom()
            sig.append((int(round(ox)), int(round(wd)), int(y), int(h)))
        return tuple(sig)

    def geometry_changed(self):
        """True when the charts were re-laid out (resize, hidden chart, axis width change): tiles no longer line up."""
        return self.signature() != self._sig

    # ---------- per frame -------------------------------------------------------------------
    def position(self):
        pos = self.clock.now()
        if self.max_offset is not None and pos >= self.max_offset:
            pos = self.max_offset
        return pos

    def tick(self):
        """Call once per frame. Returns the playback position (seconds)."""
        t0 = time.perf_counter()
        pos = self.position()
        if self.state == "buffering" and self.reuse_ok and self._covered(pos):
            # Reused (verified) tiles already cover the window: start moving first, build the next page afterwards.
            if self._buffer_t0 is not None:
                self.buffer_ms.append((time.perf_counter() - self._buffer_t0) * 1000.0)
                self._buffer_t0 = None
            self.state = "running"; self.clock.seek(self.hold_offset); self.clock.play()
            pos = self.position()
        self._pump(pos)
        self.pump_ms.append((time.perf_counter() - t0) * 1000.0)
        if self.state == "buffering" and self._covered(pos):
            if self._buffer_t0 is not None:
                self.buffer_ms.append((time.perf_counter() - self._buffer_t0) * 1000.0)
                self._buffer_t0 = None
            self.state = "running"; self.clock.seek(self.hold_offset); self.clock.play()
            pos = self.position()
        elif self.state == "running" and not self._covered(pos, self._lead_px()):
            # Never run the clock into tiles that are not captured yet (that would show blank gaps instead of data):
            # hold the position and wait, exactly like a video player rebuffering. The check looks ~0.35 s of
            # motion ahead, so the tile that is about to enter the window is always ready before it appears.
            self.clock.pause(); self.state = "rebuffering"; self.rebuffers += 1; self._rebuf_t0 = time.perf_counter()
        elif self.state == "rebuffering" and self._covered(pos, self._lead_px()):
            self.clock.play(); self.state = "running"
            self.rebuffer_ms += (time.perf_counter() - self._rebuf_t0) * 1000.0
        for c in self.canvases:
            c.update()
        return pos

    # ---------- tile bookkeeping -------------------------------------------------------------
    def _x0(self, pos, panel=0): return pos * self.ppxs[panel]

    def _lead_px(self):
        return abs(self.clock.speed) * 0.35 * self.ppx

    def _visible_tiles(self, pos, extra_px=0.0):
        extra_seconds = float(extra_px) / self.ppx
        return range(
            int(math.floor(float(pos) / self.tile_s)),
            int(math.floor((float(pos) + self.window_s + extra_seconds) / self.tile_s)) + 1,
        )

    def _wanted(self, pos):
        vis = list(self._visible_tiles(pos))
        ahead = max(1, int(math.ceil(max(2.0, 1.5 * abs(self.clock.speed)) / self.tile_s)))
        order = vis + [vis[-1] + j for j in range(1, ahead + 1)]
        return [k for k in order if k >= 0 and self._valid(k)]

    def _valid(self, k):
        if self.max_offset is None: return True
        return k * self.tile_s <= self.max_offset + self.window_s

    def _ready(self, k): return all((i, k) in self.tiles for i in range(len(self.panels)))

    def _covered(self, pos, extra_px=0.0):
        return all(self._ready(k) for k in self._visible_tiles(pos, extra_px) if self._valid(k))

    def _capture_offset(self, k):
        """Live offset that puts tile k in the middle half of every chart."""
        o = k * self.tile_s - (self.window_s - self.tile_s) / 2.0
        o_c = o
        if o_c < 0: o_c = 0.0
        if self.max_offset is not None and o_c > self.max_offset: o_c = self.max_offset
        return o_c

    def _pump(self, pos):
        deadline = time.perf_counter() + self.budget_ms / 1000.0
        while time.perf_counter() < deadline:
            if self._cur is None:
                todo = [k for k in self._wanted(pos) if not self._ready(k)]
                if not todo: return
                k = todo[0]
                o_c = self._capture_offset(k)
                drive_t0 = time.perf_counter()
                self.drive(o_c)                                  # one live refresh per page (may exceed the budget; max once per tick)
                self._page_drive_ms = (time.perf_counter() - drive_t0) * 1000.0
                stall = self._page_drive_ms / 1000.0
                if stall > 0.03 and self.clock.playing:
                    # The GUI thread was blocked for `stall` seconds: do not let the wall clock run ahead into tiles
                    # that were not captured yet. Playback simply waits that long (like a player that stalls).
                    self.clock.t0 += stall
                self._page_grab_ms = 0.0
                self._page_active_ms = self._page_drive_ms
                self._cur = (k, 0, o_c)
                return
            k, i, o_c = self._cur
            w, geom = self.panels[i]
            ox, wd, y, h = geom()
            panel_width = self.Ws[i]
            tile_px = self.tile_pxs[i]
            a = int(round((k * self.tile_s - o_c) * self.ppxs[i]))
            m = self.margin
            ax = max(0, a - m); aw = min(tile_px + 2 * m, panel_width - ax)
            grab_t0 = time.perf_counter()
            self.tiles[(i, k)] = self._grab_tile(i, w, QRect(int(round(ox)) + ax, y, aw, h))
            self.tile_left_margin[(i, k)] = a - ax
            grab_elapsed = (time.perf_counter() - grab_t0) * 1000.0
            self._page_grab_ms += grab_elapsed
            if self._page_active_ms is not None:
                self._page_active_ms += grab_elapsed
            self._hide_live_overlays(w)
            self._cur = (k, i + 1, o_c) if i + 1 < len(self.panels) else None
            if self._cur is None:
                if self._page_active_ms is not None:
                    self.page_ms.append(self._page_active_ms)
                    self.drive_ms.append(self._page_drive_ms)
                    self.grab_ms.append(self._page_grab_ms)
                self._page_active_ms = None
                self._page_drive_ms = 0.0
                self._page_grab_ms = 0.0
                self._evict(pos)
                continue

    def _evict(self, pos, keep_behind=2, keep_ahead=8):
        k0 = int(math.floor(float(pos) / self.tile_s))
        for key in [key for key in self.tiles if not (k0 - keep_behind <= key[1] <= k0 + keep_ahead)]:
            self.tiles.pop(key, None)
            self.tile_left_margin.pop(key, None)

    # ---------- painting ---------------------------------------------------------------------
    def paint_panel(self, p, i, w, h):
        p.fillRect(0, 0, w, h, Qt.white)
        if self.state == "buffering" or self.snap[i] is None and not self.tiles:
            if self.snap[i] is not None:
                p.drawPixmap(0, 0, self.snap[i])
            return
        pos = self.position()
        x0 = self._x0(pos, i)
        ppx = self.ppxs[i]
        if self.grid[i] is not None:
            p.drawPixmap(0, 0, self.grid[i])                       # fixed axes behind the scrolling waveform
        if self.smooth:
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        else:
            x0 = math.floor(x0)
        for k in self._visible_tiles(pos):
            pm = self.tiles.get((i, k))
            if pm is None:
                self.misses += 1
                continue
            # Position every tile from its absolute time.  Using
            # ``k * round(tile_s * ppx)`` accumulates the rounding error once
            # per tile; after a seek several hours into a recording that can
            # shift compact-window tiles far enough left to expose a blank
            # strip at the right edge.  Keep the time-to-pixel mapping in
            # floating point and round only the final paint/clip coordinates.
            x = k * self.tile_s * ppx - x0
            x_next = (k + 1) * self.tile_s * ppx - x0
            if self.smooth:
                left_margin = self.tile_left_margin.get((i, k), self.margin)
                # Neighbouring tiles must NOT overlap. Tiles are transparent, so an overlap draws the same curve twice
                # (doubled peak, darker lines). Each tile owns exactly [x, x_next); the extra margin columns of the
                # pixmap are only source pixels for the sub-pixel blit at its two edges.
                clip_left = int(math.floor(x))
                clip_right = int(math.floor(x_next))
                p.save(); p.setClipRect(QRect(clip_left, 0, max(1, clip_right - clip_left), h))
                p.drawPixmap(QPointF(x - left_margin, 0), pm); p.restore()
            else:
                left_margin = self.tile_left_margin.get((i, k), self.margin)
                clip_left = int(math.floor(x))
                clip_right = int(math.floor(x_next))
                p.save(); p.setClipRect(QRect(clip_left, 0, max(1, clip_right - clip_left), h))
                p.drawPixmap(int(math.floor(x - left_margin)), 0, pm); p.restore()
