/* Reader for the Minnesota ballot map files. Plain functions, no library, and nothing newer than every browser has.

   Every file is TopoJSON on a grid of 0.00001 degree: "arcs" are the lines (each delta-encoded), and a shape's
   "arcs" name the lines its rings are made of (a negative number n means line ~n walked backwards).

     MNGeo.open(json)                        a parsed file, made ready (its lines decoded once); returns the same object
     MNGeo.candidates(index, lon, lat)       [{county: "123", i: 17}, ...]: the precincts whose box holds the point
     MNGeo.precinctAt(file, lon, lat, only)  {i, geometry, edge, near} or null. edge: metres to the precinct's nearest
                                             line; near: the other precincts within MNGeo.NEAR metres of the point.
                                             only: optional list of precinct numbers to try (from candidates)
     MNGeo.locate(index, lon, lat, getCounty, done)
                                             the whole walk. getCounty(id, cb) is the page's own loader and must call
                                             cb(parsed county file); done({county, i, geometry, edge, near}) or done(null)
     MNGeo.shapeAt(file, name, lon, lat)     {i, geometry, edge} or null, in any file (name: the object's name, which
                                             is the layer's kind: "house", "school", ...)
     MNGeo.schoolAt(precinct, lon, lat, getSchool, done)
                                             the school district at a point whose precinct is known (a third of
                                             precincts are split between districts). getSchool(id, cb) loads
                                             school/<id>.json; done(id) or done(null)
     MNGeo.polygons(file, geometry)          [polygon, ...], polygon = [ring, ...] (outer first), ring = [[lon, lat], ...]
                                             closed, for drawing
     MNGeo.outline(file, kind, id)           in a county file: the lines that are an outline of that kind ("house",
                                             "mcd", "ward" ...; see file.arcKinds), as [[lon, lat], ...] each; with id,
                                             only the outline of that one shape
     MNGeo.inside(file, geometry, lon, lat)  true or false

   A point within a few metres of a line can fall on either side of it; when edge is small, say so. */
var MNGeo = (function () {
  var NEAR = 30;

  function open(file) {
    var lines = [], a, arc, x, y, flat, k;
    if (file._lines) { return file; }
    for (a = 0; a < file.arcs.length; a++) {
      arc = file.arcs[a];
      x = 0;
      y = 0;
      flat = [];
      for (k = 0; k < arc.length; k++) {
        x += arc[k][0];
        y += arc[k][1];
        flat.push(x, y);
      }
      lines.push(flat);
    }
    file._lines = lines;
    return file;
  }

  function gridX(file, lon) { return (lon - file.transform.translate[0]) / file.transform.scale[0]; }
  function gridY(file, lat) { return (lat - file.transform.translate[1]) / file.transform.scale[1]; }
  function lonOf(file, x) { return x * file.transform.scale[0] + file.transform.translate[0]; }
  function latOf(file, y) { return y * file.transform.scale[1] + file.transform.translate[1]; }

  /* one ring as a flat list x0, y0, x1, y1 ... on the grid, without the closing point */
  function ring(file, refs) {
    var out = [], n, r, line, k, first = true;
    for (n = 0; n < refs.length; n++) {
      r = refs[n];
      line = file._lines[r >= 0 ? r : ~r];
      if (r >= 0) {
        for (k = first ? 0 : 2; k < line.length; k += 2) { out.push(line[k], line[k + 1]); }
      } else {
        for (k = line.length - (first ? 2 : 4); k >= 0; k -= 2) { out.push(line[k], line[k + 1]); }
      }
      first = false;
    }
    out.length = out.length - 2;
    return out;
  }

  /* a shape's polygons, each a list of rings (outer first); kept on the shape after the first call */
  function rings(file, geometry) {
    var polys, out = [], p, q, one;
    if (geometry._p) { return geometry._p; }
    open(file);
    polys = geometry.type === "MultiPolygon" ? geometry.arcs : (geometry.type === "Polygon" ? [geometry.arcs] : []);
    for (p = 0; p < polys.length; p++) {
      one = [];
      for (q = 0; q < polys[p].length; q++) { one.push(ring(file, polys[p][q])); }
      out.push(one);
    }
    geometry._p = out;
    return out;
  }

  function inRing(x, y, pts) {
    var inside = false, n = pts.length, xj = pts[n - 2], yj = pts[n - 1], k, xi, yi;
    for (k = 0; k < n; k += 2) {
      xi = pts[k];
      yi = pts[k + 1];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) { inside = !inside; }
      xj = xi;
      yj = yi;
    }
    return inside;
  }

  /* even-odd over every ring of the shape: holes and islands need no special care */
  function insideGrid(file, geometry, x, y) {
    var polys = rings(file, geometry), count = 0, p, q;
    for (p = 0; p < polys.length; p++) {
      for (q = 0; q < polys[p].length; q++) {
        if (inRing(x, y, polys[p][q])) { count++; }
      }
    }
    return count % 2 === 1;
  }

  function inside(file, geometry, lon, lat) {
    return insideGrid(file, geometry, gridX(file, lon), gridY(file, lat));
  }

  /* metres from a grid point to the shape's nearest line */
  function edgeGrid(file, geometry, x, y) {
    var polys = rings(file, geometry), c = Math.cos(latOf(file, y) * Math.PI / 180), best = Infinity;
    var p, q, pts, n, k, ax, ay, bx, by, dx, dy, dd, t, ex, ey, d, px = x * c;
    for (p = 0; p < polys.length; p++) {
      for (q = 0; q < polys[p].length; q++) {
        pts = polys[p][q];
        n = pts.length;
        ax = pts[n - 2] * c;
        ay = pts[n - 1];
        for (k = 0; k < n; k += 2) {
          bx = pts[k] * c;
          by = pts[k + 1];
          dx = bx - ax;
          dy = by - ay;
          dd = dx * dx + dy * dy;
          t = dd === 0 ? 0 : ((px - ax) * dx + (y - ay) * dy) / dd;
          if (t < 0) { t = 0; } else if (t > 1) { t = 1; }
          ex = px - (ax + t * dx);
          ey = y - (ay + t * dy);
          d = ex * ex + ey * ey;
          if (d < best) { best = d; }
          ax = bx;
          ay = by;
        }
      }
    }
    return Math.sqrt(best) * file.transform.scale[1] * 111320;
  }

  function candidates(index, lon, lat) {
    var out = [], bx = (lon - index.transform.translate[0]) / index.box_step, by = (lat - index.transform.translate[1]) / index.box_step;
    var c, id, b, i;
    for (c = 0; c < index.counties.length; c++) {
      id = index.counties[c].id;
      b = index.boxes[id];
      for (i = 0; i < b.length; i += 4) {
        if (b[i] - 0.5 <= bx && bx <= b[i + 2] + 0.5 && b[i + 1] - 0.5 <= by && by <= b[i + 3] + 0.5) {
          out.push({county: id, i: i / 4});
        }
      }
    }
    return out;
  }

  function byEdge(a, b) { return a.edge - b.edge; }

  function testOne(file, i, x, y) {
    var geometry = file.objects.precincts.geometries[i];
    return {i: i, geometry: geometry, edge: edgeGrid(file, geometry, x, y), inside: insideGrid(file, geometry, x, y)};
  }

  /* found: the first precinct holding the point; failing that, the nearest within NEAR metres (a point on a line) */
  function settle(hits) {
    var found = null, near = [], n, h;
    for (n = 0; n < hits.length; n++) {
      h = hits[n];
      if (found === null && h.inside) { found = h; } else if (h.edge <= NEAR) { near.push(h); }
    }
    if (found === null && near.length) {
      near.sort(byEdge);
      found = near.shift();
    }
    if (found === null) { return null; }
    found.near = near;
    return found;
  }

  function precinctAt(file, lon, lat, only) {
    var x, y, hits = [], n, total;
    open(file);
    x = gridX(file, lon);
    y = gridY(file, lat);
    if (only) {
      for (n = 0; n < only.length; n++) { hits.push(testOne(file, only[n], x, y)); }
    } else {
      total = file.objects.precincts.geometries.length;
      for (n = 0; n < total; n++) { hits.push(testOne(file, n, x, y)); }
    }
    return settle(hits);
  }

  function locate(index, lon, lat, getCounty, done) {
    var cands = candidates(index, lon, lat), order = [], by = {}, n, hits = [];
    for (n = 0; n < cands.length; n++) {
      if (!by[cands[n].county]) {
        by[cands[n].county] = [];
        order.push(cands[n].county);
      }
      by[cands[n].county].push(cands[n].i);
    }
    order.sort();
    function next(k) {
      if (k >= order.length) {
        done(settle(hits));
        return;
      }
      getCounty(order[k], function (file) {
        var x, y, m, h;
        open(file);
        x = gridX(file, lon);
        y = gridY(file, lat);
        for (m = 0; m < by[order[k]].length; m++) {
          h = testOne(file, by[order[k]][m], x, y);
          h.county = order[k];
          hits.push(h);
        }
        next(k + 1);
      });
    }
    next(0);
  }

  function shapeAt(file, name, lon, lat) {
    var list, x, y, n, g, bb;
    open(file);
    list = file.objects[name].geometries;
    x = gridX(file, lon);
    y = gridY(file, lat);
    for (n = 0; n < list.length; n++) {
      g = list[n];
      bb = g.bbox;
      if (!bb || lon < bb[0] || lon > bb[2] || lat < bb[1] || lat > bb[3]) { continue; }
      if (insideGrid(file, g, x, y)) { return {i: n, geometry: g, edge: edgeGrid(file, g, x, y)}; }
    }
    return null;
  }

  /* The school district at a point, given the point's precinct (its shape from a county file). A precinct that lies
     in one district and touches no other is answered at once; otherwise the districts it lies in, then the ones it
     only brushes, are tried against their own lines. getSchool(id, cb) is the page's loader for school/<id>.json and
     must call cb(parsed file). done(id) or done(null): in no school district (the airport), or too near a line to say. */
  function schoolAt(precinct, lon, lat, getSchool, done) {
    var p = precinct.properties, list = (p.school || []).concat(p.school_edge || []);
    if (list.length === 1 && !p.school_out) {
      done(list[0]);
      return;
    }
    function next(k) {
      if (k >= list.length) {
        done(null);
        return;
      }
      getSchool(list[k], function (file) {
        open(file);
        if (insideGrid(file, file.objects.school.geometries[0], gridX(file, lon), gridY(file, lat))) {
          done(list[k]);
        } else {
          next(k + 1);
        }
      });
    }
    next(0);
  }

  function polygons(file, geometry) {
    var polys = rings(file, geometry), out = [], p, q, k, pts, one, line;
    for (p = 0; p < polys.length; p++) {
      one = [];
      for (q = 0; q < polys[p].length; q++) {
        pts = polys[p][q];
        line = [];
        for (k = 0; k < pts.length; k += 2) { line.push([lonOf(file, pts[k]), latOf(file, pts[k + 1])]); }
        line.push([lonOf(file, pts[0]), latOf(file, pts[1])]);
        one.push(line);
      }
      out.push(one);
    }
    return out;
  }

  function has(value, id) {
    var n;
    if (value === id) { return true; }
    if (value && typeof value === "object") {
      for (n = 0; n < value.length; n++) { if (value[n] === id) { return true; } }
    }
    return false;
  }

  function outline(file, kind, id) {
    var bit = -1, out = [], n, a, k, line, pts, list, r, l;
    open(file);
    for (n = 0; n < file.arcKinds.length; n++) { if (file.arcKinds[n] === kind) { bit = 1 << n; } }
    if (bit < 0) { return out; }
    list = file.objects.precincts.geometries;
    for (a = 0; a < file._lines.length; a++) {
      if (!(file.arcMask[a] & bit)) { continue; }
      if (id !== undefined && id !== null) {             /* the shape on one side of the line and not on the other */
        r = file.arcSides[2 * a];
        l = file.arcSides[2 * a + 1];
        if ((r >= 0 && has(list[r].properties[kind], id)) === (l >= 0 && has(list[l].properties[kind], id))) { continue; }
      }
      pts = file._lines[a];
      line = [];
      for (k = 0; k < pts.length; k += 2) { line.push([lonOf(file, pts[k]), latOf(file, pts[k + 1])]); }
      out.push(line);
    }
    return out;
  }

  return {NEAR: NEAR, open: open, candidates: candidates, precinctAt: precinctAt, locate: locate, shapeAt: shapeAt,
          schoolAt: schoolAt, polygons: polygons, outline: outline, inside: inside};
}());
if (typeof module !== "undefined" && module.exports) { module.exports = MNGeo; }
