import { useEffect, useRef } from 'react';
import Phaser from 'phaser';
import type { MapResult, Placement } from '../../../packages/shared/types';

type Props = {
  map: MapResult;
  play: boolean;
  overlays: string[];
  zoom: number;
  stage: string;
  onSelect: (id: string) => void;
  onMove: (id: string, x: number, y: number) => void;
  onInteract: (text: string) => void;
};
const TILE = 16;
const COLORS = [0x76b5a0, 0xc8a277, 0x8c9cc6, 0xb58fba, 0xc6bd7a];
export function MapCanvas(props: Props) {
  const host = useRef<HTMLDivElement>(null);
  const current = useRef(props);
  current.current = props;
  const gameRef = useRef<Phaser.Game | null>(null);
  useEffect(() => {
    if (!host.current) return;
    const map = props.map;
    const assets = new Map(map.assets.map((a) => [a.id, a]));
    class Room extends Phaser.Scene {
      player!: Phaser.GameObjects.Sprite;
      debug!: Phaser.GameObjects.Graphics;
      labels: Phaser.GameObjects.Text[] = [];
      keys: any;
      walkDir = 'south';
      moving = false;
      lastOverlay = '';
      preload() {
        for (const a of map.assets)
          for (const [o, url] of Object.entries(a.orientationSprites))
            this.load.image(a.id + '_' + o, url);
        this.load.spritesheet('explorer', '/assets/player_walk.png', {
          frameWidth: 16,
          frameHeight: 24,
        });
        this.load.spritesheet('caretaker', '/assets/npc_walk.png', {
          frameWidth: 16,
          frameHeight: 24,
        });
      }
      create() {
        this.cameras.main.setBackgroundColor('#192229');
        const w = map.layout.width,
          h = map.layout.height;
        this.add
          .rectangle(
            (w * TILE) / 2,
            (h * TILE) / 2 + 6,
            (w - 1) * TILE,
            (h - 1) * TILE,
            0x080d12,
            0.4,
          )
          .setDepth(-50);
        for (let y = 1; y < h - 1; y++)
          for (let x = 1; x < w - 1; x++)
            this.add
              .image(x * TILE, y * TILE, 'wood_floor_south')
              .setOrigin(0)
              .setDepth(-40)
              .setTint((x + y) % 3 === 0 ? 0xeee4cd : 0xffffff);
        for (let x = 1; x < w - 1; x++)
          this.add
            .image(x * TILE, 8, 'north_wall_south')
            .setOrigin(0)
            .setDepth(-20);
        const border = this.add.graphics().setDepth(-10);
        border.fillStyle(0x3a3534, 1);
        border.fillRect(12, 8, 5, (h - 1) * 16 - 8);
        border.fillRect((w - 1) * 16 - 1, 8, 5, (h - 1) * 16 - 8);
        border.fillStyle(0x5b4738, 1);
        border.fillRect(16, (h - 1) * 16, (w - 2) * 16, 4);
        this.add
          .image(map.layout.exit.x * TILE, 30, 'door_south')
          .setOrigin(0.5, 1)
          .setDepth(-5);
        border.fillStyle(0xcfa878);
        border.fillRect((map.layout.entrance.x - 1) * 16, (h - 1) * 16, 32, 4);
        const visibleFurniture = !['Architecture', 'Zones'].includes(current.current.stage);
        for (const p of map.layout.placements) {
          const a = assets.get(p.assetId)!;
          const parent = p.parentId
            ? map.layout.placements.find((q) => q.id === p.parentId)
            : undefined;
          const image = this.add
            .image(
              (p.x + a.footprint.width / 2) * TILE,
              (p.y + a.footprint.height - p.visualLift) * TILE,
              a.id + '_' + p.orientation,
            )
            .setOrigin(a.anchor.x / a.spriteSize.width, a.anchor.y / a.spriteSize.height);
          const depth =
            a.renderLayer === 'floor_decoration'
              ? -25
              : a.renderLayer === 'wall_decoration'
                ? -1
                : parent
                  ? (parent.y + assets.get(parent.assetId)!.footprint.height) * TILE + 1
                  : (p.y + a.footprint.height) * TILE;
          image
            .setDepth(depth + a.depthOffset)
            .setVisible(visibleFurniture)
            .setInteractive({ draggable: true, pixelPerfect: true });
          image.on('pointerdown', () => current.current.onSelect(p.id));
          image.on('drag', (_: unknown, x: number, y: number) => {
            if (!current.current.play) {
              image.setPosition(x, y);
              image.setAlpha(0.7);
            }
          });
          image.on('dragend', () => {
            if (!current.current.play) {
              const nx = Math.round((image.x / TILE - a.footprint.width / 2) * 2) / 2;
              const ny = Math.round((image.y / TILE - a.footprint.height + p.visualLift) * 2) / 2;
              image
                .setPosition(
                  (p.x + a.footprint.width / 2) * TILE,
                  (p.y + a.footprint.height - p.visualLift) * TILE,
                )
                .setAlpha(1);
              current.current.onMove(p.id, nx, ny);
            }
          });
        }
        for (const [row, dir] of ['south', 'west', 'east', 'north'].entries())
          this.anims.create({
            key: 'walk_' + dir,
            frames: this.anims.generateFrameNumbers('explorer', {
              start: row * 3,
              end: row * 3 + 2,
            }),
            frameRate: 8,
            repeat: -1,
          });
        for (const n of map.validation.npcs)
          this.add
            .sprite(n.x * TILE, (n.y + 0.25) * TILE, 'caretaker', 0)
            .setOrigin(0.5, 1)
            .setDepth(n.y * TILE)
            .setVisible(visibleFurniture);
        this.player = this.add
          .sprite(map.layout.entrance.x * TILE, map.layout.entrance.y * TILE, 'explorer', 0)
          .setOrigin(0.5, 1)
          .setDepth(map.layout.entrance.y * TILE);
        this.debug = this.add.graphics().setDepth(10000);
        this.keys = this.input.keyboard!.addKeys({
          up: 'W',
          down: 'S',
          left: 'A',
          right: 'D',
          up2: 'UP',
          down2: 'DOWN',
          left2: 'LEFT',
          right2: 'RIGHT',
          interact: 'E',
        });
        this.input.keyboard!.enabled = false;
        this.game.canvas.setAttribute('tabindex', '0');
        this.game.canvas.setAttribute(
          'aria-label',
          'Playable interior. Click to focus, use WASD or arrow keys to walk, E to interact.',
        );
        this.game.canvas.addEventListener('focus', () => {
          this.input.keyboard!.enabled = true;
        });
        this.game.canvas.addEventListener('blur', () => {
          this.input.keyboard!.enabled = false;
          this.input.keyboard!.resetKeys();
        });
        this.input.on('pointerdown', () => this.game.canvas.focus());
        this.input.keyboard!.on('keydown-E', (event: KeyboardEvent) => {
          if (event.repeat || !current.current.play) return;
          const npc = map.validation.npcs.find(
            (n) =>
              Math.hypot(n.x - this.player.x / TILE, n.y - this.player.y / TILE) <=
              n.interactionRadius,
          );
          current.current.onInteract(
            npc ? `${npc.name}: ${npc.dialogue}` : 'Move closer to the caretaker to talk.',
          );
        });
        this.scale.on('resize', () => this.fit());
        this.fit();
        this.registry.set('ready', true);
        this.game.canvas.dataset.ready = 'true';
      }
      fit() {
        const p = current.current;
        const fit = Math.min(
          (this.scale.width - 64) / (map.layout.width * TILE),
          (this.scale.height - 64) / (map.layout.height * TILE),
        );
        this.cameras.main.setZoom(Math.max(0.5, fit) * p.zoom);
        if (p.play) this.cameras.main.startFollow(this.player, true, 0.1, 0.1);
        else {
          this.cameras.main.stopFollow();
          this.cameras.main.centerOn((map.layout.width * TILE) / 2, (map.layout.height * TILE) / 2);
        }
      }
      blocked(x: number, y: number) {
        const r = map.layout.playerSize / 2;
        const tx = x / TILE,
          ty = y / TILE;
        if (
          tx - r < 1 ||
          tx + r > map.layout.width - 1 ||
          ty - r < 2 ||
          ty + r > map.layout.height - 1
        )
          return true;
        return map.validation.collisions.some(
          (b) => tx - r < b.x + b.width && tx + r > b.x && ty - r < b.y + b.height && ty + r > b.y,
        );
      }
      update(_: number, delta: number) {
        const p = current.current;
        this.player.setVisible(p.play);
        const overlay = JSON.stringify([p.overlays, p.zoom, p.play, p.stage]);
        if (overlay !== this.lastOverlay) {
          this.lastOverlay = overlay;
          this.drawDebug();
          this.fit();
        }
        if (!p.play) return;
        let dx =
          (this.keys.right.isDown || this.keys.right2.isDown ? 1 : 0) -
          (this.keys.left.isDown || this.keys.left2.isDown ? 1 : 0);
        let dy =
          (this.keys.down.isDown || this.keys.down2.isDown ? 1 : 0) -
          (this.keys.up.isDown || this.keys.up2.isDown ? 1 : 0);
        const length = Math.hypot(dx, dy);
        if (length) {
          dx /= length;
          dy /= length;
          this.walkDir =
            Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'east' : 'west') : dy > 0 ? 'south' : 'north';
          this.player.play('walk_' + this.walkDir, true);
        } else {
          this.player.anims.stop();
          this.player.setFrame(['south', 'west', 'east', 'north'].indexOf(this.walkDir) * 3);
        }
        const step = (56 * Math.min(delta, 50)) / 1000;
        const steps = Math.max(1, Math.ceil(step / 2));
        for (let i = 0; i < steps; i++) {
          const nx = this.player.x + (dx * step) / steps,
            ny = this.player.y + (dy * step) / steps;
          if (!this.blocked(nx, this.player.y)) this.player.x = nx;
          if (!this.blocked(this.player.x, ny)) this.player.y = ny;
        }
        this.player.setDepth(this.player.y + 0.5);
        this.game.canvas.dataset.playerX = String(this.player.x / TILE);
        this.game.canvas.dataset.playerY = String(this.player.y / TILE);
      }
      drawDebug() {
        const enabled = new Set(current.current.overlays);
        if (current.current.stage === 'Zones') enabled.add('Zones');
        const d = this.debug;
        d.clear();
        this.labels.forEach((t) => t.destroy());
        this.labels = [];
        const rect = (x: number, y: number, w: number, h: number, color: number, alpha = 0.15) => {
          d.fillStyle(color, alpha);
          d.fillRect(x * 16, y * 16, w * 16, h * 16);
          d.lineStyle(0.6, color, 0.8);
          d.strokeRect(x * 16, y * 16, w * 16, h * 16);
        };
        const dot = (x: number, y: number, color = 0xffdf91) => {
          d.fillStyle(color);
          d.fillCircle(x * 16, y * 16, 1.8);
        };
        const label = (x: number, y: number, text: string, color = '#cde9dd') => {
          this.labels.push(
            this.add
              .text(x * 16, y * 16, text, {
                fontSize: '6px',
                fontFamily: 'monospace',
                color,
                backgroundColor: '#17232c',
              })
              .setDepth(10001),
          );
        };
        if (enabled.has('Grid')) {
          d.lineStyle(0.4, 0xe0d9c4, 0.25);
          for (let x = 1; x < map.layout.width; x++) {
            d.lineBetween(x * 16, 32, x * 16, (map.layout.height - 1) * 16);
            label(x, 1.7, String(x));
          }
          for (let y = 2; y < map.layout.height; y++) {
            d.lineBetween(16, y * 16, (map.layout.width - 1) * 16, y * 16);
            label(0.4, y, String(y));
          }
        }
        if (enabled.has('Boundaries'))
          rect(1, 2, map.layout.width - 2, map.layout.height - 3, 0xf5d490, 0.02);
        if (enabled.has('Zones'))
          Object.entries(map.layout.zones).forEach(([id, z], i) => {
            rect(z.x, z.y, z.width, z.height, COLORS[i % COLORS.length]);
            label(
              z.x + 0.2,
              z.y + 0.2,
              map.scene.zones.find((a: any) => a.id === id)?.purpose || id,
            );
          });
        if (enabled.has('Collision'))
          map.validation.collisions.forEach((b) =>
            rect(b.x, b.y, b.width, b.height, 0xf0837d, 0.3),
          );
        if (enabled.has('Occupied cells'))
          for (let y = 2; y < map.layout.height - 1; y++)
            for (let x = 1; x < map.layout.width - 1; x++)
              if (
                map.validation.collisions.some(
                  (b) => x < b.x + b.width && x + 1 > b.x && y < b.y + b.height && y + 1 > b.y,
                )
              )
                rect(x, y, 1, 1, 0xe89f66, 0.2);
        if (enabled.has('Walkable cells'))
          map.validation.walkable.forEach((p) => rect(p.x, p.y, 1, 1, 0x67bea4, 0.12));
        if (enabled.has('Circulation'))
          map.layout.circulation.forEach((p) => rect(p.x - 0.5, p.y - 0.5, 1, 1, 0x7aabd6, 0.25));
        if (enabled.has('Paths')) {
          d.lineStyle(0.7, 0xe4c17c, 0.8);
          map.validation.paths.forEach((path) => {
            for (let i = 1; i < path.points.length; i++)
              d.lineBetween(
                path.points[i - 1].x * 16,
                path.points[i - 1].y * 16,
                path.points[i].x * 16,
                path.points[i].y * 16,
              );
          });
        }
        if (enabled.has('Interactions'))
          map.validation.interactions.forEach((p) => {
            dot(p.x, p.y);
            label(p.x + 0.1, p.y, 'E');
          });
        for (const p of map.layout.placements) {
          const a = assets.get(p.assetId)!;
          const x = p.x + a.footprint.width / 2,
            y = p.y + a.footprint.height - p.visualLift;
          if (enabled.has('Sprite anchors')) dot(x, y);
          if (enabled.has('Visual bounds'))
            rect(
              x - a.anchor.x / 16,
              y - a.anchor.y / 16,
              a.spriteSize.width / 16,
              a.spriteSize.height / 16,
              0xd8a8dc,
              0.05,
            );
          if (enabled.has('Depth')) label(x, y, `${Math.round(y * 16)}`);
        }
        map.scene.groups.forEach((g: any, i: number) => {
          const ps = map.layout.placements.filter((p) => p.groupId === g.id);
          const anchor = ps.find((p) => p.id === g.anchorId);
          if (anchor && enabled.has('Group anchors'))
            dot(anchor.x + assets.get(anchor.assetId)!.footprint.width / 2, anchor.y, 0xf1a55f);
          if (ps.length && enabled.has('Groups')) {
            const x = Math.min(...ps.map((p) => p.x)),
              y = Math.min(...ps.map((p) => p.y)),
              r = Math.max(...ps.map((p) => p.x + assets.get(p.assetId)!.footprint.width)),
              b = Math.max(...ps.map((p) => p.y + assets.get(p.assetId)!.footprint.height));
            rect(x, y, r - x, b - y, COLORS[i % COLORS.length], 0.06);
          }
          if (enabled.has('Relationships'))
            for (const o of g.objects) {
              const from = ps.find((p) => p.id === o.id);
              if (!from) continue;
              for (const rel of o.relations) {
                const to = ps.find((p) => p.id === rel.target);
                if (to) {
                  d.lineStyle(0.6, 0xf4d5a4);
                  d.lineBetween(
                    (from.x + 0.5) * 16,
                    (from.y + 0.5) * 16,
                    (to.x + 0.5) * 16,
                    (to.y + 0.5) * 16,
                  );
                }
              }
            }
        });
        if (enabled.has('Failures'))
          map.validation.failures.forEach((f: any, i: number) =>
            label(1, 2 + i * 0.5, f.message, '#ff9d96'),
          );
      }
    }
    let game: Phaser.Game | undefined;
    const resize = new ResizeObserver(() => {
      if (host.current && game && host.current.clientWidth > 0 && host.current.clientHeight > 0)
        game.scale.resize(host.current.clientWidth, host.current.clientHeight);
    });
    // Defer boot until React's effect is committed; StrictMode may clean up before boot.
    const frame = requestAnimationFrame(() => {
      if (!host.current) return;
      game = new Phaser.Game({
        type: Phaser.CANVAS,
        parent: host.current,
        width: host.current.clientWidth,
        height: host.current.clientHeight,
        backgroundColor: '#192229',
        pixelArt: true,
        roundPixels: true,
        antialias: false,
        scene: Room,
        scale: { mode: Phaser.Scale.NONE },
        // The focusable canvas is the only child. Keep Phaser's key capture off the page.
        input: { keyboard: { target: host.current } },
        audio: { noAudio: true },
      });
      gameRef.current = game;
      resize.observe(host.current);
    });
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      game?.destroy(true);
      gameRef.current = null;
    };
  }, [props.map, props.stage]);
  return <div ref={host} className="map-canvas" />;
}
