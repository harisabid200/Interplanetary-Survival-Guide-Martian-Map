// Explicit spherical equirectangular equations, matching the actual DEM CRS.
// No EPSG:4326/3857 aliases, Earth radius or Earth distance helpers.
export function projectionFunctions(crs) {
  const radians = Math.PI / 180;
  const xScale = crs.radius_m * Math.cos(crs.standard_parallel_deg * radians) * radians;
  const yScale = crs.radius_m * radians;
  return {
    forward: ([lon, lat]) => [(lon - crs.central_meridian_deg) * xScale, lat * yScale],
    inverse: ([x, y]) => [x / xScale + crs.central_meridian_deg, y / yScale],
  };
}

export function cellAt([x, y], region) {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  const [a, b, c, d, e, f] = region.affine;
  if (b !== 0 || d !== 0 || a <= 0 || e >= 0) throw new Error('Unsupported raster transform');
  const col = Math.floor((x - c) / a) + 0;
  const row = Math.floor((y - f) / e) + 0;
  // West/north edges included; east/south excluded. Never clamp outside data.
  return row >= 0 && col >= 0 && row < region.height && col < region.width
    ? {row, col, index: row * region.width + col} : null;
}

export function cellCenter(row, col, region) {
  const [a, , c, , e, f] = region.affine;
  return [c + (col + .5) * a, f + (row + .5) * e];
}

export function sampleAt(coordinate, region, grids) {
  const cell = cellAt(coordinate, region);
  if (!cell) return {status: 'outside'};
  if (!grids.valid[cell.index] || !Number.isFinite(grids.elevation[cell.index])) return {status: 'nodata', ...cell};
  const slope = grids.slopeValid[cell.index] && Number.isFinite(grids.slope[cell.index]) ? grids.slope[cell.index] : null;
  const center = cellCenter(cell.row, cell.col, region);
  return {status: 'valid', ...cell, center, lonlat: projectionFunctions(region.crs).inverse(center),
    elevation: grids.elevation[cell.index], slope};
}
