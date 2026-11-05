import { Billboard, RoundedBox, useGLTF } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import { useEffect, useLayoutEffect, useMemo, useRef, type ReactNode } from "react";
import * as THREE from "three";
import type { Category } from "@/api/types";

type Vec3 = [number, number, number];

/** glTF로 바꾸려면 여기에 카테고리별 파일 경로만 넣는다. 예: 음료: "/models/fridge.glb" */
export const FIXTURE_MODELS: Partial<Record<Category, string>> = {};

export const noRaycast = () => null;

const PALETTE = ["#d9695f", "#e6c15c", "#6fb3a6", "#4f86b8", "#d99a3d", "#9dbf6b", "#efece2", "#d98a5f", "#7a8fa6", "#c4564b", "#3f7f6b", "#e8dcc0"];
const paletteColor = (index: number) => PALETTE[(index * 7 + 3) % PALETTE.length];

const standard = (color: string, extra: THREE.MeshStandardMaterialParameters = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.7, metalness: 0.04, ...extra });

const METAL = standard("#8d9490", { roughness: 0.35, metalness: 0.75 });
const DARK_METAL = standard("#2c312e", { roughness: 0.45, metalness: 0.55 });
const RAIL = standard("#d9dcd6", { roughness: 0.4, metalness: 0.3 });
const PRICE_TAG = new THREE.MeshBasicMaterial({ color: "#f4f4ee", toneMapped: false });
const LAMP = new THREE.MeshBasicMaterial({ color: "#ffffff", toneMapped: false });
const GLASS = new THREE.MeshStandardMaterial({ color: "#d6ecff", transparent: true, opacity: 0.12, roughness: 0.1, metalness: 0, envMapIntensity: 0.3, depthWrite: false });

export function Box({ size, position, material, shadow = true, rounded = 0, rotation }: {
  size: Vec3;
  position: Vec3;
  material: THREE.Material;
  shadow?: boolean;
  rounded?: number;
  rotation?: Vec3;
}) {
  if (rounded > 0) {
    return (
      <RoundedBox
        args={size}
        radius={rounded}
        smoothness={2}
        position={position}
        rotation={rotation}
        material={material}
        castShadow={shadow}
        receiveShadow
        raycast={noRaycast}
      />
    );
  }
  return (
    <mesh position={position} rotation={rotation} material={material} castShadow={shadow} receiveShadow raycast={noRaycast}>
      <boxGeometry args={size} />
    </mesh>
  );
}

/** 글자가 들어간 표지판. 항상 카메라를 향한다. 글꼴을 불러온 뒤 한 번 더 그린다. */
export function Plaque({ text, size, position, background = "#23251f", color = "#f1f2ec", fontScale = 0.6 }: {
  text: string;
  size: [number, number];
  position: Vec3;
  background?: string;
  color?: string;
  fontScale?: number;
}) {
  const invalidate = useThree((state) => state.invalidate);
  const gl = useThree((state) => state.gl);
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 768;
    canvas.height = Math.max(64, Math.round((768 * size[1]) / size[0]));
    const canvasTexture = new THREE.CanvasTexture(canvas);
    canvasTexture.colorSpace = THREE.SRGBColorSpace;
    canvasTexture.anisotropy = Math.min(8, gl.capabilities.getMaxAnisotropy());
    return canvasTexture;
  }, [size, gl]);

  useEffect(() => {
    const font = `700 ${Math.round((texture.image as HTMLCanvasElement).height * fontScale)}px 'IBM Plex Sans KR', 'Malgun Gothic', sans-serif`;
    const draw = () => {
      const canvas = texture.image as HTMLCanvasElement;
      const context = canvas.getContext("2d");
      if (!context) return;
      context.fillStyle = background;
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = color;
      context.font = font;
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.fillText(text, canvas.width / 2, canvas.height * 0.54);
      texture.needsUpdate = true;
      invalidate();
    };
    draw();
    document.fonts?.load(font, text).then(draw).catch(() => undefined);
  }, [texture, text, background, color, fontScale, invalidate]);

  return (
    <Billboard position={position}>
      <mesh raycast={noRaycast}>
        <planeGeometry args={size} />
        <meshBasicMaterial map={texture} toneMapped={false} />
      </mesh>
    </Billboard>
  );
}

interface BatchItem {
  position: Vec3;
  size: Vec3;
  color: string;
  rotation?: Vec3;
}

function centered(geometry: THREE.BufferGeometry) {
  geometry.computeBoundingBox();
  const box = geometry.boundingBox!;
  geometry.translate(0, -(box.max.y + box.min.y) / 2, 0);
  return geometry;
}

export const UNIT_BOX = new THREE.BoxGeometry(1, 1, 1);
const CAN = new THREE.CylinderGeometry(1, 1, 1, 14);
const CUP = new THREE.CylinderGeometry(1, 0.72, 1, 14);
const PRISM = new THREE.CylinderGeometry(1, 1, 1, 3);
const BOTTLE = centered(new THREE.LatheGeometry(
  [[0, 0], [0.92, 0], [1, 0.06], [1, 0.6], [0.82, 0.7], [0.42, 0.82], [0.38, 0.88], [0.38, 1], [0, 1]].map(([x, y]) => new THREE.Vector2(x, y)),
  14,
));
const BAG = (() => {
  // 가운데가 부풀고 위아래가 눌린 과자 봉지 모양
  const geometry = new THREE.BoxGeometry(1, 1, 1, 6, 8, 2);
  const position = geometry.attributes.position;
  for (let index = 0; index < position.count; index++) {
    const x = position.getX(index);
    const y = position.getY(index);
    const puff = (1 - (2 * y) ** 4) * (1 - (2 * x) ** 4 * 0.6);
    position.setZ(index, position.getZ(index) * (0.2 + puff * 0.8));
  }
  geometry.computeVertexNormals();
  return geometry;
})();

const PRODUCT_MATERIAL = new THREE.MeshStandardMaterial({ roughness: 0.45, metalness: 0.03 });

/** 상품은 수백 개라 모양별로 하나의 인스턴스 메시로 그린다. */
export function Batch({ geometry, items, material = PRODUCT_MATERIAL }: {
  geometry: THREE.BufferGeometry;
  items: BatchItem[];
  material?: THREE.Material;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const matrix = new THREE.Matrix4();
    const color = new THREE.Color();
    const euler = new THREE.Euler();
    const quaternion = new THREE.Quaternion();
    items.forEach((item, index) => {
      quaternion.setFromEuler(euler.set(...(item.rotation ?? [0, 0, 0])));
      matrix.compose(new THREE.Vector3(...item.position), quaternion, new THREE.Vector3(...item.size));
      mesh.setMatrixAt(index, matrix);
      mesh.setColorAt(index, color.set(item.color));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [items]);
  return <instancedMesh ref={meshRef} args={[geometry, material, items.length]} castShadow raycast={noRaycast} />;
}

/** 선반 앞의 가격표 줄 */
function PriceRail({ width, y, z, count }: { width: number; y: number; z: number; count: number }) {
  const tags = useMemo<BatchItem[]>(
    () => Array.from({ length: count }, (_, index) => ({
      position: [-width / 2 + ((index + 0.5) * width) / count, y, z + 0.012] as Vec3,
      size: [0.13, 0.05, 0.01] as Vec3,
      color: "#f4f4ee",
    })),
    [width, y, z, count],
  );
  return (
    <>
      <Box size={[width, 0.06, 0.02]} position={[0, y, z]} material={RAIL} shadow={false} />
      <Batch geometry={UNIT_BOX} items={tags} material={PRICE_TAG} />
    </>
  );
}

const FRIDGE_DOORS = [-1.75, 0, 1.75];
const FRIDGE_SHELVES = [0.42, 0.92, 1.42, 1.92];

function BeverageFridge({ body }: { body: THREE.MeshStandardMaterial }) {
  const products = useMemo(() => {
    const bottles: BatchItem[] = [];
    const labels: BatchItem[] = [];
    const caps: BatchItem[] = [];
    const cans: BatchItem[] = [];
    let index = 0;
    FRIDGE_DOORS.forEach((doorX) => {
      FRIDGE_SHELVES.forEach((y, row) => {
        for (let column = 0; column < 6; column++) {
          const x = doorX - 0.65 + column * 0.26;
          for (const z of [0.2, -0.12]) {
            const color = paletteColor(index++);
            if (row === 2) {
              cans.push({ position: [x, y + 0.13, z], size: [0.085, 0.24, 0.085], color });
              cans.push({ position: [x, y + 0.255, z], size: [0.07, 0.012, 0.07], color: "#c9ced0" });
            } else {
              bottles.push({ position: [x, y + 0.2, z], size: [0.068, 0.4, 0.068], color });
              labels.push({ position: [x, y + 0.13, z], size: [0.071, 0.1, 0.071], color: "#f1efe6" });
              caps.push({ position: [x, y + 0.405, z], size: [0.031, 0.03, 0.031], color: paletteColor(index + 4) });
            }
          }
        }
      });
    });
    return { bottles, labels, caps, cans };
  }, []);
  const back = useMemo(() => standard("#eaf5ff", { emissive: "#d6ecff", emissiveIntensity: 0.75 }), []);
  const shelf = useMemo(() => standard("#cdd6da", { roughness: 0.4, metalness: 0.3 }), []);

  return (
    <>
      <Box size={[5.4, 0.3, 1.1]} position={[0, 0.15, 0]} material={body} rounded={0.03} />
      <Box size={[5.4, 0.34, 1.1]} position={[0, 2.53, 0]} material={body} rounded={0.03} />
      <Box size={[0.1, 2.7, 1.1]} position={[-2.65, 1.35, 0]} material={body} />
      <Box size={[0.1, 2.7, 1.1]} position={[2.65, 1.35, 0]} material={body} />
      <Box size={[5.2, 2.05, 0.06]} position={[0, 1.33, -0.5]} material={back} shadow={false} />
      <Box size={[5, 0.02, 0.02]} position={[0, 0.1, 0.56]} material={DARK_METAL} shadow={false} />
      {FRIDGE_SHELVES.slice(1).map((y) => (
        <group key={y}>
          <Box size={[5.2, 0.03, 0.92]} position={[0, y, -0.03]} material={shelf} shadow={false} />
          <PriceRail width={5.2} y={y - 0.01} z={0.44} count={15} />
        </group>
      ))}
      <Batch geometry={BOTTLE} items={products.bottles} />
      <Batch geometry={CAN} items={products.labels} />
      <Batch geometry={CAN} items={products.caps} />
      <Batch geometry={CAN} items={products.cans} />
      {FRIDGE_DOORS.map((doorX) => (
        <group key={doorX} position={[doorX, 0, 0.53]}>
          <Box size={[0.07, 2.08, 0.06]} position={[-0.84, 1.33, 0]} material={DARK_METAL} />
          <Box size={[0.07, 2.08, 0.06]} position={[0.84, 1.33, 0]} material={DARK_METAL} />
          <Box size={[1.74, 0.07, 0.06]} position={[0, 0.33, 0]} material={DARK_METAL} />
          <Box size={[1.74, 0.07, 0.06]} position={[0, 2.33, 0]} material={DARK_METAL} />
          <Box size={[0.05, 1.96, 0.02]} position={[-0.77, 1.33, -0.05]} material={LAMP} shadow={false} />
          <Box size={[1.62, 1.94, 0.015]} position={[0, 1.33, 0]} material={GLASS} shadow={false} />
          <Box size={[0.035, 0.55, 0.035]} position={[0.74, 1.3, 0.07]} material={METAL} />
        </group>
      ))}
      <Plaque text="음료" size={[1.4, 0.4]} position={[0, 2.98, 0.2]} />
    </>
  );
}

const COOLER_LAMPS = [1.42, 1.9, 2.36];

function OpenCooler({ body }: { body: THREE.MeshStandardMaterial }) {
  const products = useMemo(() => {
    const boxes: BatchItem[] = [];
    const lids: BatchItem[] = [];
    const triangles: BatchItem[] = [];
    const cups: BatchItem[] = [];
    let index = 0;
    for (let column = 0; column < 10; column++) {
      const x = -1.85 + column * 0.41;
      for (const z of [0.3, -0.03, -0.32]) {
        boxes.push({ position: [x, 0.85, z], size: [0.35, 0.09, 0.27], color: paletteColor(index++) });
        lids.push({ position: [x, 0.905, z], size: [0.35, 0.025, 0.27], color: "#f4f4ee" });
      }
    }
    for (let column = 0; column < 14; column++) {
      const x = -1.9 + column * 0.292;
      triangles.push({ position: [x, 1.25, 0.1], size: [0.12, 0.09, 0.14], color: paletteColor(index++), rotation: [-Math.PI / 2, 0, 0] });
      triangles.push({ position: [x, 1.25, -0.2], size: [0.12, 0.09, 0.14], color: "#efece2", rotation: [-Math.PI / 2, 0, 0] });
      triangles.push({ position: [x, 1.73, -0.15], size: [0.13, 0.11, 0.17], color: paletteColor(index++), rotation: [-Math.PI / 2, 0, 0] });
    }
    for (let column = 0; column < 11; column++) {
      const x = -1.85 + column * 0.37;
      cups.push({ position: [x, 2.14, -0.2], size: [0.13, 0.17, 0.13], color: paletteColor(index++) });
    }
    return { boxes, lids, triangles, cups };
  }, []);
  const parts = useMemo(() => ({
    deck: standard("#dbe8e4", { roughness: 0.45 }),
    back: standard("#eef6f3", { emissive: "#dff4ee", emissiveIntensity: 0.35 }),
    lid: new THREE.MeshStandardMaterial({ color: "#f4f4ee", transparent: true, opacity: 0.8, roughness: 0.15 }),
  }), []);

  return (
    <>
      <Box size={[4.4, 0.75, 1.1]} position={[0, 0.375, 0]} material={body} rounded={0.03} />
      <Box size={[4.3, 0.04, 1]} position={[0, 0.78, 0]} material={parts.deck} shadow={false} />
      <Box size={[4.4, 1.95, 0.12]} position={[0, 1.72, -0.49]} material={body} />
      <Box size={[4.2, 1.8, 0.02]} position={[0, 1.65, -0.42]} material={parts.back} shadow={false} />
      <Box size={[0.1, 1.95, 1]} position={[-2.15, 1.72, -0.05]} material={body} />
      <Box size={[0.1, 1.95, 1]} position={[2.15, 1.72, -0.05]} material={body} />
      <Box size={[4.4, 0.24, 0.85]} position={[0, 2.62, -0.12]} material={body} rounded={0.03} />
      <Box size={[4.25, 0.03, 0.72]} position={[0, 1.14, -0.05]} material={parts.deck} shadow={false} />
      <Box size={[4.25, 0.03, 0.56]} position={[0, 1.62, -0.13]} material={parts.deck} shadow={false} />
      <Box size={[4.25, 0.03, 0.42]} position={[0, 2.03, -0.2]} material={parts.deck} shadow={false} />
      {COOLER_LAMPS.map((y) => (
        <Box key={y} size={[4.1, 0.02, 0.05]} position={[0, y - 0.32, 0.16 - (y - 1.42) * 0.35]} material={LAMP} shadow={false} />
      ))}
      <Box size={[4.1, 0.03, 0.06]} position={[0, 2.48, 0.22]} material={LAMP} shadow={false} />
      <PriceRail width={4.25} y={1.12} z={0.32} count={13} />
      <PriceRail width={4.25} y={1.6} z={0.15} count={13} />
      <PriceRail width={4.25} y={2.01} z={0.02} count={13} />
      <PriceRail width={4.3} y={0.74} z={0.56} count={13} />
      <Batch geometry={UNIT_BOX} items={products.boxes} />
      <Batch geometry={UNIT_BOX} items={products.lids} material={parts.lid} />
      <Batch geometry={PRISM} items={products.triangles} />
      <Batch geometry={CUP} items={products.cups} />
      <Plaque text="간편식사" size={[1.7, 0.4]} position={[0, 3.03, 0.1]} />
    </>
  );
}

const WOOD_SHELVES = [0.1, 0.56, 1.02, 1.48, 1.94];

function WoodShelf({ body }: { body: THREE.MeshStandardMaterial }) {
  const products = useMemo(() => {
    const cups: BatchItem[] = [];
    const lids: BatchItem[] = [];
    const packs: BatchItem[] = [];
    let index = 0;
    WOOD_SHELVES.slice(0, 4).forEach((y, row) => {
      for (let column = 0; column < 12; column++) {
        const x = -1.98 + column * 0.36;
        const color = paletteColor(index++);
        if (row % 2 === 0) {
          for (const z of [0.16, -0.12]) {
            cups.push({ position: [x, y + 0.14, z], size: [0.135, 0.24, 0.135], color });
            lids.push({ position: [x, y + 0.268, z], size: [0.138, 0.012, 0.138], color: "#f4f1e6" });
          }
        } else {
          for (const z of [0.18, -0.08]) {
            packs.push({ position: [x, y + 0.19, z], size: [0.27, 0.33, 0.2], color });
          }
        }
      }
    });
    return { cups, lids, packs };
  }, []);
  const pegboard = useMemo(() => standard("#8a6e47", { roughness: 0.85 }), []);

  return (
    <>
      <Box size={[4.4, 2.1, 0.05]} position={[0, 1.05, -0.37]} material={pegboard} />
      <Box size={[0.09, 2.1, 0.8]} position={[-2.17, 1.05, 0]} material={body} rounded={0.02} />
      <Box size={[0.09, 2.1, 0.8]} position={[2.17, 1.05, 0]} material={body} rounded={0.02} />
      {WOOD_SHELVES.map((y) => (
        <Box key={y} size={[4.3, 0.06, 0.76]} position={[0, y, 0]} material={body} />
      ))}
      {WOOD_SHELVES.slice(0, 4).map((y) => (
        <PriceRail key={y} width={4.25} y={y} z={0.39} count={12} />
      ))}
      <Batch geometry={CUP} items={products.cups} />
      <Batch geometry={CAN} items={products.lids} />
      <Batch geometry={BAG} items={products.packs} />
      <Plaque text="식품" size={[1.4, 0.4]} position={[0, 2.38, 0.05]} />
    </>
  );
}

const GONDOLA_SHELVES = [0.26, 0.7, 1.14];

function SnackGondola({ body }: { body: THREE.MeshStandardMaterial }) {
  const bags = useMemo(() => {
    const items: BatchItem[] = [];
    let index = 0;
    GONDOLA_SHELVES.forEach((y) => {
      for (let column = 0; column < 14; column++) {
        const x = -2.2 + column * 0.34;
        for (const z of [0.46, 0.22, -0.22, -0.46]) {
          items.push({ position: [x, y + 0.19, z], size: [0.27, 0.34, 0.13], color: paletteColor(index++) });
        }
      }
    });
    return items;
  }, []);
  const parts = useMemo(() => ({
    kick: standard("#2f3a3f", { roughness: 0.6 }),
    shelf: standard("#e8e6dd", { roughness: 0.5, metalness: 0.2 }),
  }), []);

  return (
    <>
      <Box size={[5, 0.2, 1.3]} position={[0, 0.1, 0]} material={parts.kick} />
      <Box size={[5, 1.45, 0.07]} position={[0, 0.82, 0]} material={body} />
      <Box size={[0.09, 1.5, 1.3]} position={[-2.46, 0.84, 0]} material={body} rounded={0.02} />
      <Box size={[0.09, 1.5, 1.3]} position={[2.46, 0.84, 0]} material={body} rounded={0.02} />
      {GONDOLA_SHELVES.map((y) => (
        <group key={y}>
          <Box size={[4.85, 0.04, 0.58]} position={[0, y, 0.32]} material={parts.shelf} />
          <Box size={[4.85, 0.04, 0.58]} position={[0, y, -0.32]} material={parts.shelf} />
          <PriceRail width={4.85} y={y} z={0.62} count={14} />
        </group>
      ))}
      <Batch geometry={BAG} items={bags} />
      <Plaque text="과자류" size={[1.5, 0.4]} position={[0, 1.83, 0]} />
    </>
  );
}

function IceFreezer({ body }: { body: THREE.MeshStandardMaterial }) {
  const packs = useMemo(() => {
    const items: BatchItem[] = [];
    let index = 0;
    for (let column = 0; column < 12; column++) {
      for (let row = 0; row < 4; row++) {
        const height = 0.06 + ((column * 3 + row) % 3) * 0.02;
        items.push({
          position: [-1.45 + column * 0.264, 0.83 + height / 2, -0.42 + row * 0.28],
          size: [0.23, height, 0.25],
          color: paletteColor(index++),
          rotation: [0, ((column + row) % 3) * 0.07 - 0.07, 0],
        });
      }
    }
    return items;
  }, []);
  const parts = useMemo(() => ({
    rim: standard("#7cc0e0", { roughness: 0.3, metalness: 0.2 }),
    well: standard("#7f9fae", { roughness: 0.7 }),
    lid: new THREE.MeshStandardMaterial({ color: "#c9ebff", transparent: true, opacity: 0.08, roughness: 0.2, metalness: 0, envMapIntensity: 0.15, depthWrite: false }),
  }), []);

  return (
    <>
      <Box size={[3.4, 0.8, 1.3]} position={[0, 0.4, 0]} material={body} rounded={0.05} />
      <Box size={[3.4, 0.09, 0.03]} position={[0, 0.14, 0.655]} material={parts.rim} shadow={false} />
      <Box size={[3.26, 0.02, 1.16]} position={[0, 0.815, 0]} material={parts.well} shadow={false} />
      <Batch geometry={UNIT_BOX} items={packs} />
      <Box size={[3.4, 0.2, 0.08]} position={[0, 0.9, 0.61]} material={parts.rim} />
      <Box size={[3.4, 0.2, 0.08]} position={[0, 0.9, -0.61]} material={parts.rim} />
      <Box size={[0.08, 0.2, 1.3]} position={[-1.66, 0.9, 0]} material={parts.rim} />
      <Box size={[0.08, 0.2, 1.3]} position={[1.66, 0.9, 0]} material={parts.rim} />
      <Box size={[1.66, 0.015, 1.14]} position={[-0.8, 0.98, 0]} material={parts.lid} shadow={false} />
      <Box size={[1.66, 0.015, 1.14]} position={[0.8, 0.995, 0]} material={parts.lid} shadow={false} />
      <Plaque text="아이스크림" size={[1.9, 0.4]} position={[0, 1.28, 0]} background="#3c6f88" />
    </>
  );
}

function HotCounter({ body, warmer }: { body: THREE.MeshStandardMaterial; warmer: THREE.MeshStandardMaterial }) {
  const food = useMemo(() => {
    const sticks: BatchItem[] = [];
    const buns: BatchItem[] = [];
    for (let index = 0; index < 8; index++) {
      sticks.push({
        position: [-1.82 + index * 0.17, 1.27, 0.02],
        size: [0.05, 0.34, 0.05],
        color: index % 2 ? "#b4543f" : "#d99a3d",
        rotation: [0.25, 0, 0],
      });
    }
    for (let index = 0; index < 7; index++) {
      buns.push({ position: [-1.8 + index * 0.2, 1.53, -0.02], size: [0.085, 0.07, 0.085], color: "#e8c58a" });
    }
    return { sticks, buns };
  }, []);
  const parts = useMemo(() => ({
    top: standard("#6d5a48", { roughness: 0.4 }),
    stripe: standard("#a9794a"),
    register: standard("#26292a", { roughness: 0.35, metalness: 0.4 }),
    screen: new THREE.MeshBasicMaterial({ color: "#9ad1ff", toneMapped: false }),
    machine: standard("#e6e6e0", { roughness: 0.3, metalness: 0.3 }),
    rack: standard("#b9b9b0", { roughness: 0.3, metalness: 0.7 }),
  }), []);

  return (
    <>
      <Box size={[4.2, 1, 1.05]} position={[0, 0.5, 0]} material={body} rounded={0.03} />
      <Box size={[4.2, 0.12, 0.02]} position={[0, 0.22, 0.53]} material={parts.stripe} shadow={false} />
      <Box size={[4.3, 0.06, 1.15]} position={[0, 1.03, 0]} material={parts.top} rounded={0.02} />
      {/* 온장고 */}
      <Box size={[1.5, 0.05, 0.62]} position={[-1.2, 1.09, 0]} material={DARK_METAL} />
      <Box size={[1.42, 0.58, 0.5]} position={[-1.2, 1.4, -0.02]} material={warmer} shadow={false} />
      <Batch geometry={CAN} items={food.sticks} />
      <Box size={[1.4, 0.02, 0.5]} position={[-1.2, 1.46, -0.02]} material={parts.rack} shadow={false} />
      <Batch geometry={CAN} items={food.buns} />
      <Box size={[1.5, 0.05, 0.62]} position={[-1.2, 1.72, 0]} material={DARK_METAL} />
      {[-1.94, -0.46].map((x) => (
        <Box key={x} size={[0.04, 0.62, 0.62]} position={[x, 1.4, 0]} material={DARK_METAL} />
      ))}
      <Box size={[1.46, 0.6, 0.015]} position={[-1.2, 1.4, 0.3]} material={GLASS} shadow={false} />
      {/* 계산대 */}
      <Box size={[0.62, 0.14, 0.46]} position={[0.65, 1.13, 0.02]} material={parts.register} rounded={0.02} />
      <Box size={[0.06, 0.26, 0.06]} position={[0.65, 1.3, -0.08]} material={parts.register} />
      <Box size={[0.46, 0.3, 0.04]} position={[0.65, 1.47, -0.03]} material={parts.register} rotation={[-0.18, 0, 0]} />
      <Box size={[0.4, 0.24, 0.01]} position={[0.65, 1.47, 0]} material={parts.screen} rotation={[-0.18, 0, 0]} shadow={false} />
      <Box size={[0.14, 0.05, 0.24]} position={[1.08, 1.09, 0.2]} material={parts.register} />
      {/* 커피 머신과 컵 */}
      <Box size={[0.52, 0.72, 0.5]} position={[1.72, 1.42, -0.1]} material={parts.machine} rounded={0.04} />
      <Box size={[0.32, 0.22, 0.04]} position={[1.72, 1.34, 0.16]} material={parts.register} />
      <Box size={[0.32, 0.1, 0.03]} position={[1.72, 1.64, 0.16]} material={parts.screen} shadow={false} />
      <Plaque text="즉석조리" size={[1.7, 0.4]} position={[0.2, 2.03, 0]} background="#5c4a37" />
    </>
  );
}

export interface FixtureSpec {
  category: Category;
  position: Vec3;
  rotationY: number;
  /** 핀을 띄울 높이 */
  top: number;
  bodyColor: string;
  hitSize: Vec3;
  hitY: number;
  /** 바닥 그림자 크기 */
  footprint: [number, number];
}

// 기본 시점(방위각 30°, 고도 30°)에서 서로 겹치지 않도록 투영을 계산해 정한 위치다.
export const FIXTURES: FixtureSpec[] = [
  { category: "음료", position: [2.2, 0, -3.85], rotationY: 0, top: 2.7, bodyColor: "#35523f", hitSize: [5.4, 2.75, 1.15], hitY: 1.38, footprint: [5.9, 1.7] },
  { category: "간편식사", position: [-3.6, 0, -3.85], rotationY: 0, top: 2.75, bodyColor: "#5f9d90", hitSize: [4.4, 2.75, 1.15], hitY: 1.38, footprint: [4.9, 1.7] },
  { category: "식품", position: [-8.45, 0, -2], rotationY: Math.PI / 2, top: 2.1, bodyColor: "#c49c62", hitSize: [4.4, 2.15, 0.85], hitY: 1.08, footprint: [4.9, 1.3] },
  { category: "과자류", position: [-0.9, 0, 0.65], rotationY: 0, top: 1.55, bodyColor: "#e4834b", hitSize: [5, 1.6, 1.35], hitY: 0.8, footprint: [5.5, 1.9] },
  { category: "아이스크림", position: [6.1, 0, 0.4], rotationY: 0, top: 1.02, bodyColor: "#dbeaf2", hitSize: [3.45, 1.04, 1.35], hitY: 0.52, footprint: [3.9, 1.8] },
  { category: "즉석조리", position: [-5, 0, 3.9], rotationY: 0, top: 1.75, bodyColor: "#d6c6ad", hitSize: [4.3, 1.8, 1.15], hitY: 0.9, footprint: [4.8, 1.6] },
];

function GltfFixture({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} />;
}

export function FixtureShape({ category, body, warmer }: {
  category: Category;
  body: THREE.MeshStandardMaterial;
  warmer: THREE.MeshStandardMaterial;
}): ReactNode {
  const modelUrl = FIXTURE_MODELS[category];
  if (modelUrl) return <GltfFixture url={modelUrl} />;
  switch (category) {
    case "음료":
      return <BeverageFridge body={body} />;
    case "간편식사":
      return <OpenCooler body={body} />;
    case "식품":
      return <WoodShelf body={body} />;
    case "과자류":
      return <SnackGondola body={body} />;
    case "아이스크림":
      return <IceFreezer body={body} />;
    case "즉석조리":
      return <HotCounter body={body} warmer={warmer} />;
  }
}
