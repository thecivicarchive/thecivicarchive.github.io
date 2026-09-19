"""Pre-projection into the same 975x610 Albers USA space that us-atlas uses (d3.geoAlbersUsa().scale(1300).translate([487.5, 305]))."""
import math

EPS = 1e-6


class ConicEqualArea:
    def __init__(self, parallels, rotate_lon, center, scale, translate):
        y0, y1 = (math.radians(p) for p in parallels)
        sy0 = math.sin(y0)
        self.n = n = (sy0 + math.sin(y1)) / 2
        self.c = c = 1 + sy0 * (2 * n - sy0)
        self.r0 = math.sqrt(c) / n
        self.rot = rotate_lon
        self.k = scale
        cx, cy = self._raw(math.radians(center[0]), math.radians(center[1]))
        self.dx = translate[0] - scale * cx
        self.dy = translate[1] + scale * cy

    def _raw(self, lam, phi):
        r = math.sqrt(self.c - 2 * self.n * math.sin(phi)) / self.n
        x = lam * self.n
        return r * math.sin(x), self.r0 - r * math.cos(x)

    def __call__(self, lon, lat):
        lam = math.radians(((lon + self.rot + 180) % 360) - 180)
        x, y = self._raw(lam, math.radians(lat))
        return self.k * x + self.dx, self.dy - self.k * y


class AlbersUsa:
    """Composite projection: lower 48, Alaska (scaled 0.35) and Hawaii insets, as in d3-geo."""
    def __init__(self, k=1300.0, tx=487.5, ty=305.0):
        self.lower48 = ConicEqualArea((29.5, 45.5), 96, (-0.6, 38.7), k, (tx, ty))
        self.alaska = ConicEqualArea((55, 65), 154, (-2, 58.5), k * 0.35, (tx - 0.307 * k, ty + 0.201 * k))
        self.hawaii = ConicEqualArea((8, 18), 157, (-3, 19.9), k, (tx - 0.205 * k, ty + 0.212 * k))
        self.k, self.tx, self.ty = k, tx, ty

    def __call__(self, lon, lat):
        k, x, y = self.k, self.tx, self.ty
        # d3 picks the sub-projection by where the point lands in the lower-48 frame
        px, py = self.lower48(lon, lat)
        ny = (py - y) / k
        nx = (px - x) / k
        if 0.120 - EPS < ny < 0.234 + EPS and -0.425 - EPS < nx < -0.214 + EPS:
            return self.alaska(lon, lat)
        if 0.166 - EPS < ny < 0.234 + EPS and -0.214 - EPS < nx < -0.115 + EPS:
            return self.hawaii(lon, lat)
        return px, py

    def by_state(self, st):
        return self.alaska if st == "AK" else (self.hawaii if st == "HI" else self.lower48)
