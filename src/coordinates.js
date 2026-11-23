export function pullAt(point, grid, width, height) {
  const rows = grid.length, cols = grid[0].length;
  const u = Math.max(0, Math.min(1, point.x / (width - 1))) * (cols - 1);
  const v = Math.max(0, Math.min(1, point.y / (height - 1))) * (rows - 1);
  const i = Math.min(cols - 2, Math.floor(u)), j = Math.min(rows - 2, Math.floor(v));
  const fx = u - i, fy = v - j;
  return [0, 1].map(k => (1-fy)*((1-fx)*grid[j][i][k] + fx*grid[j][i+1][k])
                         + fy*((1-fx)*grid[j+1][i][k] + fx*grid[j+1][i+1][k]));
}
