from __future__ import annotations

import math
import numpy as np
from scipy.interpolate import splprep, splev

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

from PyQt6.QtCore import Qt, QPointF, QRectF, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QPainterPath, QPixmap, QTransform, QAction
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsPathItem,
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QMessageBox,
)

def rdp_simplify(points: List[Tuple[float, float]], epsilon: float) -> List[Tuple[float, float]]:
    """
    Douglas–Peucker simplification (iterative).
    `epsilon` is a distance threshold in the same units as points (here: image pixels).
    """
    n = len(points)
    if n <= 2:
        return points[:]
    keep = [False] * n
    keep[0] = keep[-1] = True

    stack = [(0, n - 1)]
    while stack:
        s, e = stack.pop()
        x1, y1 = points[s]
        x2, y2 = points[e]
        max_d = -1.0
        idx = -1
        for i in range(s + 1, e):
            px, py = points[i]
            d = _perp_dist_to_segment(px, py, x1, y1, x2, y2)
            if d > max_d:
                max_d = d
                idx = i
        if max_d > epsilon and idx != -1:
            keep[idx] = True
            stack.append((s, idx))
            stack.append((idx, e))

    return [pt for pt, k in zip(points, keep) if k]

def polyline_length(points: List[Tuple[float, float]]) -> float:
    """Sum of straight segments; same units as inputs (image px)."""
    if len(points) < 2:
        return 0.0
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        total += math.hypot(x2 - x1, y2 - y1)
    return total

# --------- Polyline helpers ---------
def _perp_dist_to_segment(px: float, py: float,
                        x1: float, y1: float,
                        x2: float, y2: float) -> float:
    """Perpendicular distance from P to line segment A(x1,y1)->B(x2,y2) in same units as inputs."""
    vx, vy = x2 - x1, y2 - y1
    if vx == 0.0 and vy == 0.0:
        # A and B are the same point
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * vx + (py - y1) * vy) / (vx*vx + vy*vy)
    if t <= 0.0:
        # closest to A
        return math.hypot(px - x1, py - y1)
    elif t >= 1.0:
        # closest to B
        return math.hypot(px - x2, py - y2)
    # project to segment
    projx = x1 + t * vx
    projy = y1 + t * vy
    return math.hypot(px - projx, py - projy)

# --------- Data Models (image-pixel coordinates) ---------
@dataclass(frozen=True)
class CrackData:
    points: List[Tuple[float, float]]                 # raw
    points_simplified: List[Tuple[float, float]]      # RDP result
    crack_type: str = "External"
    epsilon_used: float = 1.0

@dataclass(frozen=True)
class PerimeterData:
    control_points: List[Tuple[float, float]]
    spline_points: List[Tuple[float, float]]

# --------- Coordinate utilities ---------
class CoordinateManager:
    @staticmethod
    def scene_to_image(scene_pt: QPointF, image_item: QGraphicsPixmapItem) -> Tuple[float, float]:
        """Map a scene point into the original image pixel grid."""
        local = image_item.mapFromScene(scene_pt)  # item coords (scaled)
        # Map item coords to original pixmap pixels
        br = image_item.boundingRect()
        pm = image_item.pixmap()
        if br.width() == 0 or br.height() == 0:
            return (0.0, 0.0)
        x = local.x() * (pm.width() / br.width())
        y = local.y() * (pm.height() / br.height())
        return (float(x), float(y))

    @staticmethod
    def image_to_scene(image_pt: Tuple[float, float], image_item: QGraphicsPixmapItem) -> QPointF:
        """Map an image pixel coordinate into scene space."""
        br = image_item.boundingRect()
        pm = image_item.pixmap()
        if pm.width() == 0 or pm.height() == 0:
            return QPointF()
        ix, iy = image_pt
        x_item = ix * (br.width() / pm.width())
        y_item = iy * (br.height() / pm.height())
        return image_item.mapToScene(QPointF(x_item, y_item))

# --------- Scene for items ---------
class CanvasScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.image_item: Optional[QGraphicsPixmapItem] = None

        # Overlays created once and kept alive
        self.perimeter_item = QGraphicsPathItem()
        self.perimeter_item.setZValue(10)
        pen = QPen(Qt.GlobalColor.green, 2)
        pen.setCosmetic(True)
        self.perimeter_item.setPen(pen)
        self.addItem(self.perimeter_item)

        self.crack_items: List[QGraphicsPathItem] = []

    def set_image(self, pix: QPixmap):
        """Update or create the background image item without destroying overlays."""
        if self.image_item is None:
            self.image_item = self.addPixmap(pix)
            self.image_item.setZValue(0)
        else:
            self.image_item.setPixmap(pix)

        # Keep a little gutter around the content
        r = self.itemsBoundingRect().adjusted(-50, -50, 50, 50)
        self.setSceneRect(r)

# --------- View with zoom/pan and drawing modes (no legacy preview) ---------
class CanvasView(QGraphicsView):
    """
    Modes:
      - 'idle': no drawing
      - 'draw_perimeter': LMB adds red-cross control points; MMB to spline/confirm; RMB delete/clear
      - 'draw_crack': LMB drag to draw; RMB delete near point
    """
    perimeterUpdated = pyqtSignal()
    cracksUpdated = pyqtSignal()
    modeChanged = pyqtSignal(str)

    def __init__(self, scene: CanvasScene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)

        self._mode: str = 'idle'

        # Visual pens
        self._perimeter_pen = QPen(Qt.GlobalColor.green, 2); self._perimeter_pen.setCosmetic(True)
        self._crack_pen = QPen(Qt.GlobalColor.red, 2); self._crack_pen.setCosmetic(True)
        
        # Snap/zoom
        self._snap_radius_img = 5.0
        self._min_scale: float = 1.0
        self._max_scale: float = 32.0
        self._draw_start_scale: float = 1.0

        # RMB pan state
        self._rmb_pressed = False
        self._rmb_panning = False
        self._rmb_last_pos = QPointF()
        self._rmb_drag_threshold = 3.0

        # Crack storage + live draw
        self._crack_preview_item: Optional[QGraphicsPathItem] = None
        self._cracks: List[CrackData] = []
        self._current_crack_img: List[Tuple[float, float]] = []
        self._has_valid_inside_point = False

        # Perimeter editing
        self._perim_ctrl_img: List[Tuple[float, float]] = []
        self._perim_generated: bool = False
        self._perim_ctrl_item: Optional[QGraphicsPathItem] = None
        self._perimeter: Optional[PerimeterData] = None
        self._csd_px: float = 1.0  # avoid div-by-zero; recompute on perimeter changes
        self._item_to_crack: Dict[QGraphicsPathItem, CrackData] = {}

    def _apply_mode(self, mode: str, force_emit: bool = False):
        if self._mode == mode and not force_emit:
            return
        self._mode = mode
        self.modeChanged.emit(mode)

    # ---------- Public API ----------
    def load_image(self, path: str) -> bool:
        pm = QPixmap(path)
        if pm.isNull():
            return False
        scene: CanvasScene = self.scene()  # type: ignore
        scene.set_image(pm)
        self._fit_and_set_min()

        # clear any transient crack state on new image
        self._current_crack_img.clear()
        self._has_valid_inside_point = False
        self._clear_crack_preview()
        self.clear_overlays()  # optional: full reset
        self._perimeter = None
        self._csd_px = 1.0
        return True

    def set_mode(self, mode: str):
        self._current_crack_img.clear()
        self._has_valid_inside_point = False
        self._clear_crack_preview()
        self._apply_mode(mode)

    def clear_overlays(self):
        scene: CanvasScene = self.scene()  # type: ignore
        scene.perimeter_item.setPath(QPainterPath())
        if self._perim_ctrl_item:
            scene.removeItem(self._perim_ctrl_item)
            self._perim_ctrl_item = None
        self._perim_ctrl_img.clear()
        self._perim_generated = False

        # reset perimeter model + csd
        self._perimeter = None
        self._csd_px = 1.0

        for itm in list(scene.crack_items):
            scene.removeItem(itm)
        scene.crack_items.clear()
        self._cracks.clear()
        self._item_to_crack.clear()

        self._apply_mode('draw_perimeter', force_emit=True)
        self.perimeterUpdated.emit()
        self.cracksUpdated.emit()

    def get_perimeter_data(self) -> PerimeterData:
        return self._perimeter or PerimeterData([], [])
    
    def get_crack_data_list(self) -> List[CrackData]:
        return list(self._cracks)

    def resimplify_all_cracks(self, new_eps: float):
        scene: CanvasScene = self.scene()  # type: ignore
        if not scene:
            return

        # Recompute simplified points for each crack in order
        new_cracks: List[CrackData] = []
        for c in self._cracks:
            simp = rdp_simplify(c.points, new_eps)
            new_cracks.append(CrackData(points=c.points,
                                        points_simplified=simp,
                                        crack_type=c.crack_type,
                                        epsilon_used=new_eps))
        self._cracks = new_cracks

        # Update scene items to match the new simplified geometry
        for item, c in zip(scene.crack_items, self._cracks):
            if item.scene() is not None:
                item.setPath(self._build_path_from_img(c.points_simplified or c.points))

        # Rebuild the item->crack map so it points at the NEW CrackData objects
        self._item_to_crack = {item: c for item, c in zip(scene.crack_items, self._cracks)}

        # update types when epsilon changes
        self._reclassify_all_cracks()
        self.cracksUpdated.emit()


    # ---------- Perimeter UI ----------
    def _update_perim_ctrl_overlay(self):
        scene: CanvasScene = self.scene()  # type: ignore
        if scene.image_item is None:
            return
        if self._perim_ctrl_item is None:
            self._perim_ctrl_item = QGraphicsPathItem()
            self._perim_ctrl_item.setZValue(12)
            pen = QPen(Qt.GlobalColor.red, 1); pen.setCosmetic(True)
            self._perim_ctrl_item.setPen(pen)
            scene.addItem(self._perim_ctrl_item)

        p = QPainterPath()
        cross_len = 5
        for ix, iy in self._perim_ctrl_img:
            spt = CoordinateManager.image_to_scene((ix, iy), scene.image_item)
            p.moveTo(spt + QPointF(-cross_len, 0)); p.lineTo(spt + QPointF(cross_len, 0))
            p.moveTo(spt + QPointF(0, -cross_len)); p.lineTo(spt + QPointF(0, cross_len))
        self._perim_ctrl_item.setPath(p)

    def _delete_nearest_ctrl_point(self, img_xy: Tuple[float, float], thresh_px: float = 10.0) -> bool:
        if not self._perim_ctrl_img:
            return False
        tx, ty = img_xy
        best_i, best_d2 = -1, thresh_px * thresh_px
        for i, (x, y) in enumerate(self._perim_ctrl_img):
            d2 = (x - tx)**2 + (y - ty)**2
            if d2 <= best_d2:
                best_i, best_d2 = i, d2
        if best_i >= 0:
            self._perim_ctrl_img.pop(best_i)
            self._update_perim_ctrl_overlay()
            return True
        return False

    def _clockwise_sorted(self, pts: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        if not pts: return pts
        cx = sum(x for x, _ in pts)/len(pts); cy = sum(y for _, y in pts)/len(pts)
        return sorted(pts, key=lambda p: math.atan2(p[1]-cy, p[0]-cx))

    def _generate_perimeter_loop(self):
        scene: CanvasScene = self.scene()  # type: ignore
        if scene.image_item is None:
            return
        if len(self._perim_ctrl_img) < 3:
            try:
                QMessageBox.warning(self, "Not Enough Points",
                                    "Please add more points to define the perimeter.")
            except Exception:
                pass
            return

        # 1) Order clockwise (legacy behavior)
        ordered = self._clockwise_sorted(self._perim_ctrl_img)

        # 2) Drop near-duplicates (~1 px) to avoid splprep failures
        dedup: List[Tuple[float, float]] = []
        for p in ordered:
            if not dedup or math.hypot(p[0] - dedup[-1][0], p[1] - dedup[-1][1]) >= 1.0:
                dedup.append(p)
        if len(dedup) < 3:
            return

        # Optional: avoid identical first/last with per=True
        if math.hypot(dedup[0][0] - dedup[-1][0], dedup[0][1] - dedup[-1][1]) < 1e-6:
            dedup = dedup[:-1]
            if len(dedup) < 3:
                return

        # 3) Try to build a periodic spline. Fall back to polygon if it fails.
        spline_img: List[Tuple[float, float]]
        try:
            x = [pt[0] for pt in dedup]
            y = [pt[1] for pt in dedup]
            tck, _ = splprep([x, y], s=0, per=True)
            sx, sy = splev(np.linspace(0.0, 1.0, 1000), tck)
            spline_img = list(zip(map(float, sx), map(float, sy)))
        except Exception:
            # Fallback: just use the deduped polygon
            spline_img = dedup

        # 4) Draw to scene from spline_img (works for both spline and fallback)
        path = QPainterPath()
        first = CoordinateManager.image_to_scene(spline_img[0], scene.image_item)
        path.moveTo(first)
        for px, py in spline_img[1:]:
            path.lineTo(CoordinateManager.image_to_scene((px, py), scene.image_item))
        path.closeSubpath()
        scene.perimeter_item.setPen(self._perimeter_pen)
        scene.perimeter_item.setPath(path)
        self._perim_generated = True

        # 5) Store model copy and recompute CSD
        #    (use dedup as control points so we don’t persist duplicates)
        self._set_perimeter(ctrl_img=dedup, spline_img=spline_img)

        # 6) Reclassify cracks against the new perimeter
        self._reclassify_all_cracks()

    def _clear_perimeter_loop(self):
        scene: CanvasScene = self.scene()  # type: ignore
        scene.perimeter_item.setPath(QPainterPath())
        self._perim_generated = False

        # reset model copy + csd
        self._perimeter = None
        self._csd_px = 1.0

        # with no perimeter all cracks are considered internal
        self._reclassify_all_cracks()
        self.perimeterUpdated.emit()

    # ---------- zoom-floor helpers ----------
    
    def _fit_and_set_min(self):
        """Fit the image to the view and record that transform as the min zoom."""
        scene: CanvasScene = self.scene()  # type: ignore
        if not scene or not scene.image_item:
            return
        self.resetTransform()
        self.fitInView(scene.image_item, Qt.AspectRatioMode.KeepAspectRatio)
        # record current uniform scale as the minimum
        self._min_scale = self.transform().m11()
        self.centerOn(scene.image_item)

    def _recompute_min_scale(self):
        """Keep the min zoom consistent when the viewport size changes."""
        scene: CanvasScene = self.scene()  # type: ignore
        if not scene or not scene.image_item:
            return
        img_rect = scene.image_item.sceneBoundingRect()
        if img_rect.isEmpty():
            return

        vw = self.viewport().width()
        vh = self.viewport().height()
        if vw <= 0 or vh <= 0:
            return

        sx = vw / img_rect.width()
        sy = vh / img_rect.height()
        new_min = min(sx, sy)

        cur = self.transform().m11()
        if cur < new_min and cur > 0:
            self.scale(new_min / cur, new_min / cur)
            self.centerOn(scene.image_item)

        self._min_scale = new_min

    # ---------- Geometry / helpers ----------
    def _set_perimeter(self, ctrl_img: List[Tuple[float,float]], spline_img: List[Tuple[float,float]]):
        self._perimeter = PerimeterData(control_points=list(ctrl_img),
                                        spline_points=list(spline_img))
        # CSD = perimeter_length / pi (in pixels)
        per_len = 0.0
        for (x1,y1),(x2,y2) in zip(spline_img, spline_img[1:]):
            per_len += math.hypot(x2-x1, y2-y1)
        per_len += math.hypot(spline_img[0][0]-spline_img[-1][0], spline_img[0][1]-spline_img[-1][1])
        self._csd_px = (per_len / math.pi) if per_len > 0 else 1.0
        self.perimeterUpdated.emit()
    
    def _ensure_crack_preview(self):
        if self._crack_preview_item is None:
            scene: CanvasScene = self.scene()  # type: ignore
            self._crack_preview_item = QGraphicsPathItem()
            self._crack_preview_item.setZValue(15)
            pen = QPen(self._crack_pen)        # same visual as final cracks
            pen.setCosmetic(True)
            self._crack_preview_item.setPen(pen)
            scene.addItem(self._crack_preview_item)

    def _update_crack_preview(self):
        if not self._current_crack_img:
            return
        # show live path (simplified)
        eps = self._crack_preview_eps_px()
        preview_src = self._smooth_once(self._current_crack_img)
        preview_pts = rdp_simplify(preview_src, eps)
        self._ensure_crack_preview()
        self._crack_preview_item.setPath(self._build_path_from_img(preview_pts))

    def _clear_crack_preview(self):
        if self._crack_preview_item is not None:
            scene: CanvasScene = self.scene()  # type: ignore
            scene.removeItem(self._crack_preview_item)
            self._crack_preview_item = None

    def _extract_points_from_path(self, item: QGraphicsPathItem, image_item: Optional[QGraphicsPixmapItem]):
        if image_item is None: return
        path = item.path()
        for i in range(path.elementCount()):
            e = path.elementAt(i)
            yield CoordinateManager.scene_to_image(self.mapToScene(self.mapFromScene(QPointF(e.x, e.y))), image_item)

    def _perimeter_points_img(self) -> List[Tuple[float, float]]:
        if self._perimeter and len(self._perimeter.spline_points) >= 3:
            return self._perimeter.spline_points
        # fallback if no model yet (during early editing)
        scene: CanvasScene = self.scene()  # type: ignore
        if not scene or scene.image_item is None:
            return []
        return list(self._extract_points_from_path(scene.perimeter_item, scene.image_item))

    def is_within_perimeter_img(self, img_xy: Tuple[float, float]) -> bool:
        pts = self._perimeter_points_img()
        if len(pts) < 3: return True
        x, y = img_xy; inside = False; j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]; xj, yj = pts[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    def snap_to_perimeter_img(self, img_xy: Tuple[float, float], threshold_px: float = 5.0) -> Tuple[float, float]:
        pts = self._perimeter_points_img()
        if len(pts) < 3: return img_xy
        x, y = img_xy; best = None; best_d2 = threshold_px * threshold_px
        for px, py in pts:
            d2 = (px-x)**2 + (py-y)**2
            if d2 <= best_d2:
                best = (px, py); best_d2 = d2
        return best if best is not None else img_xy

    def _classify_crack_img(self, crack_img: List[Tuple[float, float]]) -> str:
        if not crack_img:
            return "Internal"
        s = int(self._endpoint_on_perimeter(crack_img[0])) + int(self._endpoint_on_perimeter(crack_img[-1]))
        return "Internal" if s == 0 else ("External" if s == 1 else "Split")

    def _build_path_from_img(self, img_pts: List[Tuple[float, float]]) -> QPainterPath:
        scene: CanvasScene = self.scene()  # type: ignore
        p = QPainterPath()
        if not img_pts or scene.image_item is None: return p
        p.moveTo(CoordinateManager.image_to_scene(img_pts[0], scene.image_item))
        for ipt in img_pts[1:]:
            p.lineTo(CoordinateManager.image_to_scene(ipt, scene.image_item))
        return p

    def _delete_crack_near_scene_point(self, scene_pt: QPointF, tol_scene_px: float = 8.0) -> bool:
        scene: CanvasScene = self.scene()  # type: ignore
        if scene.image_item is None: return False
        for item in list(scene.crack_items):
            path = item.path()
            for i in range(path.elementCount()):
                e = path.elementAt(i)
                if QPointF(e.x, e.y).toPoint() == scene_pt.toPoint() or \
                   (QPointF(e.x, e.y) - scene_pt).manhattanLength() <= tol_scene_px:
                    scene.removeItem(item)
                    scene.crack_items.remove(item)
                    c = self._item_to_crack.pop(item, None)
                    if c:
                        try:
                            self._cracks.remove(c)
                        except ValueError:
                            pass
                    self.cracksUpdated.emit()
                    return True
        return False

    def _pan_by_pixels(self, dx: float, dy: float):
        p1 = self.mapToScene(self.viewport().rect().center())
        p2 = self.mapToScene(self.viewport().rect().center() - QPoint(int(dx), int(dy)))
        self.centerOn(self.mapToScene(self.viewport().rect().center()) + (p2 - p1))

    def _reclassify_all_cracks(self):
        updated = []
        for c in self._cracks:
            pts = self._pts_for_measure(c)  # classify using the same geometry we measure
            new_type = self._classify_crack_img(pts)
            if new_type != c.crack_type:
                c = CrackData(points=c.points,
                            points_simplified=c.points_simplified,
                            crack_type=new_type)
            updated.append(c)
        self._cracks = updated

    def _dist_to_polyline(self, pt: Tuple[float,float], poly: List[Tuple[float,float]]) -> float:
        x,y = pt
        best = float("inf")
        for (x1,y1),(x2,y2) in zip(poly, poly[1:]+poly[:1]):  # closed
            vx, vy = x2-x1, y2-y1
            if vx==vy==0: 
                d = math.hypot(x-x1, y-y1)
            else:
                t = max(0.0, min(1.0, ((x-x1)*vx + (y-y1)*vy) / (vx*vx + vy*vy)))
                px, py = x1 + t*vx, y1 + t*vy
                d = math.hypot(x-px, y-py)
            best = min(best, d)
        return best

    def _endpoint_on_perimeter(self, p: Tuple[float,float], eps_px: float = 3.0) -> bool:
        if not self._perimeter or len(self._perimeter.spline_points) < 3:
            return False
        return self._dist_to_polyline(p, self._perimeter.spline_points) <= eps_px

    def engine_inputs(self):
        """Return (csd_px, [(type, length_pct), ...]) for rating engine."""
        out = []
        for c in self._cracks:
            pts = self._pts_for_measure(c)
            L = polyline_length(pts)
            pct = (L / self._csd_px) * 100.0 if self._csd_px > 0 else 0.0
            out.append((c.crack_type, pct))
        return self._csd_px, out

    def _pts_for_measure(self, c: CrackData) -> List[Tuple[float, float]]:
        """Prefer the simplified polyline; fall back to raw if missing."""
        return c.points_simplified or c.points
    
    def _crack_eps_px(self) -> float:
        """
        Simplification tolerance in image px, scaled by the draw start zoom.
        At 1x zoom → ~1.0 px. Zoomed out (scale<1) → larger ε (more smoothing).
        """
        base = 1.0
        return base * (1.0 / self._draw_start_scale)

    def _crack_preview_eps_px(self) -> float:
        """Preview simplification tolerance (a bit tighter for fidelity)."""
        return max(0.5, 0.6 * self._crack_eps_px())
    
    def _smooth_once(self, pts: List[Tuple[float,float]]) -> List[Tuple[float,float]]:
        if len(pts) < 3: 
            return pts[:]
        out = [pts[0]]
        for i in range(1, len(pts)-1):
            x = (pts[i-1][0] + pts[i][0] + pts[i+1][0]) / 3.0
            y = (pts[i-1][1] + pts[i][1] + pts[i+1][1]) / 3.0
            out.append((x, y))
        out.append(pts[-1])
        return out

    # ---------- Events ----------
    def wheelEvent(self, e):
        step = 1.25 if e.angleDelta().y() > 0 else 0.8
        cur = self.transform().m11()
        target = cur * step
        if target < self._min_scale: step = self._min_scale / cur
        elif target > self._max_scale: step = self._max_scale / cur
        if abs(step - 1.0) > 1e-6: self.scale(step, step)

    def mousePressEvent(self, e):
        scene: CanvasScene = self.scene()  # type: ignore

        # Right: maybe pan, maybe delete on release
        if e.button() == Qt.MouseButton.RightButton:
            self._rmb_pressed = True; self._rmb_panning = False
            self._rmb_last_pos = e.position()
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            return

        # Middle: perimeter generate/confirm
        if e.button() == Qt.MouseButton.MiddleButton and self._mode == 'draw_perimeter':
            if not self._perim_generated:
                self._generate_perimeter_loop()
            else:
                if self._perim_ctrl_item:
                    scene.removeItem(self._perim_ctrl_item); self._perim_ctrl_item = None
                self._perim_ctrl_img.clear()
                self._apply_mode('draw_crack')
            return

        # Left:
        if e.button() == Qt.MouseButton.LeftButton:
            if self._mode == 'draw_perimeter':
                if scene.image_item is None: return
                img_xy = CoordinateManager.scene_to_image(self.mapToScene(e.position().toPoint()), scene.image_item)
                self._perim_ctrl_img.append(img_xy)
                self._update_perim_ctrl_overlay()
                return
            if self._mode == 'draw_crack':
                self._current_crack_img.clear()
                self._has_valid_inside_point = False
                self._clear_crack_preview()
                self._draw_start_scale = max(self.transform().m11(), 1e-6)  # record scale at start
                return

        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        # RMB pan
        if self._rmb_pressed:
            delta = e.position() - self._rmb_last_pos
            if not self._rmb_panning and delta.manhattanLength() >= self._rmb_drag_threshold:
                self._rmb_panning = True
                self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            if self._rmb_panning:
                self._pan_by_pixels(delta.x(), delta.y())
                self._rmb_last_pos = e.position()
                return

        # Crack live draw (drag)
        if self._mode == 'draw_crack' and (e.buttons() & Qt.MouseButton.LeftButton):
            scene: CanvasScene = self.scene()  # type: ignore
            if scene.image_item is not None:
                img_xy = CoordinateManager.scene_to_image(self.mapToScene(e.position().toPoint()), scene.image_item)
                if not self.is_within_perimeter_img(img_xy):
                    return
                MIN_STEP = 0.75  # image px
                if not self._has_valid_inside_point:
                    self._has_valid_inside_point = True
                    img_xy = self.snap_to_perimeter_img(img_xy, self._snap_radius_img)
                    self._current_crack_img = [img_xy]
                else:
                    lx, ly = self._current_crack_img[-1]
                    if math.hypot(img_xy[0]-lx, img_xy[1]-ly) >= MIN_STEP:
                        self._current_crack_img.append(img_xy)

                # show live path
                self._update_crack_preview()
                return  # consume move while drawing

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        # RMB release → delete if it wasn’t a pan
        if e.button() == Qt.MouseButton.RightButton and self._rmb_pressed:
            self._rmb_pressed = False
            was_panning = self._rmb_panning
            self._rmb_panning = False
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            if not was_panning:
                scene: CanvasScene = self.scene()  # type: ignore
                sp = self.mapToScene(e.position().toPoint())
                if self._mode == 'draw_perimeter':
                    if not self._perim_generated:
                        if scene.image_item:
                            img_xy = CoordinateManager.scene_to_image(sp, scene.image_item)
                            self._delete_nearest_ctrl_point(img_xy, 10.0)
                    else:
                        self._clear_perimeter_loop()
                        self._reclassify_all_cracks()
                        self._clear_crack_preview()
                elif self._mode == 'draw_crack':
                    self._delete_crack_near_scene_point(sp)
                    self._clear_crack_preview()
            return

        # Crack finalize
        if self._mode == 'draw_crack' and e.button() == Qt.MouseButton.LeftButton:
            scene: CanvasScene = self.scene()  # type: ignore
            if scene.image_item is not None and self._has_valid_inside_point:
                end_img = CoordinateManager.scene_to_image(self.mapToScene(e.position().toPoint()), scene.image_item)
                end_img = self.snap_to_perimeter_img(end_img, self._snap_radius_img)
                if not self.is_within_perimeter_img(end_img) and self._current_crack_img:
                    end_img = self._current_crack_img[-1]
                self._current_crack_img.append(end_img)

                if len(self._current_crack_img) >= 3:
                    # finalize crack
                    eps = self._crack_eps_px()
                    src = self._smooth_once(self._current_crack_img)
                    final_pts = rdp_simplify(src, eps)

                    crack_item = QGraphicsPathItem()
                    crack_item.setZValue(20)
                    crack_item.setPen(self._crack_pen)
                    crack_item.setPath(self._build_path_from_img(final_pts))
                    scene.addItem(crack_item)
                    scene.crack_items.append(crack_item)

                    ctype = self._classify_crack_img(final_pts)  # classify on simplified endpoints
                    cdata = CrackData(points=list(self._current_crack_img),
                                    points_simplified=list(final_pts),
                                    crack_type=ctype, epsilon_used=eps)
                    self._cracks.append(cdata)
                    self._item_to_crack[crack_item] = cdata
                    self.cracksUpdated.emit()


            # cleanup preview + transient
            self._current_crack_img.clear()
            self._has_valid_inside_point = False
            self._clear_crack_preview()
            return

        super().mouseReleaseEvent(e)

    # keep min-scale consistent on resize
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._recompute_min_scale()

# ----- for testing new zoom view features before committing -----
class GVTestPane(QWidget):
    def __init__(self, image_path: str = ""):
        super().__init__()
        layout = QVBoxLayout(self)

        scene = CanvasScene()
        self.view = CanvasView(scene)
        layout.addWidget(self.view)

        # Buttons
        btns = QHBoxLayout()

        self.btn_load = QPushButton("Load Image")
        self.btn_load.clicked.connect(self.load_image_dialog)
        btns.addWidget(self.btn_load)

        self.btn_perim = QPushButton("Perimeter Mode")
        self.btn_perim.clicked.connect(lambda: self.view.set_mode('draw_perimeter'))
        btns.addWidget(self.btn_perim)

        self.btn_crack = QPushButton("Crack Mode")
        self.btn_crack.clicked.connect(lambda: self.view.set_mode('draw_crack'))
        btns.addWidget(self.btn_crack)

        self.btn_idle = QPushButton("Idle Mode")
        self.btn_idle.clicked.connect(lambda: self.view.set_mode('idle'))
        btns.addWidget(self.btn_idle)

        self.btn_dump = QPushButton("Print Data")
        self.btn_dump.clicked.connect(self._print_data)
        btns.addWidget(self.btn_dump)

        layout.addLayout(btns)

        if image_path:
            self.view.load_image(image_path)

    def load_image_dialog(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if fname:
            self.view.load_image(fname)

    def _print_data(self):
        per = self.view.get_perimeter_data()
        cracks = self.view.get_crack_data_list()
        print("Perimeter control pts:", per.control_points[:5], f"... ({len(per.control_points)} pts)")
        print("Cracks:", [len(c.points) for c in cracks])
