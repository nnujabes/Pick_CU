import { Environment, Lightformer, OrthographicCamera } from "@react-three/drei";
import { useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { Category } from "@/api/types";
import { PANEL_WIDTH } from "@/components/SidePanel";
import { Batch, Box, FIXTURES, FixtureShape, noRaycast, UNIT_BOX, WOOD_GRAIN, type FixtureSpec } from "./fixtures";

const ROOM = { halfX: 9, halfZ: 4.5, height: 4.2, doorStart: 5.7 };
const AZIMUTH = THREE.MathUtils.degToRad(30);
const ELEVATION = THREE.MathUtils.degToRad(27);
const FOCUS_ELEVATION = THREE.MathUtils.degToRad(15);
const CAMERA_DISTANCE = 30;
const FOCUS_SECONDS = 0.6;
/** 정면을 볼 때 진열대 앞면에서 이 거리보다 앞에 있는 물건은 잘라 낸다. */
const FOCUS_CLEARANCE = 1.2;
const FIT_MARGIN = 1.04;
const BOOT_SECONDS = 0.9;
const PIN_LIFT = 0.95;

function cameraDirection(azimuth: number, elevation: number, target = new THREE.Vector3()) {
  return target.set(
    Math.sin(azimuth) * Math.cos(elevation),
    Math.sin(elevation),
    Math.cos(azimuth) * Math.cos(elevation),
  );
}

/** 점들이 화면에서 차지하는 중심과 크기를 카메라 방향에서 계산한다. */
function fitPoints(points: THREE.Vector3[]) {
  const forward = cameraDirection(AZIMUTH, ELEVATION).negate();
  const right = forward.clone().cross(new THREE.Vector3(0, 1, 0)).normalize();
  const up = right.clone().cross(forward);
  const us = points.map((point) => point.dot(right));
  const vs = points.map((point) => point.dot(up));
  const [minU, maxU, minV, maxV] = [Math.min(...us), Math.max(...us), Math.min(...vs), Math.max(...vs)];
  return {
    center: right.clone().multiplyScalar((minU + maxU) / 2).add(up.clone().multiplyScalar((minV + maxV) / 2)),
    width: maxU - minU,
    height: maxV - minV,
  };
}

const ROOM_FIT = fitPoints(
  [-ROOM.halfX - 0.2, ROOM.halfX].flatMap((x) =>
    [-ROOM.halfZ - 0.2, ROOM.halfZ].flatMap((z) => [-0.3, ROOM.height].map((y) => new THREE.Vector3(x, y, z))),
  ),
);
const FIXTURE_FIT = fitPoints(
  FIXTURES.flatMap((spec) => {
    const [width, , depth] = spec.hitSize;
    const alongX = spec.rotationY === 0 ? width / 2 : depth / 2;
    const alongZ = spec.rotationY === 0 ? depth / 2 : width / 2;
    return [-1, 1].flatMap((sx) =>
      [-1, 1].flatMap((sz) =>
        [0, spec.top + 0.6].map((y) => new THREE.Vector3(spec.position[0] + sx * alongX, y, spec.position[2] + sz * alongZ)),
      ),
    );
  }),
);

const LIME = new THREE.Color("#d4f27a");
const STRIP_ON = new THREE.Color("#ffe6bd");
const STRIP_OFF = new THREE.Color("#5a5346");
const STRIP_Y = 3.82;
const STRIPS: { position: [number, number, number]; size: [number, number, number] }[] = [
  ...[-6, -2.25, 1.8].map((x) => ({ position: [x, STRIP_Y, -4.42] as [number, number, number], size: [2.9, 0.07, 0.12] as [number, number, number] })),
  ...[-3.15, -0.3, 2.5].map((z) => ({ position: [-8.92, STRIP_Y, z] as [number, number, number], size: [0.12, 0.07, 2.5] as [number, number, number] })),
];
/** 천장 조명이 바닥에 반사되는 자리 */
const FLOOR_POOLS: [number, number][] = [
  [-5.6, -2], [-1.6, -2.2], [2.2, -2.3], [5.6, -2.4],
  [-6.6, 0.8], [-4.4, 1.3], [-1.2, 1.8], [2.4, 1], [3.4, 3.4], [-0.4, 3.6], [5.8, -0.5], [8, 0.8],
];

const damp = (current: number, target: number, delta: number, speed = 7) =>
  THREE.MathUtils.damp(current, target, speed, delta);

export interface TipEvent {
  category: Category;
  clientX: number;
  clientY: number;
}

interface Props {
  selected: Category[];
  pinned: Partial<Record<Category, number>>;
  focused: Category | null;
  highlighted: Category[];
  hovered: Category | null;
  reduced: boolean;
  onHover: (tip: TipEvent | null) => void;
  onActivate: (tip: TipEvent) => void;
}

function canvasTexture(width: number, height: number, draw: (context: CanvasRenderingContext2D) => void) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (context) draw(context);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/** 큰 타일에 줄눈과 약간의 얼룩을 넣어 반복한다. */
function useFloorTexture() {
  return useMemo(() => {
    const texture = canvasTexture(512, 512, (context) => {
      context.fillStyle = "#a89d87";
      context.fillRect(0, 0, 512, 512);
      const tones = ["#ece2cd", "#e6dbc5", "#efe6d2", "#e9dfc9"];
      for (let row = 0; row < 2; row++) {
        for (let column = 0; column < 2; column++) {
          context.fillStyle = tones[(row * 2 + column) % tones.length];
          context.fillRect(column * 256 + 2, row * 256 + 2, 252, 252);
        }
      }
    });
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set((ROOM.halfX * 2) / 2.8, (ROOM.halfZ * 2) / 2.8);
    texture.anisotropy = 8;
    return texture;
  }, []);
}

/** 징두리 벽의 세로 홈 */
function slatTexture(width: number) {
  const texture = canvasTexture(64, 16, (context) => {
    context.fillStyle = "#6f8064";
    context.fillRect(0, 0, 64, 16);
    context.fillStyle = "#566650";
    for (let x = 0; x < 64; x += 16) context.fillRect(x, 0, 3, 16);
  });
  texture.wrapS = THREE.RepeatWrapping;
  texture.repeat.set(width / 0.5, 1);
  return texture;
}

/** 가구 아래가 바닥에 붙어 보이도록 까는 부드러운 그림자 */
const CONTACT_SHADOW = (() => {
  const texture = canvasTexture(128, 128, (context) => {
    const image = context.createImageData(128, 128);
    for (let y = 0; y < 128; y++) {
      for (let x = 0; x < 128; x++) {
        const edge = Math.min(x, 127 - x, y, 127 - y) / 28;
        const alpha = Math.min(1, edge) ** 2;
        image.data[(y * 128 + x) * 4 + 3] = alpha * 120;
      }
    }
    context.putImageData(image, 0, 0);
  });
  return new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false, color: "#17140c" });
})();

/** 냉장고·온장고 불빛이 바닥에 번지는 효과 */
function glowMaterial(color: string) {
  const texture = canvasTexture(128, 128, (context) => {
    const gradient = context.createRadialGradient(64, 64, 4, 64, 64, 64);
    gradient.addColorStop(0, "rgba(255,255,255,0.55)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    context.fillStyle = gradient;
    context.fillRect(0, 0, 128, 128);
  });
  return new THREE.MeshBasicMaterial({ map: texture, color, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false });
}

/** 벽 조명이 아래로 번지는 빛 */
const WALL_WASH = (() => {
  const texture = canvasTexture(256, 128, (context) => {
    const gradient = context.createLinearGradient(0, 0, 0, 128);
    gradient.addColorStop(0, "rgba(255,255,255,0.9)");
    gradient.addColorStop(0.45, "rgba(255,255,255,0.3)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    context.fillStyle = gradient;
    context.fillRect(0, 0, 256, 128);
    context.globalCompositeOperation = "destination-in";
    const sides = context.createLinearGradient(0, 0, 256, 0);
    sides.addColorStop(0, "rgba(0,0,0,0)");
    sides.addColorStop(0.2, "rgba(0,0,0,1)");
    sides.addColorStop(0.8, "rgba(0,0,0,1)");
    sides.addColorStop(1, "rgba(0,0,0,0)");
    context.fillStyle = sides;
    context.fillRect(0, 0, 256, 128);
  });
  return new THREE.MeshBasicMaterial({ map: texture, color: "#7d5f31", transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false });
})();

function FloorDecal({ material, size, position, rotation = 0, y = 0.012 }: {
  material: THREE.Material;
  size: [number, number];
  position: [number, number];
  rotation?: number;
  y?: number;
}) {
  return (
    <mesh position={[position[0], y, position[1]]} rotation={[-Math.PI / 2, 0, rotation]} material={material} raycast={noRaycast}>
      <planeGeometry args={size} />
    </mesh>
  );
}

function Fixture({ spec, selected, active, highlighted, pinCount, reduced, onHover, onActivate }: {
  spec: FixtureSpec;
  selected: boolean;
  active: boolean;
  highlighted: boolean;
  pinCount: number;
  reduced: boolean;
  onHover: Props["onHover"];
  onActivate: Props["onActivate"];
}) {
  const body = useMemo(() => {
    const material = new THREE.MeshStandardMaterial({ color: spec.bodyColor, map: spec.wood ? WOOD_GRAIN : null, roughness: 0.55, metalness: 0.06 });
    material.emissive.copy(LIME);
    material.emissiveIntensity = 0;
    return material;
  }, [spec.bodyColor, spec.wood]);
  const warmer = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#ffcf8a", emissive: "#ff9f3d", emissiveIntensity: 0.8, transparent: true, opacity: 0.85 }),
    [],
  );
  const pin = useRef<THREE.Mesh>(null);
  const pinPop = useRef(0);
  const invalidate = useThree((state) => state.invalidate);
  const glow = active || highlighted ? 0.2 : selected ? 0.05 : 0;

  useEffect(() => invalidate(), [glow, pinCount, highlighted, invalidate]);

  useFrame(({ clock }, delta) => {
    body.emissiveIntensity = reduced ? glow : damp(body.emissiveIntensity, glow, delta, 12);
    const time = clock.elapsedTime;
    if (spec.category === "즉석조리" && !reduced) {
      // 온장고 안쪽만 천천히 변한다. 벽과 바닥을 비추는 조명은 고정이다.
      warmer.emissiveIntensity = 0.8 + Math.sin(time * 0.9) * 0.08;
    }
    if (pin.current) {
      const popTarget = highlighted ? 1 : 0;
      pinPop.current = reduced ? popTarget : damp(pinPop.current, popTarget, delta, 9);
      const bob = reduced ? 0 : Math.sin(time * 2.4) * 0.12;
      pin.current.position.y = spec.top + PIN_LIFT + bob + pinPop.current * 0.55;
      pin.current.scale.setScalar(1 + pinPop.current * 0.6);
      if (!reduced) pin.current.rotation.y = time * 1.5;
    }
  });

  const toTip = (event: ThreeEvent<PointerEvent | MouseEvent>): TipEvent => ({
    category: spec.category,
    clientX: event.nativeEvent.clientX,
    clientY: event.nativeEvent.clientY,
  });

  return (
    <>
      <FloorDecal
        material={CONTACT_SHADOW}
        size={spec.footprint}
        position={[spec.position[0], spec.position[2]]}
        rotation={spec.rotationY}
        y={0.02}
      />
      <group position={spec.position} rotation={[0, spec.rotationY, 0]}>
        <Suspense fallback={null}>
          <FixtureShape category={spec.category} body={body} warmer={warmer} />
        </Suspense>
        <mesh
          position={[0, spec.hitY, 0]}
          onPointerOver={(event) => {
            event.stopPropagation();
            if (event.nativeEvent.pointerType !== "touch") onHover(toTip(event));
          }}
          onPointerMove={(event) => {
            event.stopPropagation();
            if (event.nativeEvent.pointerType !== "touch") onHover(toTip(event));
          }}
          onPointerOut={(event) => {
            if (event.nativeEvent.pointerType !== "touch") onHover(null);
          }}
          onClick={(event) => {
            event.stopPropagation();
            onActivate(toTip(event));
          }}
        >
          <boxGeometry args={spec.hitSize} />
          <meshBasicMaterial transparent opacity={0} depthWrite={false} />
        </mesh>
      </group>
      {spec.category === "즉석조리" && (
        <pointLight color="#ffb060" intensity={5} distance={4} decay={2} position={[spec.position[0] - 1.36, 1.9, spec.position[2] + 0.9]} />
      )}
      {(pinCount > 0 || highlighted) && (
        <mesh
          ref={pin}
          position={[spec.position[0], spec.top + PIN_LIFT, spec.position[2]]}
          rotation={[Math.PI, 0, 0]}
          raycast={noRaycast}
        >
          <coneGeometry args={[0.24, 0.5, 18]} />
          <meshBasicMaterial color="#d4f27a" toneMapped={false} />
        </mesh>
      )}
    </>
  );
}

function Entrance() {
  const width = ROOM.halfX - ROOM.doorStart;
  const parts = useMemo(() => ({
    frame: new THREE.MeshStandardMaterial({ color: "#2a241e", roughness: 0.4, metalness: 0.65 }),
    view: new THREE.MeshBasicMaterial({
      toneMapped: false,
      map: canvasTexture(256, 256, (context) => {
        // 유리에 비친 매장: 어두운 바탕에 흐린 선반과 불빛
        const gradient = context.createLinearGradient(0, 0, 0, 256);
        gradient.addColorStop(0, "#14120f");
        gradient.addColorStop(1, "#241f18");
        context.fillStyle = gradient;
        context.fillRect(0, 0, 256, 256);
        context.filter = "blur(5px)";
        for (let row = 0; row < 4; row++) {
          for (let column = 0; column < 9; column++) {
            context.fillStyle = (row + column) % 3 ? "#54442a" : "#2d3a2c";
            context.fillRect(8 + column * 27, 60 + row * 32, 20, 20);
          }
        }
        context.filter = "none";
      }),
    }),
    glass: new THREE.MeshStandardMaterial({ color: "#d9e4e6", transparent: true, opacity: 0.1, roughness: 0.05, metalness: 0.3, depthWrite: false }),
    handle: new THREE.MeshStandardMaterial({ color: "#e2e3de", roughness: 0.25, metalness: 0.3 }),
  }), []);
  const glassHeight = ROOM.height - 0.65;
  return (
    <group position={[ROOM.doorStart + width / 2, 0, -ROOM.halfZ - 0.1]}>
      <Box size={[width, ROOM.height, 0.05]} position={[0, ROOM.height / 2, -0.03]} material={parts.view} shadow={false} />
      <Box size={[width, 0.55, 0.2]} position={[0, ROOM.height - 0.275, 0]} material={parts.frame} />
      <Box size={[width, 0.1, 0.2]} position={[0, 0.05, 0]} material={parts.frame} />
      {[-width / 2 + 0.06, 0, width / 2 - 0.06].map((x) => (
        <Box key={x} size={[x === 0 ? 0.08 : 0.12, ROOM.height, 0.2]} position={[x, ROOM.height / 2, 0]} material={parts.frame} />
      ))}
      <Box size={[width - 0.1, glassHeight, 0.02]} position={[0, 0.1 + glassHeight / 2, 0.04]} material={parts.glass} shadow={false} />
      {[-0.17, 0.17].map((x) => (
        <Box key={x} size={[0.045, 1.5, 0.05]} position={[x, 1.45, 0.17]} material={parts.handle} />
      ))}
    </group>
  );
}

function StoreProps() {
  const parts = useMemo(() => ({
    bin: new THREE.MeshStandardMaterial({ color: "#c9ccc9", roughness: 0.3, metalness: 0.4 }),
    binLid: new THREE.MeshStandardMaterial({ color: "#26282a", roughness: 0.45, metalness: 0.5 }),
    mat: new THREE.MeshStandardMaterial({ color: "#3f4d38", roughness: 0.95 }),
    basket: new THREE.MeshStandardMaterial({ color: "#54634c", roughness: 0.65 }),
    basketInside: new THREE.MeshStandardMaterial({ color: "#2a3327", roughness: 0.8 }),
    stool: new THREE.MeshStandardMaterial({ color: "#c3a06a", roughness: 0.3, metalness: 0.4 }),
    seat: new THREE.MeshStandardMaterial({ color: "#59684f", roughness: 0.7 }),
  }), []);
  return (
    <>
      <Box size={[2.5, 0.025, 1.45]} position={[7, 0.02, -3.72]} material={parts.mat} shadow={false} />
      {[0, 1, 2, 3].map((index) => (
        <Box key={index} size={[0.72, 0.13, 0.52]} position={[8.4, 0.08 + index * 0.11, -1.45]} material={parts.basket} rounded={0.025} />
      ))}
      <Box size={[0.6, 0.01, 0.4]} position={[8.4, 0.475, -1.45]} material={parts.basketInside} shadow={false} />
      <mesh position={[8.65, 0.42, 4.03]} material={parts.bin} castShadow raycast={noRaycast}>
        <cylinderGeometry args={[0.27, 0.27, 0.84, 20]} />
      </mesh>
      <mesh position={[8.65, 0.85, 4.03]} material={parts.binLid} castShadow raycast={noRaycast}>
        <cylinderGeometry args={[0.28, 0.28, 0.04, 20]} />
      </mesh>
      <mesh position={[-2.1, 0.03, 4.07]} material={parts.stool} raycast={noRaycast}>
        <cylinderGeometry args={[0.2, 0.22, 0.05, 18]} />
      </mesh>
      <mesh position={[-2.1, 0.38, 4.07]} material={parts.stool} castShadow raycast={noRaycast}>
        <cylinderGeometry args={[0.03, 0.04, 0.7, 10]} />
      </mesh>
      <mesh position={[-2.1, 0.77, 4.07]} material={parts.seat} castShadow raycast={noRaycast}>
        <cylinderGeometry args={[0.24, 0.24, 0.1, 18]} />
      </mesh>
    </>
  );
}

/** 3D 박스에 남는 위아래를 채우는 밤 동네: 인도, 찻길, 뒤쪽 건물과 불 켜진 창 */
function Neighborhood() {
  const parts = useMemo(() => ({
    road: new THREE.MeshBasicMaterial({ color: "#171716", toneMapped: false }),
    sidewalk: new THREE.MeshBasicMaterial({ color: "#2b2b29", toneMapped: false }),
    curb: new THREE.MeshBasicMaterial({ color: "#4a4a46", toneMapped: false }),
    lane: new THREE.MeshBasicMaterial({ color: "#5f5f5a", toneMapped: false }),
    buildingA: new THREE.MeshBasicMaterial({ color: "#121315", toneMapped: false }),
    buildingB: new THREE.MeshBasicMaterial({ color: "#191a1c", toneMapped: false }),
    window: new THREE.MeshBasicMaterial({ toneMapped: false }),
  }), []);
  const buildings = useMemo(() => [
    { x: -14, width: 10, height: 20, material: parts.buildingB },
    { x: -4, width: 10, height: 26, material: parts.buildingA },
    { x: 6, width: 10, height: 20, material: parts.buildingB },
    { x: 16, width: 10, height: 26, material: parts.buildingA },
    { x: 26, width: 10, height: 22, material: parts.buildingB },
  ], [parts]);
  const windows = useMemo(() => {
    const items: { position: [number, number, number]; size: [number, number, number]; color: string }[] = [];
    buildings.forEach((building, buildingIndex) => {
      for (let floor = 0; floor < 13; floor++) {
        for (let column = 0; column < 5; column++) {
          // 일정하게 흩어 놓은 켜진 창. 깜빡이지 않는다.
          const seed = (buildingIndex * 31 + floor * 17 + column * 7) % 9;
          if (seed > 1) continue;
          items.push({
            position: [building.x - 3.6 + column * 1.8, 1.2 + floor * 1.5, -9.98],
            size: [0.42, 0.6, 0.02],
            color: seed === 0 ? "#c9a771" : "#a58a5c",
          });
          items.push({
            position: [building.x - 3.6 + column * 1.8, 1.2 + floor * 1.5, -9.96],
            size: [0.025, 0.6, 0.02],
            color: "#3b3226",
          });
        }
      }
    });
    return items;
  }, [buildings]);
  return (
    <>
      <mesh position={[0, -0.34, 0]} rotation={[-Math.PI / 2, 0, 0]} material={parts.road} raycast={noRaycast}>
        <planeGeometry args={[110, 80]} />
      </mesh>
      <Box size={[110, 0.2, 2.6]} position={[0, -0.22, 5.9]} material={parts.sidewalk} shadow={false} />
      <Box size={[110, 0.22, 0.12]} position={[0, -0.21, 7.25]} material={parts.curb} shadow={false} />
      <Box size={[50, 0.2, 14.4]} position={[34.1, -0.22, -2.6]} material={parts.sidewalk} shadow={false} />
      {[-11, -4, 3, 10].map((x) => (
        <Box key={x} size={[3.4, 0.01, 0.12]} position={[x, -0.32, 10.4]} material={parts.lane} shadow={false} />
      ))}
      {buildings.map((building) => (
        <Box
          key={building.x}
          size={[building.width, building.height, 6]}
          position={[building.x, building.height / 2 - 0.3, -13]}
          material={building.material}
          shadow={false}
        />
      ))}
      <Batch geometry={UNIT_BOX} items={windows} material={parts.window} />
    </>
  );
}

export function StoreRoom({ selected, pinned, focused, highlighted, hovered, reduced, onHover, onActivate }: Props) {
  const camera = useRef<THREE.OrthographicCamera>(null);
  const hemisphere = useRef<THREE.HemisphereLight>(null);
  const sun = useRef<THREE.DirectionalLight>(null);
  const size = useThree((state) => state.size);
  const gl = useThree((state) => state.gl);
  const invalidate = useThree((state) => state.invalidate);
  const bootStart = useRef<number | null>(reduced ? -BOOT_SECONDS : null);
  const focusProgress = useRef(0);
  const lastFocus = useRef<FixtureSpec | null>(null);
  const floorTexture = useFloorTexture();
  const scratch = useMemo(() => ({
    direction: new THREE.Vector3(),
    focusLook: new THREE.Vector3(),
    look: new THREE.Vector3(),
  }), []);

  const backWallWidth = ROOM.halfX + ROOM.doorStart;
  const backWallX = (-ROOM.halfX + ROOM.doorStart) / 2;
  const leftDepth = ROOM.halfZ * 2;
  const materials = useMemo(() => ({
    floor: new THREE.MeshStandardMaterial({ map: floorTexture, roughness: 0.32, metalness: 0.02 }),
    slab: new THREE.MeshStandardMaterial({ color: "#d9d1bf", roughness: 0.8 }),
    wall: new THREE.MeshStandardMaterial({ color: "#e6dcc8", roughness: 0.85 }),
    wallCap: new THREE.MeshStandardMaterial({ color: "#6e6d68", roughness: 0.7 }),
    wainscotBack: new THREE.MeshStandardMaterial({ map: slatTexture(backWallWidth), roughness: 0.6 }),
    wainscotLeft: new THREE.MeshStandardMaterial({ map: slatTexture(leftDepth), roughness: 0.6 }),
    ledge: new THREE.MeshBasicMaterial({ color: "#ffd9a0", toneMapped: false }),
    pool: glowMaterial("#6e5634"),
    ledGlow: glowMaterial("#a8732f"),
  }), [floorTexture, backWallWidth, leftDepth]);
  const stripMaterials = useMemo(
    () => STRIPS.map(() => new THREE.MeshBasicMaterial({ color: STRIP_OFF.clone(), toneMapped: false })),
    [],
  );

  // 가로를 먼저 채운다. 박스가 납작해서 진열대가 잘리면 그때만 줄인다.
  const widthZoom = size.width / (ROOM_FIT.width * FIT_MARGIN);
  const baseZoom = Math.min(widthZoom, size.height / (FIXTURE_FIT.height * 1.03));
  const baseCenter = size.height / baseZoom >= ROOM_FIT.height ? ROOM_FIT.center : FIXTURE_FIT.center;

  useEffect(() => invalidate(), [focused, size.width, size.height, invalidate]);

  useFrame(({ clock }, delta) => {
    const cam = camera.current;
    if (!cam || !size.width || !size.height) return;
    const time = clock.elapsedTime;

    // 형광등: 처음 들어올 때 한 번만 차례로 켜진다.
    if (bootStart.current == null) bootStart.current = time;
    const boot = Math.min(1, (time - bootStart.current) / BOOT_SECONDS);
    stripMaterials.forEach((material, index) => {
      material.color.copy(boot >= (index + 1) / stripMaterials.length ? STRIP_ON : STRIP_OFF);
    });
    if (hemisphere.current) hemisphere.current.intensity = 0.5 + 0.55 * boot;
    if (sun.current) sun.current.intensity = 0.3 + 0.65 * boot;

    // 진열대를 열면 0.6초 동안 정면으로 돌며 다가가고, 닫으면 돌아온다.
    const focusedSpec = FIXTURES.find((spec) => spec.category === focused) ?? null;
    if (focusedSpec) lastFocus.current = focusedSpec;
    const goal = focusedSpec ? 1 : 0;
    if (reduced) {
      focusProgress.current = goal;
    } else {
      const step = delta / FOCUS_SECONDS;
      focusProgress.current = focusProgress.current < goal
        ? Math.min(goal, focusProgress.current + step)
        : Math.max(goal, focusProgress.current - step);
    }
    const eased = THREE.MathUtils.smoothstep(focusProgress.current, 0, 1);

    let azimuth = AZIMUTH;
    let elevation = ELEVATION;
    let zoom = baseZoom;
    let near = 0.1;
    scratch.look.copy(baseCenter);
    const spec = lastFocus.current;
    if (spec && eased > 0) {
      // 패널에 가리지 않는 부분의 가운데에 진열대가 오게 한다.
      const rect = gl.domElement.getBoundingClientRect();
      const isPhone = window.innerWidth <= 520;
      const overlap = isPhone ? 0 : Math.max(0, rect.right - (window.innerWidth - PANEL_WIDTH));
      const visibleWidth = Math.max(240, rect.width - overlap);
      const focusZoom = Math.min(visibleWidth / (spec.hitSize[0] * 1.12), rect.height / ((spec.top + 1.1) * 1.2));
      const shift = overlap / 2 / focusZoom;
      scratch.focusLook.set(
        spec.position[0] + Math.cos(spec.rotationY) * shift,
        spec.top * 0.5,
        spec.position[2] - Math.sin(spec.rotationY) * shift,
      );
      scratch.look.lerp(scratch.focusLook, eased);
      azimuth = THREE.MathUtils.lerp(AZIMUTH, spec.rotationY, eased);
      elevation = THREE.MathUtils.lerp(ELEVATION, FOCUS_ELEVATION, eased);
      zoom = THREE.MathUtils.lerp(baseZoom, focusZoom, eased);
      near = THREE.MathUtils.lerp(0.1, CAMERA_DISTANCE - spec.hitSize[2] / 2 - FOCUS_CLEARANCE, eased);
    }

    cameraDirection(azimuth, elevation, scratch.direction).multiplyScalar(CAMERA_DISTANCE);
    cam.position.copy(scratch.look).add(scratch.direction);
    cam.lookAt(scratch.look);
    cam.zoom = zoom;
    cam.near = near;
    cam.updateProjectionMatrix();
  });

  return (
    <>
      <OrthographicCamera makeDefault ref={camera} near={0.1} far={120} position={[15, 15, 22]} />
      <Environment resolution={64} frames={1} environmentIntensity={0.45}>
        <Lightformer intensity={2.2} position={[0, 8, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[18, 6, 1]} />
        <Lightformer intensity={0.9} position={[0, 2, 12]} scale={[20, 4, 1]} />
        <Lightformer intensity={0.5} position={[12, 3, 0]} rotation={[0, -Math.PI / 2, 0]} scale={[10, 4, 1]} />
      </Environment>
      <hemisphereLight ref={hemisphere} args={["#fff1d8", "#a08c6c", 0.5]} />
      <directionalLight
        ref={sun}
        color="#ffe9c9"
        position={[5, 16, 8]}
        intensity={0.3}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-14}
        shadow-camera-right={14}
        shadow-camera-top={11}
        shadow-camera-bottom={-11}
        shadow-camera-near={1}
        shadow-camera-far={45}
        shadow-bias={-0.0006}
        shadow-normalBias={0.02}
        shadow-radius={5}
      />

      <Neighborhood />

      {/* 바닥 */}
      <Box size={[ROOM.halfX * 2 + 0.2, 0.28, leftDepth + 0.2]} position={[-0.1, -0.16, -0.1]} material={materials.slab} shadow={false} />
      <mesh position={[0, 0, 0]} rotation={[-Math.PI / 2, 0, 0]} material={materials.floor} receiveShadow raycast={noRaycast}>
        <planeGeometry args={[ROOM.halfX * 2, leftDepth]} />
      </mesh>
      {FLOOR_POOLS.map((pool) => (
        <FloorDecal key={pool.join()} material={materials.pool} size={[2.6, 2.2]} position={pool} y={0.03} />
      ))}
      <FloorDecal material={materials.ledGlow} size={[5.6, 0.9]} position={[-5.15, 4.5 - 0.02]} y={0.03} />
      <FloorDecal material={materials.ledGlow} size={[4.6, 1]} position={[6.15, 2.15]} y={0.03} />

      {/* 뒷벽과 왼쪽 벽 */}
      <Box size={[backWallWidth, ROOM.height, 0.2]} position={[backWallX, ROOM.height / 2, -ROOM.halfZ - 0.1]} material={materials.wall} />
      <Box size={[0.2, ROOM.height, leftDepth + 0.2]} position={[-ROOM.halfX - 0.1, ROOM.height / 2, -0.1]} material={materials.wall} />
      <Box size={[backWallWidth, 0.95, 0.03]} position={[backWallX, 0.475, -ROOM.halfZ + 0.015]} material={materials.wainscotBack} shadow={false} />
      <Box size={[0.03, 0.95, leftDepth]} position={[-ROOM.halfX + 0.015, 0.475, 0]} material={materials.wainscotLeft} shadow={false} />
      <Box size={[backWallWidth, 0.025, 0.05]} position={[backWallX, 0.965, -ROOM.halfZ + 0.03]} material={materials.ledge} shadow={false} />
      <Box size={[0.05, 0.025, leftDepth]} position={[-ROOM.halfX + 0.03, 0.965, 0]} material={materials.ledge} shadow={false} />
      <Box size={[backWallWidth + 0.2, 0.14, 0.24]} position={[backWallX - 0.1, ROOM.height + 0.07, -ROOM.halfZ - 0.1]} material={materials.wallCap} shadow={false} />
      <Box size={[0.24, 0.14, leftDepth + 0.2]} position={[-ROOM.halfX - 0.1, ROOM.height + 0.07, -0.1]} material={materials.wallCap} shadow={false} />

      {/* 벽 조명과 벽에 번지는 빛 */}
      {STRIPS.map((strip, index) => {
        const alongX = strip.size[0] > strip.size[2];
        const length = Math.max(strip.size[0], strip.size[2]);
        return (
          <group key={index}>
            <Box size={strip.size} position={strip.position} material={stripMaterials[index]} shadow={false} />
            <mesh
              position={alongX ? [strip.position[0], STRIP_Y - 1.3, -ROOM.halfZ + 0.025] : [-ROOM.halfX + 0.025, STRIP_Y - 1.3, strip.position[2]]}
              rotation={[0, alongX ? 0 : Math.PI / 2, 0]}
              material={WALL_WASH}
              raycast={noRaycast}
            >
              <planeGeometry args={[length + 1.6, 2.6]} />
            </mesh>
          </group>
        );
      })}

      <Entrance />
      <StoreProps />

      {FIXTURES.map((spec) => (
        <Fixture
          key={spec.category}
          spec={spec}
          selected={selected.includes(spec.category)}
          active={hovered === spec.category || focused === spec.category}
          highlighted={highlighted.includes(spec.category)}
          pinCount={pinned[spec.category] ?? 0}
          reduced={reduced}
          onHover={onHover}
          onActivate={onActivate}
        />
      ))}
    </>
  );
}
