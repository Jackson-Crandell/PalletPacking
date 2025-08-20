class PackingViewer3D {
    constructor(containerId, sceneData) {
        this.container = document.getElementById(containerId);
        this.sceneData = sceneData;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.animationId = null;
        
        // Check if Three.js is available
        if (typeof THREE === 'undefined') {
            throw new Error('Three.js library not loaded');
        }
        
        this.init();
    }
    
    init() {
        try {
            // Create scene
            this.scene = new THREE.Scene();
            this.scene.background = new THREE.Color(0xf8f9fa);
            
            // Create camera
            const containerRect = this.container.getBoundingClientRect();
            const aspect = containerRect.width / containerRect.height;
            this.camera = new THREE.PerspectiveCamera(50, aspect, 0.1, 10000);
            
            // Create renderer with error handling
            this.renderer = new THREE.WebGLRenderer({
                antialias: true,
                preserveDrawingBuffer: true
            });
            this.renderer.setSize(containerRect.width, containerRect.height);
            this.renderer.setPixelRatio(window.devicePixelRatio);
            
            // Check WebGL support
            const gl = this.renderer.getContext();
            if (!gl) {
                throw new Error('WebGL not supported');
            }
            
            this.renderer.shadowMap.enabled = true;
            this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            
            this.container.appendChild(this.renderer.domElement);
            
            // Add lights
            this.setupLighting();
            
            // Load scene data
            this.loadSceneData();
            
            // Setup camera position
            this.setupCamera();
            
            // Add controls
            this.setupControls();
            
            // Start animation loop
            this.animate();
            
            // Handle window resize
            window.addEventListener('resize', () => this.onWindowResize());
            
        } catch (error) {
            console.error('Failed to initialize 3D viewer:', error);
            throw error;
        }
    }
    
    setupLighting() {
        // Ambient light
        const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
        this.scene.add(ambientLight);
        
        // Directional light
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(50, 50, 50);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        this.scene.add(directionalLight);
        
        // Additional directional light from another angle
        const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.4);
        directionalLight2.position.set(-50, 30, 30);
        this.scene.add(directionalLight2);
    }
    
    loadSceneData() {
        // Create materials map
        const materials = {};
        this.sceneData.materials.forEach(materialData => {
            materials[materialData.uuid] = this.createMaterial(materialData);
        });
        
        // Create geometries map
        const geometries = {};
        this.sceneData.geometries.forEach(geometryData => {
            geometries[geometryData.uuid] = this.createGeometry(geometryData);
        });
        
        // Create objects
        this.sceneData.objects.forEach(objectData => {
            const object = this.createObject(objectData, geometries, materials);
            if (object) {
                this.scene.add(object);
            }
        });
    }
    
    createMaterial(materialData) {
        switch (materialData.type) {
            case 'MeshPhongMaterial':
                return new THREE.MeshPhongMaterial({
                    color: materialData.color,
                    transparent: materialData.transparent || false,
                    opacity: materialData.opacity || 1.0,
                    side: materialData.side || THREE.FrontSide
                });
            case 'LineBasicMaterial':
                return new THREE.LineBasicMaterial({
                    color: materialData.color,
                    linewidth: materialData.linewidth || 1
                });
            default:
                return new THREE.MeshPhongMaterial({ color: 0x808080 });
        }
    }
    
    createGeometry(geometryData) {
        switch (geometryData.type) {
            case 'BoxGeometry':
                const data = geometryData.data;
                return new THREE.BoxGeometry(
                    data.width, data.height, data.depth,
                    data.widthSegments, data.heightSegments, data.depthSegments
                );
            case 'EdgesGeometry':
                return this.createWireframeGeometry(geometryData.data);
            default:
                return new THREE.BoxGeometry(1, 1, 1);
        }
    }
    
    createWireframeGeometry(data) {
        const geometry = new THREE.BufferGeometry();
        
        // Convert edges to line segments
        const positions = [];
        data.edges.forEach(edge => {
            const v1 = data.vertices[edge[0]];
            const v2 = data.vertices[edge[1]];
            positions.push(v1[0], v1[1], v1[2]);
            positions.push(v2[0], v2[1], v2[2]);
        });
        
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        return geometry;
    }
    
    createObject(objectData, geometries, materials) {
        const geometry = geometries[objectData.geometry];
        const material = materials[objectData.material];
        
        if (!geometry || !material) {
            console.warn('Missing geometry or material for object:', objectData.name);
            return null;
        }
        
        let object;
        switch (objectData.type) {
            case 'Mesh':
                object = new THREE.Mesh(geometry, material);
                object.castShadow = true;
                object.receiveShadow = true;
                break;
            case 'LineSegments':
                object = new THREE.LineSegments(geometry, material);
                break;
            default:
                return null;
        }
        
        object.name = objectData.name;
        
        // Apply transformation matrix
        if (objectData.matrix) {
            const matrix = new THREE.Matrix4();
            matrix.fromArray(objectData.matrix);
            object.applyMatrix4(matrix);
        }
        
        return object;
    }
    
    setupCamera() {
        // Calculate scene bounds
        const box = new THREE.Box3().setFromObject(this.scene);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        
        // Position camera
        const maxDim = Math.max(size.x, size.y, size.z);
        const distance = maxDim * 1.5;
        
        this.camera.position.set(
            center.x + distance * 0.7,
            center.y + distance * 0.5,
            center.z + distance * 0.7
        );

        // Rotate camera to look at center
        
        this.camera.lookAt(center);
    }
    
    setupControls() {
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.1;
        this.controls.enableZoom = true;
        this.controls.enablePan = true;
        this.controls.enableRotate = true;
        
        // Set target to scene center
        const box = new THREE.Box3().setFromObject(this.scene);
        const center = box.getCenter(new THREE.Vector3());
        this.controls.target.copy(center);
        
        this.controls.update();
    }
    
    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());
        
        if (this.controls) {
            this.controls.update();
        }
        
        this.renderer.render(this.scene, this.camera);
    }
    
    onWindowResize() {
        const containerRect = this.container.getBoundingClientRect();
        
        this.camera.aspect = containerRect.width / containerRect.height;
        this.camera.updateProjectionMatrix();
        
        this.renderer.setSize(containerRect.width, containerRect.height);
    }
    
    dispose() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        
        if (this.controls) {
            this.controls.dispose();
        }
        
        if (this.renderer) {
            this.renderer.dispose();
        }
        
        window.removeEventListener('resize', this.onWindowResize.bind(this));
    }
    
    // Public methods for interaction
    resetCamera() {
        this.setupCamera();
        this.controls.update();
    }
    
    toggleWireframe() {
        this.scene.traverse((child) => {
            if (child.isMesh && child.material) {
                child.material.wireframe = !child.material.wireframe;
            }
        });
    }
    
    showOnlyContainer() {
        this.scene.traverse((child) => {
            if (child.name && child.name !== 'Container') {
                child.visible = !child.visible;
            }
        });
    }
}

// Utility function to initialize viewer
function initializePackingViewer(containerId, sceneDataJson) {
    try {
        const sceneData = JSON.parse(sceneDataJson);
        return new PackingViewer3D(containerId, sceneData);
    } catch (error) {
        console.error('Failed to initialize 3D viewer:', error);
        return null;
    }
}