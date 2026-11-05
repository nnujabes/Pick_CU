import { Billboard, RoundedBox, useGLTF } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import { useEffect, useLayoutEffect, useMemo, useRef, type ReactNode } from "react";
import * as THREE from "three";
import type { Category } from "@/api/types";

type Vec3 = [number, number, number];

/** glTF로 바꾸려면 여기에 카테고리별 파일 경로만 넣는다. 예: 음료: "/models/fridge.glb" */
export const FIXTURE_MODELS: Partial<Record<Category, string>> = {};

export const noRaycast = () => null;

const standard = (color: string, extra: THREE.MeshStandardMaterialParameters = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.7, metalness: 0.04, ...extra });

const RAIL = standard("#d9dcd6", { roughness: 0.4, metalness: 0.3 });
const PRICE_TAG = new THREE.MeshBasicMaterial({ color: "#f4f4ee", toneMapped: false });
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
export function Plaque({ text, size, position, background = "#25221d", color = "#f7f3e8", fontScale = 0.56 }: {
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
  }, [size[0], size[1], gl]);

  useEffect(() => {
    const font = `700 ${Math.round((texture.image as HTMLCanvasElement).height * fontScale)}px 'IBM Plex Sans KR', 'Malgun Gothic', sans-serif`;
    const draw = () => {
      const canvas = texture.image as HTMLCanvasElement;
      const context = canvas.getContext("2d");
      if (!context) return;
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = background;
      context.beginPath();
      context.roundRect(0, 0, canvas.width, canvas.height, canvas.height * 0.12);
      context.fill();
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
      <mesh raycast={noRaycast} renderOrder={10}>
        <planeGeometry args={size} />
        <meshBasicMaterial map={texture} toneMapped={false} transparent depthTest={false} depthWrite={false} />
      </mesh>
    </Billboard>
  );
}

interface BatchItem {
  position: Vec3;
  size: Vec3;
  color?: string;
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
  material?: THREE.Material | THREE.Material[];
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
      mesh.setColorAt(index, color.set(item.color ?? "#ffffff"));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [items]);
  return <instancedMesh ref={meshRef} args={[geometry, material, items.length]} castShadow raycast={noRaycast} />;
}

/* ---------- 상품 포장 그림. 실제 브랜드 없이 색과 무늬로만 그린다. ---------- */

function paint(width: number, height: number, draw: (context: CanvasRenderingContext2D, w: number, h: number) => void) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (context) draw(context, width, height);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

const printed = (draw: (context: CanvasRenderingContext2D, w: number, h: number) => void, roughness = 0.5) =>
  new THREE.MeshStandardMaterial({ map: paint(96, 128, draw), roughness, metalness: 0.02 });

function textBars(context: CanvasRenderingContext2D, x: number, y: number, width: number, color: string) {
  context.fillStyle = color;
  context.fillRect(x, y, width, 6);
  context.fillRect(x + width * 0.14, y + 10, width * 0.72, 4);
}

/** 네모 상자 정면 */
function cartonFront(background: string, accent: string) {
  return printed((context, w, h) => {
    context.fillStyle = background;
    context.fillRect(0, 0, w, h);
    context.fillStyle = accent;
    context.fillRect(0, 0, w, h * 0.3);
    context.fillStyle = "#fbf8ef";
    context.fillRect(w * 0.12, h * 0.38, w * 0.76, h * 0.34);
    context.fillStyle = accent;
    context.beginPath();
    context.arc(w / 2, h * 0.55, h * 0.12, 0, Math.PI * 2);
    context.fill();
    textBars(context, w * 0.18, h * 0.1, w * 0.64, "#fbf8ef");
    textBars(context, w * 0.2, h * 0.8, w * 0.6, "#fbf8ef");
  });
}

/** 과자 봉지 정면: 위아래 접힘선과 가운데 큰 그림 */
function bagFront(background: string, accent: string) {
  return printed((context, w, h) => {
    context.fillStyle = background;
    context.fillRect(0, 0, w, h);
    const shine = context.createLinearGradient(0, 0, w, 0);
    shine.addColorStop(0.2, "rgba(255,255,255,0)");
    shine.addColorStop(0.4, "rgba(255,255,255,0.3)");
    shine.addColorStop(0.6, "rgba(255,255,255,0)");
    context.fillStyle = shine;
    context.fillRect(0, 0, w, h);
    context.fillStyle = accent;
    context.beginPath();
    context.ellipse(w / 2, h * 0.62, w * 0.36, h * 0.2, -0.2, 0, Math.PI * 2);
    context.fill();
    textBars(context, w * 0.14, h * 0.2, w * 0.72, accent);
    context.fillStyle = "rgba(0,0,0,0.27)";
    context.fillRect(0, 0, w, 6);
    context.fillRect(0, h - 6, w, 6);
  }, 0.35);
}

/** 컵라면 옆면 */
function cupWrap(background: string, accent: string) {
  return printed((context, w, h) => {
    context.fillStyle = background;
    context.fillRect(0, 0, w, h);
    context.fillStyle = accent;
    context.fillRect(0, h * 0.32, w, h * 0.34);
    context.fillStyle = "#fbf8ef";
    context.fillRect(w * 0.2, h * 0.4, w * 0.6, h * 0.16);
  });
}

/** 위에서 보이는 도시락 칸 */
const BENTO_TOP = printed((context, w, h) => {
  context.fillStyle = "#26211b";
  context.fillRect(0, 0, w, h);
  const cells: [number, number, number, number, string][] = [
    [0.06, 0.06, 0.52, 0.88, "#f6f1e3"],
    [0.62, 0.06, 0.32, 0.27, "#c4632b"],
    [0.62, 0.37, 0.32, 0.27, "#e0a93b"],
    [0.62, 0.68, 0.32, 0.26, "#6f9b42"],
  ];
  cells.forEach(([x, y, cw, ch, color]) => {
    context.fillStyle = color;
    context.fillRect(x * w, y * h, cw * w, ch * h);
  });
  context.fillStyle = "#b5512a";
  context.beginPath();
  context.ellipse(w * 0.32, h * 0.5, w * 0.16, h * 0.14, 0, 0, Math.PI * 2);
  context.fill();
}, 0.3);

/** 위에서 보이는 샐러드 그릇 */
const SALAD_TOP = printed((context, w, h) => {
  context.fillStyle = "#f2efe4";
  context.fillRect(0, 0, w, h);
  context.fillStyle = "#6fa23f";
  context.beginPath();
  context.ellipse(w / 2, h / 2, w * 0.42, h * 0.42, 0, 0, Math.PI * 2);
  context.fill();
  ([[0.36, 0.38, "#d8432f"], [0.62, 0.42, "#efc23f"], [0.46, 0.64, "#d8432f"], [0.68, 0.64, "#a7cc58"], [0.3, 0.6, "#efc23f"]] as const).forEach(([x, y, color]) => {
    context.fillStyle = color;
    context.beginPath();
    context.ellipse(w * x, h * y, w * 0.08, h * 0.06, 0, 0, Math.PI * 2);
    context.fill();
  });
}, 0.25);

/** 삼각김밥 앞면: 김과 흰 띠 */
const KIMBAP_FACE = printed((context, w, h) => {
  context.fillStyle = "#f4f0e4";
  context.fillRect(0, 0, w, h);
  context.fillStyle = "#23281f";
  context.beginPath();
  context.ellipse(w / 2, h * 0.42, w * 0.3, h * 0.26, 0, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = "#d8432f";
  context.fillRect(w * 0.26, h * 0.4, w * 0.48, h * 0.1);
}, 0.3);

/** 샌드위치 단면 */
const SANDWICH_FACE = printed((context, w, h) => {
  context.fillStyle = "#efdcb2";
  context.fillRect(0, 0, w, h);
  (["#7fa843", "#e7b93f", "#c9553a", "#7fa843"] as const).forEach((color, index) => {
    context.fillStyle = color;
    context.fillRect(0, h * (0.34 + index * 0.09), w, h * 0.07);
  });
}, 0.3);

/** 아이스크림 포장 윗면 */
function iceTop(background: string, accent: string) {
  return printed((context, w, h) => {
    context.fillStyle = background;
    context.fillRect(0, 0, w, h);
    context.fillStyle = accent;
    context.beginPath();
    context.ellipse(w / 2, h / 2, w * 0.26, h * 0.32, 0, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = "#fbf8ef";
    context.fillRect(0, h * 0.04, w, h * 0.08);
    context.fillRect(0, h * 0.88, w, h * 0.08);
  }, 0.3);
}

const plain = (color: string) => standard(color, { roughness: 0.5 });

/** 상자 재질 묶음. 순서는 +x, -x, +y, -y, +z, -z */
const boxDesign = (front: THREE.Material, side: string, top?: THREE.Material) => {
  const sideMaterial = plain(side);
  return [sideMaterial, sideMaterial, top ?? sideMaterial, sideMaterial, front, front];
};

const SNACK_COLORS: [string, string][] = [
  ["#d8352a", "#f5c518"],
  ["#1f5fa8", "#f5d547"],
  ["#e9691e", "#fff1c9"],
  ["#2f8f4e", "#f4e04d"],
  ["#f3c623", "#c8321f"],
  ["#7b3fa0", "#f5b7d1"],
  ["#16897a", "#f9d65c"],
  ["#b01f3a", "#fbe7c6"],
];
const FOOD_COLORS: [string, string][] = [
  ["#c8321f", "#f3b23a"],
  ["#2e7d4f", "#f1e6c8"],
  ["#e5e0cf", "#c8321f"],
  ["#d98a2b", "#7a3b16"],
  ["#2a5f9e", "#f1e6c8"],
  ["#e5e0cf", "#2e7d4f"],
];
const BAG_DESIGNS = SNACK_COLORS.map(([background, accent]) => boxDesign(bagFront(background, accent), background));
const SNACK_BOX_DESIGNS = SNACK_COLORS.map(([background, accent]) => boxDesign(cartonFront(background, accent), background));
const FOOD_BOX_DESIGNS = FOOD_COLORS.map(([background, accent]) => boxDesign(cartonFront(background, accent), background));
const CUP_LID = plain("#f4f1e6");
const CUP_DESIGNS = FOOD_COLORS.map(([background, accent]) => [cupWrap(background, accent), CUP_LID, CUP_LID]);
const ICE_DESIGNS = SNACK_COLORS.map(([background, accent]) => boxDesign(plain(background), background, iceTop(background, accent)));
const BENTO_DESIGN = boxDesign(plain("#2b2620"), "#2b2620", BENTO_TOP);
const SALAD_DESIGN = [plain("#e9e6da"), SALAD_TOP, plain("#e9e6da")];
const KIMBAP_DESIGN = [plain("#ece8db"), plain("#ece8db"), KIMBAP_FACE];
const SANDWICH_DESIGN = [plain("#f0ebdc"), plain("#f0ebdc"), SANDWICH_FACE];

const SAGE_DARK = standard("#39473a", { roughness: 0.65 });
const STEEL = standard("#cfd1cc", { roughness: 0.3, metalness: 0.35 });
const BRASS = standard("#c3a06a", { roughness: 0.3, metalness: 0.4 });
const BRONZE = standard("#3a332b", { roughness: 0.4, metalness: 0.6 });
const LED_WARM = new THREE.MeshBasicMaterial({ color: "#ffd9a0", toneMapped: false });
const LIT_BACK = new THREE.MeshBasicMaterial({ color: "#fbf6ea", toneMapped: false });
const COLD_BACK = new THREE.MeshBasicMaterial({ color: "#f3f8fb", toneMapped: false });
const WOOD_BACK = standard("#c9a26c", { roughness: 0.8 });
const WHITE_SHELF = standard("#d6d2c6", { roughness: 0.45, metalness: 0.1 });
const LEAF = standard("#6f8f3f", { roughness: 0.7 });
const POT = standard("#c7a35e", { roughness: 0.35, metalness: 0.6 });

function Designed({ geometry, designs, items }: {
  geometry: THREE.BufferGeometry;
  designs: THREE.Material[][];
  items: BatchItem[];
}) {
  const groups = useMemo(
    () => designs.map((_, design) => items.filter((_item, index) => index % designs.length === design)),
    [designs, items],
  );
  return (
    <>
      {groups.map((group, design) =>
        group.length > 0 ? <Batch key={design} geometry={geometry} items={group} material={designs[design]} /> : null,
      )}
    </>
  );
}

/** 선반 앞의 가격표 줄 */
function PriceRail({ width, y, z, count }: { width: number; y: number; z: number; count: number }) {
  const tags = useMemo<BatchItem[]>(
    () => Array.from({ length: count }, (_, index) => ({
      position: [-width / 2 + ((index + 0.5) * width) / count, y, z + 0.012] as Vec3,
      size: [0.13, 0.05, 0.01] as Vec3,
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

const ROUND = new THREE.SphereGeometry(1, 8, 6);

/** 화분. trail이 있으면 잎이 한쪽으로 늘어진다. */
function Plant({ position, scale = 1, trail = 0 }: { position: Vec3; scale?: number; trail?: number }) {
  const leaves = useMemo<BatchItem[]>(() => {
    const items: BatchItem[] = [];
    for (let index = 0; index < 34; index++) {
      const angle = index * 2.399;
      const ring = 0.04 + (index % 7) * 0.035;
      items.push({
        position: [Math.cos(angle) * ring, 0.26 + (index % 5) * 0.07, Math.sin(angle) * ring],
        size: [0.035, 0.02, 0.1],
        color: index % 3 ? "#ffffff" : "#c9dd9c",
        rotation: [0.6 * Math.sin(index), angle, 0.7 * Math.cos(index)],
      });
    }
    for (let index = 0; index < trail; index++) {
      items.push({
        position: [0.14 + (index % 3) * 0.05, 0.2 - index * 0.055, ((index * 37) % 11) * 0.02 - 0.1],
        size: [0.03, 0.018, 0.075],
        color: index % 2 ? "#ffffff" : "#c9dd9c",
        rotation: [index * 0.9, index * 1.7, 0.5],
      });
    }
    return items;
  }, [trail]);
  return (
    <group position={position} scale={scale}>
      <mesh position={[0, 0.1, 0]} material={POT} castShadow raycast={noRaycast}>
        <cylinderGeometry args={[0.12, 0.09, 0.2, 14]} />
      </mesh>
      <Batch geometry={ROUND} items={leaves} material={LEAF} />
    </group>
  );
}

const FRIDGE_DOORS = [-1.72, 0, 1.72];
const FRIDGE_SHELVES = [0.38, 0.84, 1.3, 1.76, 2.22];
const DRINK_ROWS = [
  ["#7cc4e8", "#2e7fc1", "#7cc4e8", "#2e7fc1", "#bfe3f5"],
  ["#4c9a4b", "#e8862a", "#d8352a", "#f2c230", "#4c9a4b"],
  ["#7a3b16", "#f2c230", "#7cc4e8", "#3a2415", "#d9d3a8"],
];

function BeverageFridge({ body }: { body: THREE.MeshStandardMaterial }) {
  const products = useMemo(() => {
    const bottles: BatchItem[] = [];
    const labels: BatchItem[] = [];
    const caps: BatchItem[] = [];
    FRIDGE_DOORS.forEach((doorX, door) => {
      FRIDGE_SHELVES.forEach((y, row) => {
        for (let column = 0; column < 6; column++) {
          const x = doorX - 0.64 + column * 0.256;
          const color = column % 3 === 2 ? DRINK_ROWS[(door + 1) % 3][row] : DRINK_ROWS[door][row];
          for (const z of [0.36, 0.04]) {
            bottles.push({ position: [x, y + 0.2, z], size: [0.105, 0.42, 0.105], color });
            labels.push({ position: [x, y + 0.13, z], size: [0.108, 0.08, 0.108], color: column % 2 ? "#f5f2e8" : "#ffe9b8" });
            caps.push({ position: [x, y + 0.42, z], size: [0.045, 0.03, 0.045], color });
          }
        }
      });
    });
    return { bottles, labels, caps };
  }, []);
  const glassShelf = useMemo(() => standard("#dfe6e8", { roughness: 0.3, metalness: 0.3 }), []);
  const grille = useMemo<BatchItem[]>(
    () => FRIDGE_DOORS.flatMap((doorX) => [0.1, 0.17, 0.24].map((y) => ({
      position: [doorX, y, 0.605] as Vec3,
      size: [1.2, 0.03, 0.01] as Vec3,
      color: "#232a24",
    }))),
    [],
  );

  return (
    <>
      <Box size={[5.3, 0.32, 1.2]} position={[0, 0.16, 0]} material={body} />
      <Box size={[5.3, 0.4, 1.2]} position={[0, 2.9, 0]} material={body} rounded={0.03} />
      <Box size={[0.12, 3.1, 1.2]} position={[-2.59, 1.55, 0]} material={body} />
      <Box size={[0.12, 3.1, 1.2]} position={[2.59, 1.55, 0]} material={body} />
      <Box size={[5.1, 2.4, 0.05]} position={[0, 1.5, -0.56]} material={COLD_BACK} shadow={false} />
      <Batch geometry={UNIT_BOX} items={grille} />
      {FRIDGE_SHELVES.map((y) => (
        <group key={y}>
          <Box size={[5.06, 0.02, 0.95]} position={[0, y, 0]} material={glassShelf} shadow={false} />
          <PriceRail width={5.06} y={y - 0.012} z={0.48} count={18} />
        </group>
      ))}
      <Batch geometry={BOTTLE} items={products.bottles} />
      <Batch geometry={CAN} items={products.labels} />
      <Batch geometry={CAN} items={products.caps} />
      {FRIDGE_DOORS.map((doorX) => (
        <group key={doorX} position={[doorX, 0, 0.56]}>
          <Box size={[0.05, 2.38, 0.05]} position={[-0.82, 1.51, 0]} material={BRONZE} />
          <Box size={[0.05, 2.38, 0.05]} position={[0.82, 1.51, 0]} material={BRONZE} />
          <Box size={[1.69, 0.05, 0.05]} position={[0, 0.34, 0]} material={BRONZE} />
          <Box size={[1.69, 0.05, 0.05]} position={[0, 2.68, 0]} material={BRONZE} />
          <Box size={[0.03, 2.2, 0.02]} position={[-0.72, 1.51, -0.06]} material={LIT_BACK} shadow={false} />
          <Box size={[1.54, 2.24, 0.015]} position={[0, 1.51, 0]} material={GLASS} shadow={false} />
          <Box size={[0.035, 0.8, 0.035]} position={[0.68, 1.5, 0.07]} material={STEEL} />
        </group>
      ))}
      <Plaque text="음료" size={[1.15, 0.42]} position={[0, 2.92, 0.7]} />
    </>
  );
}

const COOLER_TIERS = [
  { y: 0.66, z: 0.16, kind: "bento" },
  { y: 1.12, z: 0.06, kind: "mixed" },
  { y: 1.58, z: -0.04, kind: "top" },
  { y: 2.02, z: -0.14, kind: "kimbap" },
] as const;

function OpenCooler({ body }: { body: THREE.MeshStandardMaterial }) {
  const products = useMemo(() => {
    const bentos: BatchItem[] = [];
    const kimbaps: BatchItem[] = [];
    const sandwiches: BatchItem[] = [];
    const salads: BatchItem[] = [];
    const faceFront: Vec3 = [-Math.PI / 2 + 0.2, 0, 0];
    COOLER_TIERS.forEach(({ y, z, kind }) => {
      for (let column = 0; column < 12; column++) {
        const x = -2.2 + column * 0.4;
        const right = column >= 6;
        if (kind === "bento" || (kind === "mixed" && !right)) {
          for (const dz of [0.14, -0.14]) {
            bentos.push({ position: [x, y + 0.1, z + dz], size: [0.34, 0.08, 0.26], rotation: [0.35, 0, 0] });
          }
        } else if (kind === "mixed") {
          for (const dx of [-0.09, 0.09]) {
            sandwiches.push({ position: [x + dx, y + 0.13, z + 0.16], size: [0.13, 0.12, 0.14], rotation: faceFront });
          }
        } else if (kind === "top" && right) {
          salads.push({ position: [x, y + 0.08, z + 0.14], size: [0.16, 0.1, 0.16], rotation: [0.45, 0, 0] });
        } else {
          for (const dx of [-0.09, 0.09]) {
            kimbaps.push({ position: [x + dx, y + 0.13, z + 0.14], size: [0.13, 0.11, 0.14], rotation: faceFront });
          }
        }
      }
    });
    return { bentos, kimbaps, sandwiches, salads };
  }, []);
  const grille = useMemo<BatchItem[]>(
    () => [0.14, 0.22, 0.3].map((y) => ({ position: [0, y, 0.56] as Vec3, size: [4.2, 0.03, 0.01] as Vec3, color: "#232a24" })),
    [],
  );

  return (
    <>
      <Box size={[4.9, 0.62, 1.1]} position={[0, 0.31, 0]} material={body} rounded={0.03} />
      <Batch geometry={UNIT_BOX} items={grille} />
      <Box size={[4.9, 0.05, 0.02]} position={[0, 0.58, 0.56]} material={STEEL} shadow={false} />
      <Box size={[4.9, 2.2, 0.08]} position={[0, 1.7, -0.51]} material={body} />
      <Box size={[4.66, 1.84, 0.02]} position={[0, 1.54, -0.46]} material={LIT_BACK} shadow={false} />
      <Box size={[0.12, 2.8, 1.1]} position={[-2.39, 1.4, 0]} material={body} />
      <Box size={[0.12, 2.8, 1.1]} position={[2.39, 1.4, 0]} material={body} />
      <Box size={[4.9, 0.34, 1.05]} position={[0, 2.63, -0.02]} material={body} rounded={0.03} />
      <Box size={[4.6, 0.02, 0.07]} position={[0, 2.45, 0.32]} material={LED_WARM} shadow={false} />
      {COOLER_TIERS.map(({ y, z }, index) => (
        <group key={y}>
          <Box size={[4.66, 0.03, 0.82 - index * 0.06]} position={[0, y, z]} material={WHITE_SHELF} shadow={false} />
          <PriceRail width={4.66} y={y - 0.01} z={z + 0.42 - index * 0.03} count={15} />
          {index > 0 && <Box size={[4.5, 0.012, 0.05]} position={[0, y - 0.03, z + 0.2]} material={LED_WARM} shadow={false} />}
        </group>
      ))}
      <Designed geometry={UNIT_BOX} designs={[BENTO_DESIGN]} items={products.bentos} />
      <Designed geometry={PRISM} designs={[KIMBAP_DESIGN]} items={products.kimbaps} />
      <Designed geometry={PRISM} designs={[SANDWICH_DESIGN]} items={products.sandwiches} />
      <Designed geometry={CAN} designs={[SALAD_DESIGN]} items={products.salads} />
      <Plaque text="간편식사" size={[1.5, 0.42]} position={[0, 2.68, 0.6]} />
    </>
  );
}

const WOOD_SHELVES = [0.14, 0.64, 1.14, 1.64, 2.14];

function WoodShelf({ body }: { body: THREE.MeshStandardMaterial }) {
  const products = useMemo(() => {
    const sauces: BatchItem[] = [];
    const cups: BatchItem[] = [];
    const boxes: BatchItem[] = [];
    WOOD_SHELVES.forEach((y, row) => {
      for (let column = 0; column < 11; column++) {
        const x = -1.72 + column * 0.344;
        for (const z of [0.24, -0.08]) {
          if (row === 0) {
            sauces.push({ position: [x, y + 0.2, z], size: [0.085, 0.38, 0.085], color: column % 3 ? "#4a2a14" : "#7a4a1c" });
          } else if (row === 2) {
            cups.push({ position: [x, y + 0.14, z], size: [0.135, 0.26, 0.135] });
          } else {
            boxes.push({ position: [x, y + 0.18, z], size: [0.28, 0.34, 0.16] });
          }
        }
      }
    });
    return { sauces, cups, boxes };
  }, []);

  return (
    <>
      <Box size={[3.9, 2.8, 0.05]} position={[0, 1.4, -0.43]} material={WOOD_BACK} />
      <Box size={[0.1, 2.8, 0.95]} position={[-1.95, 1.4, 0]} material={body} />
      <Box size={[0.1, 2.8, 0.95]} position={[1.95, 1.4, 0]} material={body} />
      <Box size={[4, 0.1, 0.95]} position={[0, 2.75, 0]} material={body} />
      {WOOD_SHELVES.map((y) => (
        <group key={y}>
          <Box size={[3.85, 0.06, 0.9]} position={[0, y, 0]} material={body} />
          <PriceRail width={3.85} y={y} z={0.46} count={11} />
        </group>
      ))}
      <Batch geometry={BOTTLE} items={products.sauces} />
      <Designed geometry={CUP} designs={CUP_DESIGNS} items={products.cups} />
      <Designed geometry={UNIT_BOX} designs={FOOD_BOX_DESIGNS} items={products.boxes} />
      <Plant position={[1.35, 2.8, -0.05]} scale={1.3} trail={22} />
      <Plaque text="식품" size={[1.15, 0.42]} position={[-1, 2.92, 0.5]} />
    </>
  );
}

const GONDOLA_SHELVES = [0.22, 0.74, 1.26];

function SnackGondola({ body }: { body: THREE.MeshStandardMaterial }) {
  const products = useMemo(() => {
    const bags: BatchItem[] = [];
    const cartons: BatchItem[] = [];
    GONDOLA_SHELVES.forEach((y, row) => {
      const z = 0.5 - row * 0.2;
      for (let column = 0; column < 15; column++) {
        const x = -2.3 + column * 0.329;
        if (row === 2) cartons.push({ position: [x, y + 0.21, z], size: [0.3, 0.44, 0.14] });
        else bags.push({ position: [x, y + 0.23, z], size: [0.3, 0.45, 0.13] });
        if (row === 0) bags.push({ position: [x, y + 0.23, z - 0.22], size: [0.3, 0.45, 0.13] });
      }
    });
    return { bags, cartons };
  }, []);

  return (
    <>
      <Box size={[5.1, 0.2, 1.3]} position={[0, 0.1, 0]} material={SAGE_DARK} />
      <Box size={[5.1, 1.9, 0.08]} position={[0, 1, -0.1]} material={WOOD_BACK} />
      <Box size={[0.14, 2, 1.4]} position={[-2.48, 1, 0]} material={body} />
      <Box size={[0.14, 2, 1.4]} position={[2.48, 1, 0]} material={body} />
      {GONDOLA_SHELVES.map((y, row) => {
        const depth = 1.12 - row * 0.2;
        const z = -0.06 + depth / 2;
        return (
          <group key={y}>
            <Box size={[4.86, 0.04, depth]} position={[0, y, z]} material={WHITE_SHELF} />
            <PriceRail width={4.86} y={y} z={z + depth / 2} count={15} />
          </group>
        );
      })}
      <Designed geometry={BAG} designs={BAG_DESIGNS} items={products.bags} />
      <Designed geometry={UNIT_BOX} designs={SNACK_BOX_DESIGNS} items={products.cartons} />
      <Plaque text="과자류" size={[1.25, 0.42]} position={[0.2, 2.2, 0]} />
    </>
  );
}

function IceFreezer({ body }: { body: THREE.MeshStandardMaterial }) {
  const packs = useMemo(() => {
    const items: BatchItem[] = [];
    for (let column = 0; column < 11; column++) {
      for (let row = 0; row < 4; row++) {
        const height = 0.07 + ((column * 3 + row) % 3) * 0.025;
        items.push({
          position: [-1.55 + column * 0.31, 0.98 + height / 2, -0.6 + row * 0.4],
          size: [0.25, height, 0.32],
          rotation: [0, ((column + row) % 3) * 0.08 - 0.08, 0],
        });
      }
    }
    return items;
  }, []);
  const parts = useMemo(() => ({
    well: new THREE.MeshBasicMaterial({ color: "#e9f0f2", toneMapped: false }),
    lid: new THREE.MeshStandardMaterial({ color: "#dff1fb", transparent: true, opacity: 0.1, roughness: 0.1, metalness: 0, envMapIntensity: 0.4, depthWrite: false }),
  }), []);

  return (
    <>
      <Box size={[3.9, 0.1, 1.8]} position={[0, 0.05, 0]} material={BRASS} />
      <Box size={[3.9, 0.85, 1.9]} position={[0, 0.52, 0]} material={body} rounded={0.03} />
      <Box size={[3.74, 0.02, 1.72]} position={[0, 0.96, 0]} material={parts.well} shadow={false} />
      <Box size={[3.8, 0.02, 0.02]} position={[0, 0.9, 0.96]} material={LED_WARM} shadow={false} />
      <Designed geometry={UNIT_BOX} designs={ICE_DESIGNS} items={packs} />
      {[-0.91, 0.91].map((z) => (
        <Box key={z} size={[3.9, 0.2, 0.08]} position={[0, 1.04, z]} material={STEEL} />
      ))}
      {[-1.91, 1.91].map((x) => (
        <Box key={x} size={[0.08, 0.2, 1.9]} position={[x, 1.04, 0]} material={STEEL} />
      ))}
      <Box size={[0.05, 0.06, 1.9]} position={[0, 1.12, 0]} material={STEEL} />
      <Box size={[1.88, 0.015, 1.76]} position={[-0.95, 1.12, 0]} material={parts.lid} shadow={false} />
      <Box size={[1.88, 0.015, 1.76]} position={[0.95, 1.12, 0]} material={parts.lid} shadow={false} />
      <Plaque text="아이스크림" size={[1.7, 0.42]} position={[0, 1.62, 0]} />
    </>
  );
}

const WARMER_RADIUS = 0.62;
const WARMER_LENGTH = 1.86;
const WARMER_X = -1.36;

function HotCounter({ body, warmer }: { body: THREE.MeshStandardMaterial; warmer: THREE.MeshStandardMaterial }) {
  const details = useMemo(() => {
    const slats: BatchItem[] = [];
    for (let index = 0; index < 42; index++) {
      slats.push({ position: [-2.3 + index * 0.112, 0.64, 0.645], size: [0.075, 1.02, 0.04] });
    }
    const pastries: BatchItem[] = [];
    [0, 1].forEach((level) => {
      for (let column = 0; column < 7; column++) {
        for (const z of [0.12, -0.1]) {
          pastries.push({
            position: [WARMER_X - 0.66 + column * 0.22, 1.42 + level * 0.3, z - level * 0.1],
            size: [0.09, 0.06, 0.08],
            color: column % 2 ? "#d99a3d" : "#c47a2c",
          });
        }
      }
    });
    return { slats, pastries };
  }, []);
  const parts = useMemo(() => ({
    marble: new THREE.MeshStandardMaterial({
      roughness: 0.22,
      metalness: 0.02,
      map: paint(256, 128, (context, w, h) => {
        context.fillStyle = "#efeae0";
        context.fillRect(0, 0, w, h);
        context.strokeStyle = "#c9c2b4";
        context.lineWidth = 1;
        [10, 46, 88, 130, 180, 226].forEach((x, index) => {
          context.beginPath();
          context.moveTo(x, 0);
          context.bezierCurveTo(x + 30, h * 0.3, x - 20, h * 0.6, x + 26 + index * 3, h);
          context.stroke();
        });
      }),
    }),
    tray: standard("#b08d57", { roughness: 0.35, metalness: 0.7 }),
    pos: standard("#1d1f21", { roughness: 0.35, metalness: 0.4 }),
    screen: new THREE.MeshBasicMaterial({ color: "#a9d3f2", toneMapped: false }),
    terminal: standard("#e8e6df", { roughness: 0.35, metalness: 0.15 }),
    glass: new THREE.MeshStandardMaterial({ color: "#f5e6c8", transparent: true, opacity: 0.16, roughness: 0.08, envMapIntensity: 0.5, side: THREE.DoubleSide, depthWrite: false }),
  }), []);

  return (
    <>
      <Box size={[4.5, 0.1, 1.05]} position={[0, 0.05, 0]} material={BRASS} />
      <Box size={[4.7, 0.03, 0.02]} position={[0, 0.115, 0.62]} material={LED_WARM} shadow={false} />
      <Box size={[4.7, 1.05, 1.25]} position={[0, 0.63, 0]} material={body} rounded={0.08} />
      <Batch geometry={UNIT_BOX} items={details.slats} material={body} />
      <Box size={[4.82, 0.08, 1.35]} position={[0, 1.2, 0]} material={parts.marble} rounded={0.035} />

      {/* 온장고 */}
      <Box size={[WARMER_LENGTH, 0.06, 0.76]} position={[WARMER_X, 1.27, 0]} material={BRONZE} />
      <Box size={[WARMER_LENGTH - 0.05, 0.62, 0.02]} position={[WARMER_X, 1.61, -0.28]} material={warmer} shadow={false} />
      {[0, 0.3].map((y) => (
        <Box key={y} size={[WARMER_LENGTH - 0.1, 0.02, 0.5 - y * 0.4]} position={[WARMER_X, 1.37 + y, -0.02 - y * 0.3]} material={parts.tray} shadow={false} />
      ))}
      <Batch geometry={ROUND} items={details.pastries} />
      <group position={[WARMER_X, 1.3, -0.26]}>
        <mesh rotation={[0, 0, Math.PI / 2]} material={parts.glass} raycast={noRaycast}>
          <cylinderGeometry args={[WARMER_RADIUS, WARMER_RADIUS, WARMER_LENGTH, 18, 1, true, 0, Math.PI / 2]} />
        </mesh>
        {[-WARMER_LENGTH / 2, WARMER_LENGTH / 2].map((x) => (
          <group key={x} position={[x, 0, 0]} rotation={[0, -Math.PI / 2, 0]}>
            <mesh material={parts.glass} raycast={noRaycast}>
              <circleGeometry args={[WARMER_RADIUS, 18, 0, Math.PI / 2]} />
            </mesh>
            <mesh material={BRONZE} raycast={noRaycast}>
              <torusGeometry args={[WARMER_RADIUS, 0.022, 6, 18, Math.PI / 2]} />
            </mesh>
          </group>
        ))}
        <mesh position={[0, WARMER_RADIUS, 0]} rotation={[0, 0, Math.PI / 2]} material={BRONZE} raycast={noRaycast}>
          <cylinderGeometry args={[0.022, 0.022, WARMER_LENGTH, 6]} />
        </mesh>
      </group>

      {/* 계산대 */}
      <Box size={[0.42, 0.05, 0.3]} position={[0.42, 1.265, 0.02]} material={parts.pos} />
      <Box size={[0.07, 0.24, 0.07]} position={[0.42, 1.38, -0.06]} material={parts.pos} />
      <Box size={[0.62, 0.42, 0.05]} position={[0.42, 1.62, -0.04]} material={parts.pos} rotation={[-0.2, 0, 0]} />
      <Box size={[0.54, 0.34, 0.01]} position={[0.42, 1.625, -0.01]} material={parts.screen} rotation={[-0.2, 0, 0]} shadow={false} />
      <Box size={[0.44, 0.1, 0.34]} position={[0.42, 1.29, 0.36]} material={parts.pos} />
      <Box size={[0.36, 0.62, 0.34]} position={[1.2, 1.55, -0.04]} material={parts.terminal} rounded={0.03} />
      <Box size={[0.24, 0.16, 0.01]} position={[1.2, 1.68, 0.135]} material={parts.pos} shadow={false} />
      <Box size={[0.24, 0.24, 0.01]} position={[1.2, 1.42, 0.135]} material={parts.pos} shadow={false} />
      <Plant position={[1.78, 1.24, -0.1]} scale={1.25} />
      <Plaque text="즉석조리" size={[1.5, 0.42]} position={[0, 2.3, 0]} />
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
  /** 나뭇결을 입히는 진열대 */
  wood?: boolean;
  hitSize: Vec3;
  hitY: number;
  /** 바닥 그림자 크기 */
  footprint: [number, number];
}

const SAGE = "#6d7f62";
const WOOD = "#ad763a";

// 참고 이미지의 바닥 좌표를 방 좌표로 환산한 위치다.
export const FIXTURES: FixtureSpec[] = [
  { category: "음료", position: [1.85, 0, -3.9], rotationY: 0, top: 3.1, bodyColor: SAGE, hitSize: [5.3, 3.1, 1.2], hitY: 1.55, footprint: [5.8, 1.8] },
  { category: "간편식사", position: [-4.15, 0, -3.95], rotationY: 0, top: 2.8, bodyColor: SAGE, hitSize: [4.9, 2.8, 1.1], hitY: 1.4, footprint: [5.4, 1.7] },
  { category: "식품", position: [-8.5, 0, -2.4], rotationY: Math.PI / 2, top: 2.8, bodyColor: WOOD, wood: true, hitSize: [4, 2.8, 0.95], hitY: 1.4, footprint: [4.5, 1.5] },
  { category: "과자류", position: [-1.15, 0, 0.3], rotationY: 0, top: 2, bodyColor: WOOD, wood: true, hitSize: [5.1, 2, 1.4], hitY: 1, footprint: [5.6, 2] },
  { category: "아이스크림", position: [6.15, 0, 1.15], rotationY: 0, top: 1.15, bodyColor: SAGE, hitSize: [3.9, 1.15, 1.9], hitY: 0.58, footprint: [4.4, 2.5] },
  { category: "즉석조리", position: [-5.15, 0, 3.8], rotationY: 0, top: 1.95, bodyColor: WOOD, wood: true, hitSize: [4.82, 1.95, 1.35], hitY: 0.98, footprint: [5.2, 1.8] },
];

/** 나무 진열대에 입히는 결 */
export const WOOD_GRAIN = paint(128, 256, (context, w, h) => {
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, w, h);
  for (let line = 0; line < 40; line++) {
    const x = (line * 53) % w;
    context.strokeStyle = line % 3 ? "rgba(110,70,30,0.13)" : "rgba(110,70,30,0.24)";
    context.lineWidth = 1 + (line % 2);
    context.beginPath();
    context.moveTo(x, 0);
    context.bezierCurveTo(x + 4, h * 0.3, x - 4, h * 0.7, x + 2, h);
    context.stroke();
  }
});

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
