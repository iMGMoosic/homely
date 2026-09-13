export interface DecodedFrame {
  seq: number;
  width: number;
  height: number;
  brightness: number;
  bitmap: ImageBitmap | ImageData;
}

/** Header: u8 version, u8 encoding, u16 w, u16 h, u32 seq, u8 brightness (big endian). */
export async function decodeFrame(buf: ArrayBuffer): Promise<DecodedFrame | null> {
  const view = new DataView(buf);
  if (buf.byteLength < 11 || view.getUint8(0) !== 1) return null;
  const encoding = view.getUint8(1);
  const width = view.getUint16(2);
  const height = view.getUint16(4);
  const seq = view.getUint32(6);
  const brightness = view.getUint8(10);
  const payload = new Uint8Array(buf, 11);
  if (encoding === 1) {
    const rgba = new Uint8ClampedArray(width * height * 4);
    for (let i = 0, j = 0; i < payload.length; i += 3, j += 4) {
      rgba[j] = payload[i];
      rgba[j + 1] = payload[i + 1];
      rgba[j + 2] = payload[i + 2];
      rgba[j + 3] = 255;
    }
    return { seq, width, height, brightness, bitmap: new ImageData(rgba, width, height) };
  }
  const blob = new Blob([payload], { type: 'image/png' });
  const bitmap = await createImageBitmap(blob);
  return { seq, width, height, brightness, bitmap };
}
