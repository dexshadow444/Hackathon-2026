/**
 * JM Vertex Hackathon 2027 · Award-Winning 3D Interactive WebGL Hero
 * Powered by Three.js · Optimized 60FPS Reactive Mesh & Particle Network
 */
(() => {
  const container = document.getElementById("hero3dContainer");
  if (!container || typeof THREE === "undefined") return;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Scene, Camera, Renderer
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
  camera.position.z = 28;

  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "high-performance" });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  container.appendChild(renderer.domElement);

  // Group to hold all 3D objects
  const mainGroup = new THREE.Group();
  scene.add(mainGroup);

  // Colors
  const COLOR_EMERALD = 0x10b981; // #10B981 Vibrant Green
  const COLOR_CYAN = 0x38bdf8;    // #38BDF8 Electric Light Blue
  const COLOR_DARK = 0x064e3b;    // Dark Pine

  // 1. Centerpiece: Futuristic 3D Geometric Polyhedron (Icosahedron + Wireframe)
  const coreGeo = new THREE.IcosahedronGeometry(7.2, 1);
  const coreMat = new THREE.MeshPhongMaterial({
    color: 0x052e20,
    emissive: 0x064e3b,
    specular: 0x38bdf8,
    shininess: 90,
    wireframe: true,
    transparent: true,
    opacity: 0.65,
  });
  const coreMesh = new THREE.Mesh(coreGeo, coreMat);
  mainGroup.add(coreMesh);

  // Inner solid core with glass-like translucency
  const innerGeo = new THREE.IcosahedronGeometry(5.2, 0);
  const innerMat = new THREE.MeshPhongMaterial({
    color: COLOR_CYAN,
    emissive: 0x04281d,
    specular: 0xffffff,
    shininess: 100,
    flatShading: true,
    transparent: true,
    opacity: 0.35,
  });
  const innerMesh = new THREE.Mesh(innerGeo, innerMat);
  mainGroup.add(innerMesh);

  // 2. Vertex Highlight Nodes (Glowing Points)
  const posAttribute = coreGeo.attributes.position;
  const vertexPointsGeo = new THREE.BufferGeometry();
  const vertexPositions = [];
  for (let i = 0; i < posAttribute.count; i++) {
    vertexPositions.push(posAttribute.getX(i), posAttribute.getY(i), posAttribute.getZ(i));
  }
  vertexPointsGeo.setAttribute('position', new THREE.Float32BufferAttribute(vertexPositions, 3));
  const vertexPointsMat = new THREE.PointsMaterial({
    color: COLOR_CYAN,
    size: 0.45,
    transparent: true,
    opacity: 0.9,
  });
  const vertexPoints = new THREE.Points(vertexPointsGeo, vertexPointsMat);
  mainGroup.add(vertexPoints);

  // 3. Dual Cyber Orbital Rings
  const ring1Geo = new THREE.TorusGeometry(10.5, 0.08, 16, 100);
  const ring1Mat = new THREE.MeshBasicMaterial({ color: COLOR_CYAN, transparent: true, opacity: 0.55 });
  const ring1 = new THREE.Mesh(ring1Geo, ring1Mat);
  ring1.rotation.x = Math.PI / 2.8;
  mainGroup.add(ring1);

  const ring2Geo = new THREE.TorusGeometry(12.2, 0.06, 16, 100);
  const ring2Mat = new THREE.MeshBasicMaterial({ color: COLOR_EMERALD, transparent: true, opacity: 0.4 });
  const ring2 = new THREE.Mesh(ring2Geo, ring2Mat);
  ring2.rotation.y = Math.PI / 3.2;
  ring2.rotation.x = -Math.PI / 6;
  mainGroup.add(ring2);

  // 4. Ambient 3D Particle Cloud (Star Dust)
  const particleCount = 450;
  const particlesGeo = new THREE.BufferGeometry();
  const particlePositions = new Float32Array(particleCount * 3);
  const particleColors = new Float32Array(particleCount * 3);

  const col1 = new THREE.Color(COLOR_EMERALD);
  const col2 = new THREE.Color(COLOR_CYAN);
  const col3 = new THREE.Color(0xffffff);

  for (let i = 0; i < particleCount; i++) {
    const r = 14 + Math.random() * 22;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos((Math.random() * 2) - 1);

    particlePositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    particlePositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    particlePositions[i * 3 + 2] = r * Math.cos(phi);

    const c = Math.random() > 0.5 ? col1 : (Math.random() > 0.5 ? col2 : col3);
    particleColors[i * 3] = c.r;
    particleColors[i * 3 + 1] = c.g;
    particleColors[i * 3 + 2] = c.b;
  }

  particlesGeo.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
  particlesGeo.setAttribute("color", new THREE.BufferAttribute(particleColors, 3));

  const particlesMat = new THREE.PointsMaterial({
    size: 0.32,
    vertexColors: true,
    transparent: true,
    opacity: 0.7,
  });
  const particleSystem = new THREE.Points(particlesGeo, particlesMat);
  scene.add(particleSystem);

  // 5. Dynamic Dual Lights
  const lightCyan = new THREE.PointLight(COLOR_CYAN, 3.5, 60);
  lightCyan.position.set(15, 12, 18);
  scene.add(lightCyan);

  const lightEmerald = new THREE.PointLight(COLOR_EMERALD, 4.0, 60);
  lightEmerald.position.set(-18, -12, 14);
  scene.add(lightEmerald);

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
  scene.add(ambientLight);

  // Mouse interactivity with smooth lerping
  let targetRotationX = 0;
  let targetRotationY = 0;
  let currentRotationX = 0;
  let currentRotationY = 0;
  let mouseActive = false;

  function onPointerMove(e) {
    const rect = container.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
    targetRotationY = x * 0.95;
    targetRotationX = -y * 0.75;
    mouseActive = true;
  }

  window.addEventListener("pointermove", onPointerMove, { passive: true });

  // Click burst/pulse
  container.addEventListener("click", () => {
    coreMesh.scale.set(1.15, 1.15, 1.15);
    innerMesh.scale.set(1.22, 1.22, 1.22);
  });

  // Handle Resize
  function onWindowResize() {
    if (!container) return;
    const w = container.clientWidth;
    const h = container.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }
  window.addEventListener("resize", onWindowResize);

  // Visibility optimization (pause when scrolled away)
  let isVisible = true;
  const observer = new IntersectionObserver(([entry]) => {
    isVisible = entry.isIntersecting;
  }, { threshold: 0.05 });
  observer.observe(container);

  // Render Loop
  let clock = new THREE.Clock();

  function animate() {
    requestAnimationFrame(animate);
    if (!isVisible) return;

    const delta = clock.getDelta();
    const time = clock.getElapsedTime();

    if (!reduceMotion) {
      // Auto-rotation
      mainGroup.rotation.y += 0.0035;
      mainGroup.rotation.x += 0.0018;

      ring1.rotation.z += 0.006;
      ring2.rotation.z -= 0.005;

      particleSystem.rotation.y -= 0.0008;

      // Smooth mouse follow
      currentRotationX += (targetRotationX - currentRotationX) * 0.05;
      currentRotationY += (targetRotationY - currentRotationY) * 0.05;

      mainGroup.rotation.x += (currentRotationX - mainGroup.rotation.x) * 0.08;
      mainGroup.rotation.y += (currentRotationY - mainGroup.rotation.y) * 0.08;

      // Breathing / undulating pulse
      const breathe = 1 + Math.sin(time * 1.8) * 0.035;
      coreMesh.scale.lerp(new THREE.Vector3(breathe, breathe, breathe), 0.08);
      innerMesh.scale.lerp(new THREE.Vector3(breathe * 0.95, breathe * 0.95, breathe * 0.95), 0.08);

      // Light orbit
      lightCyan.position.x = Math.sin(time * 0.7) * 20;
      lightCyan.position.z = Math.cos(time * 0.7) * 20;
      lightEmerald.position.x = -Math.sin(time * 0.5) * 22;
      lightEmerald.position.z = -Math.cos(time * 0.5) * 22;
    }

    renderer.render(scene, camera);
  }

  animate();
})();
