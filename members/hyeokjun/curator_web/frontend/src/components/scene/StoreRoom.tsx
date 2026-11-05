import { Environment, Lightformer, OrthographicCamera } from "@react-three/drei";
import { useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { Category } from "@/api/types";
import { PANEL_WIDTH } from "@/components/SidePanel";
import { Batch, Box, FIXTURES, FixtureShape, noRaycast, Plaque, UNIT_BOX, type FixtureSpec } from "./fixtures";

const ROOM = { halfX: 9, halfZ: 4.5, height: 3.4, doorStart: 5.7 };
const AZIMUTH = THREE.MathUtils.degToRad(30);
const ELEVATION = THREE.MathUtils.degToRad(30);
const FOCUS_ELEVATION = THREE.MathUtils.degToRad(15);
const CAMERA_DISTANCE = 30;
const FOCUS_SECONDS = 0.6;
/** 정면을 볼 때 진열대 앞면에서 이 거리보다 앞에 있는 물건은 잘라 낸다. */
const FOCUS_CLEARANCE = 1.5;
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
const STRIP_ON = new THREE.Color("#fffdf2");
const STRIP_OFF = new THREE.Color("#55574d");
const STRIPS: { position: [number, number, number]; size: [number, number, number] }[] = [
  ...[-6, -2, 2].map((x) => ({ position: [x, 3.14, -4.27] as [number, number, number], size: [2.6, 0.1, 0.2] as [number, number, number] })),
  ...[-3, 0, 3].map((z) => ({ position: [-8.78, 3.14, z] as [number, number, number], size: [0.2, 0.1, 2.2] as [number, number, number] })),
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

/** 타일 한 장에 줄눈과 약간의 얼룩을 넣어 반복한다. */
function useFloorTexture() {
  return useMemo(() => {
    const texture = canvasTexture(256, 256, (context) => {
      context.fillStyle = "#8f8d82";
      context.fillRect(0, 0, 256, 256);
      const tones = ["#c6c3b7", "#bfbcb0", "#cbc8bd", "#c2bfb3"];
      for (let row = 0; row < 2; row++) {
        for (let column = 0; column < 2; column++) {
          context.fillStyle = tones[(row * 2 + column) % tones.length];
          context.fillRect(column * 128 + 2, row * 128 + 2, 124, 124);
        }
      }
    });
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(ROOM.halfX, ROOM.halfZ);
    texture.anisotropy = 8;
    return texture;
  }, []);
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
    const material = new THREE.MeshStandardMaterial({ color: spec.bodyColor, roughness: 0.55, metalness: 0.08 });
    material.emissive.copy(LIME);
    material.emissiveIntensity = 0;
    return material;
  }, [spec.bodyColor]);
  const warmer = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#ffcf8a", emissive: "#ff9f3d", emissiveIntensity: 0.8, transparent: true, opacity: 0.85 }),
    [],
  );
  const pin = useRef<THREE.Mesh>(null);
  const pinPop = useRef(0);
  const invalidate = useThree((state) => state.invalidate);
  const glow = active || highlighted ? 0.5 : selected ? 0.16 : 0;

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
        <pointLight color="#ffa64d" intensity={12} distance={6} decay={2} position={[spec.position[0] - 1.2, 1.9, spec.position[2] + 0.9]} />
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
    frame: new THREE.MeshStandardMaterial({ color: "#2c312e", roughness: 0.45, metalness: 0.55 }),
    night: new THREE.MeshBasicMaterial({ color: "#141b24", toneMapped: false }),
    glass: new THREE.MeshStandardMaterial({ color: "#bcd8ea", transparent: true, opacity: 0.16, roughness: 0.05, metalness: 0.2, depthWrite: false }),
    lamp: new THREE.MeshBasicMaterial({ color: "#f2b46a", toneMapped: false }),
    handle: new THREE.MeshStandardMaterial({ color: "#c9ccc6", roughness: 0.3, metalness: 0.8 }),
  }), []);
  return (
    <group position={[ROOM.doorStart + width / 2, 0, -ROOM.halfZ - 0.08]}>
      <Box size={[width, 3.4, 0.05]} position={[0, 1.7, -0.02]} material={parts.night} shadow={false} />
      {([[-0.9, 2.25, 0.08], [0.35, 2.05, 0.05], [1, 2.4, 0.06]] as const).map(([x, y, size]) => (
        <Box key={x} size={[size, size, 0.01]} position={[x, y, 0.02]} material={parts.lamp} shadow={false} />
      ))}
      <Box size={[width, 0.3, 0.14]} position={[0, 3.25, 0.05]} material={parts.frame} />
      <Box size={[width, 0.08, 0.14]} position={[0, 0.04, 0.05]} material={parts.frame} />
      {[-width / 2 + 0.04, 0, width / 2 - 0.04].map((x) => (
        <Box key={x} size={[0.08, 3.1, 0.14]} position={[x, 1.55, 0.05]} material={parts.frame} />
      ))}
      <Box size={[width - 0.1, 3.1, 0.02]} position={[0, 1.55, 0.05]} material={parts.glass} shadow={false} />
      <Box size={[0.04, 0.7, 0.05]} position={[-0.12, 1.2, 0.16]} material={parts.handle} />
      <Box size={[0.04, 0.7, 0.05]} position={[0.12, 1.2, 0.16]} material={parts.handle} />
    </group>
  );
}

function StoreProps() {
  const parts = useMemo(() => ({
    bin: new THREE.MeshStandardMaterial({ color: "#4d5359", roughness: 0.5, metalness: 0.4 }),
    binLid: new THREE.MeshStandardMaterial({ color: "#2f3438", roughness: 0.5, metalness: 0.3 }),
    mat: new THREE.MeshStandardMaterial({ color: "#3a4a41", roughness: 0.95 }),
    basket: new THREE.MeshStandardMaterial({ color: "#a3543f", roughness: 0.6 }),
    stool: new THREE.MeshStandardMaterial({ color: "#8d9490", roughness: 0.35, metalness: 0.7 }),
    seat: new THREE.MeshStandardMaterial({ color: "#3f4640", roughness: 0.7 }),
  }), []);
  return (
    <>
      <Box size={[2.2, 0.02, 1.2]} position={[7.35, 0.02, -3.55]} material={parts.mat} shadow={false} />
      {[0, 1, 2, 3].map((index) => (
        <Box key={index} size={[0.62, 0.11, 0.42]} position={[8.3, 0.08 + index * 0.1, -1.9]} material={parts.basket} rounded={0.02} />
      ))}
      <mesh position={[8.3, 0.36, 3.2]} material={parts.bin} castShadow raycast={noRaycast}>
        <cylinderGeometry args={[0.26, 0.22, 0.72, 16]} />
      </mesh>
      <mesh position={[8.3, 0.75, 3.2]} material={parts.binLid} castShadow raycast={noRaycast}>
        <cylinderGeometry args={[0.28, 0.28, 0.06, 16]} />
      </mesh>
      <mesh position={[-2.1, 0.33, 3.7]} material={parts.stool} castShadow raycast={noRaycast}>
        <cylinderGeometry args={[0.03, 0.05, 0.62, 10]} />
      </mesh>
      <mesh position={[-2.1, 0.66, 3.7]} material={parts.seat} castShadow raycast={noRaycast}>
        <cylinderGeometry args={[0.2, 0.2, 0.07, 16]} />
      </mesh>
    </>
  );
}

/** 3D 박스에 남는 위아래를 채우는 밤 동네: 인도, 찻길, 뒤쪽 건물과 불 켜진 창 */
function Neighborhood() {
  const parts = useMemo(() => ({
    road: new THREE.MeshBasicMaterial({ color: "#191a17", toneMapped: false }),
    sidewalk: new THREE.MeshStandardMaterial({ color: "#4a4b44", roughness: 0.95 }),
    curb: new THREE.MeshStandardMaterial({ color: "#6d6e65", roughness: 0.9 }),
    lane: new THREE.MeshBasicMaterial({ color: "#55564d", toneMapped: false }),
    buildingA: new THREE.MeshBasicMaterial({ color: "#26282a", toneMapped: false }),
    buildingB: new THREE.MeshBasicMaterial({ color: "#2e2f2c", toneMapped: false }),
    window: new THREE.MeshBasicMaterial({ toneMapped: false }),
  }), []);
  const buildings = useMemo(() => [
    { x: -10, width: 8, depth: 6, height: 8, material: parts.buildingA },
    { x: -1.5, width: 8, depth: 6, height: 6.2, material: parts.buildingB },
    { x: 7, width: 8, depth: 6, height: 9, material: parts.buildingA },
    { x: 15.5, width: 8, depth: 6, height: 6.8, material: parts.buildingB },
  ], [parts]);
  const windows = useMemo(() => {
    const items: { position: [number, number, number]; size: [number, number, number]; color: string }[] = [];
    buildings.forEach((building, buildingIndex) => {
      for (let floor = 0; floor * 1.4 + 1 < building.height - 0.5; floor++) {
        for (let column = 0; column < 5; column++) {
          // 일정하게 흩어 놓은 켜진 창. 깜빡이지 않는다.
          const seed = (buildingIndex * 31 + floor * 17 + column * 7) % 10;
          if (seed > 3) continue;
          items.push({
            position: [building.x - 3 + column * 1.5, floor * 1.4 + 1, -9.98],
            size: [0.55, 0.65, 0.02],
            color: seed === 0 ? "#9a7443" : "#6e6c55",
          });
        }
      }
    });
    return items;
  }, [buildings]);
  return (
    <>
      <mesh position={[0, -0.34, 0]} rotation={[-Math.PI / 2, 0, 0]} material={parts.road} raycast={noRaycast}>
        <planeGeometry args={[90, 70]} />
      </mesh>
      <Box size={[90, 0.2, 3]} position={[0, -0.22, 6.1]} material={parts.sidewalk} shadow={false} />
      <Box size={[90, 0.22, 0.14]} position={[0, -0.21, 7.65]} material={parts.curb} shadow={false} />
      <Box size={[36, 0.2, 14.6]} position={[27.1, -0.22, -2.7]} material={parts.sidewalk} shadow={false} />
      {[-9, -3, 3, 9].map((x) => (
        <Box key={x} size={[3, 0.01, 0.14]} position={[x, -0.32, 10.2]} material={parts.lane} shadow={false} />
      ))}
      {buildings.map((building) => (
        <Box
          key={building.x}
          size={[building.width, building.height, building.depth]}
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

  const materials = useMemo(() => ({
    floor: new THREE.MeshStandardMaterial({ map: floorTexture, roughness: 0.42, metalness: 0.02 }),
    slab: new THREE.MeshStandardMaterial({ color: "#3a3b35", roughness: 0.9 }),
    wall: new THREE.MeshStandardMaterial({ color: "#efece4", roughness: 0.85 }),
    wainscot: new THREE.MeshStandardMaterial({ color: "#c7cbbd", roughness: 0.6 }),
    baseboard: new THREE.MeshStandardMaterial({ color: "#5d6058", roughness: 0.6 }),
    trim: new THREE.MeshStandardMaterial({ color: "#3d3f38", roughness: 0.6 }),
    fridgeGlow: glowMaterial("#a9d4f5"),
    coolerGlow: glowMaterial("#c7f0e3"),
    warmGlow: glowMaterial("#ffa64d"),
  }), [floorTexture]);
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
    if (!cam) return;
    const time = clock.elapsedTime;

    // 형광등: 처음 들어올 때 한 번만 차례로 켜진다.
    if (bootStart.current == null) bootStart.current = time;
    const boot = Math.min(1, (time - bootStart.current) / BOOT_SECONDS);
    stripMaterials.forEach((material, index) => {
      material.color.copy(boot >= (index + 1) / stripMaterials.length ? STRIP_ON : STRIP_OFF);
    });
    if (hemisphere.current) hemisphere.current.intensity = 0.45 + 0.9 * boot;
    if (sun.current) sun.current.intensity = 0.3 + 1.35 * boot;

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

  const backWallWidth = ROOM.halfX + ROOM.doorStart;
  const backWallX = (-ROOM.halfX + ROOM.doorStart) / 2;
  const leftDepth = ROOM.halfZ * 2;

  return (
    <>
      <OrthographicCamera makeDefault ref={camera} near={0.1} far={120} position={[15, 15, 22]} />
      <Environment resolution={64} frames={1} environmentIntensity={0.45}>
        <Lightformer intensity={2.2} position={[0, 8, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[18, 6, 1]} />
        <Lightformer intensity={0.9} position={[0, 2, 12]} scale={[20, 4, 1]} />
        <Lightformer intensity={0.5} position={[12, 3, 0]} rotation={[0, -Math.PI / 2, 0]} scale={[10, 4, 1]} />
      </Environment>
      <hemisphereLight ref={hemisphere} args={["#fffdf6", "#6b6a5e", 0.45]} />
      <directionalLight
        ref={sun}
        position={[6, 16, 9]}
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
      <FloorDecal material={materials.fridgeGlow} size={[7, 3.2]} position={[2.2, -2.7]} y={0.03} />
      <FloorDecal material={materials.coolerGlow} size={[5.8, 3]} position={[-3.6, -2.8]} y={0.03} />
      <FloorDecal material={materials.warmGlow} size={[3.8, 1.8]} position={[-6.2, 4.3]} y={0.03} />

      {/* 뒷벽과 왼쪽 벽 */}
      <Box size={[backWallWidth, ROOM.height, 0.2]} position={[backWallX, ROOM.height / 2, -ROOM.halfZ - 0.1]} material={materials.wall} />
      <Box size={[0.2, ROOM.height, leftDepth + 0.2]} position={[-ROOM.halfX - 0.1, ROOM.height / 2, -0.1]} material={materials.wall} />
      <Box size={[backWallWidth, 0.85, 0.03]} position={[backWallX, 0.425, -ROOM.halfZ + 0.015]} material={materials.wainscot} shadow={false} />
      <Box size={[0.03, 0.85, leftDepth]} position={[-ROOM.halfX + 0.015, 0.425, 0]} material={materials.wainscot} shadow={false} />
      <Box size={[backWallWidth, 0.14, 0.05]} position={[backWallX, 0.07, -ROOM.halfZ + 0.04]} material={materials.baseboard} shadow={false} />
      <Box size={[0.05, 0.14, leftDepth]} position={[-ROOM.halfX + 0.04, 0.07, 0]} material={materials.baseboard} shadow={false} />
      <Box size={[backWallWidth, 0.06, 0.04]} position={[backWallX, 0.87, -ROOM.halfZ + 0.03]} material={materials.trim} shadow={false} />
      <Box size={[0.04, 0.06, leftDepth]} position={[-ROOM.halfX + 0.03, 0.87, 0]} material={materials.trim} shadow={false} />
      <Box size={[backWallWidth + 0.2, 0.06, 0.24]} position={[backWallX - 0.1, ROOM.height + 0.03, -ROOM.halfZ - 0.1]} material={materials.trim} shadow={false} />
      <Box size={[0.24, 0.06, leftDepth + 0.2]} position={[-ROOM.halfX - 0.1, ROOM.height + 0.03, -0.1]} material={materials.trim} shadow={false} />

      {/* 형광등 */}
      {STRIPS.map((strip, index) => (
        <Box key={index} size={strip.size} position={strip.position} material={stripMaterials[index]} shadow={false} />
      ))}

      <Plaque text="Pick CU" size={[2.4, 0.66]} position={[-8.3, 2.7, 3]} background="#d4f27a" color="#1b2109" fontScale={0.66} />
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
