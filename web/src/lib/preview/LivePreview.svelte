<script lang="ts">
  import { onMount } from 'svelte';
  import { connect, type ReconnectingSocket } from '../../api/ws';
  import { decodeFrame } from './frameDecoder';

  let {
    fps = 20,
    ledLook = $bindable(false),
    maxWidth = 512,
    dimToBrightness = true,
  }: { fps?: number; ledLook?: boolean; maxWidth?: number; dimToBrightness?: boolean } = $props();

  let canvas: HTMLCanvasElement;
  let wrapper: HTMLDivElement;
  let off: HTMLCanvasElement | null = null;
  let size = $state({ w: 64, h: 64 });
  let connected = $state(false);
  let seq = $state(0);
  let brightness = $state(100);
  let socket: ReconnectingSocket | null = null;
  let scale = $state(4);

  function computeScale() {
    const avail = Math.min(maxWidth, wrapper?.clientWidth ?? maxWidth);
    const maxH = Math.min(window.innerHeight * 0.5, 512);
    scale = Math.max(1, Math.floor(Math.min(avail / size.w, maxH / size.h)));
  }

  function draw() {
    if (!off) return;
    const ctx = canvas.getContext('2d')!;
    canvas.width = size.w * scale;
    canvas.height = size.h * scale;
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const alpha = dimToBrightness ? 0.35 + 0.65 * Math.max(0, Math.min(1, brightness / 100)) : 1;
    ctx.globalAlpha = alpha;
    if (ledLook && scale >= 3) {
      const src = off.getContext('2d')!.getImageData(0, 0, size.w, size.h).data;
      const r = scale * 0.42;
      for (let y = 0; y < size.h; y++) {
        for (let x = 0; x < size.w; x++) {
          const i = (y * size.w + x) * 4;
          if (src[i] + src[i + 1] + src[i + 2] === 0) continue;
          ctx.fillStyle = `rgb(${src[i]},${src[i + 1]},${src[i + 2]})`;
          ctx.beginPath();
          ctx.arc(x * scale + scale / 2, y * scale + scale / 2, r, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    } else {
      ctx.drawImage(off, 0, 0, canvas.width, canvas.height);
    }
    ctx.globalAlpha = 1;
  }

  $effect(() => {
    ledLook;
    scale;
    brightness;
    draw();
  });

  onMount(() => {
    computeScale();
    const ro = new ResizeObserver(() => {
      computeScale();
    });
    ro.observe(wrapper);
    socket = connect(
      `/api/ws/preview?fps=${fps}`,
      {
        onOpen: () => (connected = true),
        onClose: () => (connected = false),
        onMessage: async (ev) => {
          const frame = await decodeFrame(ev.data as ArrayBuffer);
          if (!frame) return;
          if (frame.width !== size.w || frame.height !== size.h) {
            size = { w: frame.width, h: frame.height };
            off = null;
            computeScale();
          }
          if (!off) {
            off = document.createElement('canvas');
            off.width = frame.width;
            off.height = frame.height;
          }
          const octx = off.getContext('2d')!;
          if (frame.bitmap instanceof ImageData) octx.putImageData(frame.bitmap, 0, 0);
          else {
            octx.drawImage(frame.bitmap, 0, 0);
            frame.bitmap.close();
          }
          seq = frame.seq;
          brightness = frame.brightness;
          draw();
        },
      },
      true,
    );
    const onVis = () =>
      socket?.send(JSON.stringify({ type: 'fps', value: document.hidden ? 2 : fps }));
    document.addEventListener('visibilitychange', onVis);
    return () => {
      ro.disconnect();
      document.removeEventListener('visibilitychange', onVis);
      socket?.close();
    };
  });
</script>

<div class="preview" bind:this={wrapper}>
  <div class="frame" style="width:{size.w * scale}px;height:{size.h * scale}px">
    <canvas bind:this={canvas}></canvas>
    {#if !connected}
      <div class="overlay">disconnected</div>
    {:else if seq === 0}
      <div class="overlay"><span class="spin"></span></div>
    {/if}
  </div>
  <div class="meta muted small">
    {size.w}×{size.h} · {scale}× · brightness {brightness}%
  </div>
</div>

<style>
  .preview {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
  }
  .frame {
    position: relative;
    background: #000;
    border-radius: 6px;
    border: 6px solid #1a1d27;
    box-shadow:
      0 10px 40px rgba(0, 0, 0, 0.5),
      inset 0 0 0 1px #000;
    max-width: 100%;
  }
  canvas {
    display: block;
    image-rendering: pixelated;
    width: 100%;
    height: 100%;
  }
  .overlay {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    color: var(--text-dim);
    background: rgba(0, 0, 0, 0.55);
    font-size: 0.9rem;
  }
</style>
