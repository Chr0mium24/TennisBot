export interface Vector2 {
  x: number;
  y: number;
}

export interface Vector3 {
  x: number;
  y: number;
  z: number;
}

export interface ImageSize {
  widthPx: number;
  heightPx: number;
}

export interface PixelBoundingBox {
  xPx: number;
  yPx: number;
  widthPx: number;
  heightPx: number;
}

export interface Matrix3x3 {
  values: [number, number, number, number, number, number, number, number, number];
  storage: 'row-major';
}

export interface Matrix3x4 {
  values: [number, number, number, number, number, number, number, number, number, number, number, number];
  storage: 'row-major';
}
