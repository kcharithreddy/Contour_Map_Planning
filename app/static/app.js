/**
 * AI Pond Planner — Phase 3 Frontend Engine
 * Handles interactive map, area selection, hydrological modeling requests,
 * and real-time visualization of pond locations, catchment polygons, and runoff volume.
 */

// ── Application State ──
const state = {
    datasetBounds: null,
    currentSelectionBounds: null,
    lastAnalysisResult: null,
    isDrawing: false,
    drawStartLatLng: null,
    dragRect: null,
    layers: {
        satellite: null,
        osm: null,
        selectionBox: null,
        catchmentPolygon: null,
        pondMarker: null
    }
};

let map = null;

// ── DOM References ──
const dom = {
    btnDrawArea: document.getElementById('btn-draw-area'),
    btnFullArea: document.getElementById('btn-full-area'),
    btnUploadModal: document.getElementById('btn-upload-modal'),
    btnClear: document.getElementById('btn-clear'),
    btnExportGeoJSON: document.getElementById('btn-export-geojson'),
    btnLayerSat: document.getElementById('btn-layer-sat'),
    btnLayerOsm: document.getElementById('btn-layer-osm'),
    loadingOverlay: document.getElementById('loading-overlay'),
    mapToast: document.getElementById('map-toast'),
    toastText: document.getElementById('toast-text'),
    toastCancel: document.getElementById('toast-cancel'),
    statusDot: document.getElementById('status-dot'),
    statusLabel: document.getElementById('status-label'),
    perfTime: document.getElementById('perf-time'),
    inputRunoffC: document.getElementById('input-runoff-c'),
    valRunoffC: document.getElementById('val-runoff-c'),
    inputResM: document.getElementById('input-res-m'),
    valResM: document.getElementById('val-res-m'),
    // KPI Cards
    volumeM3: document.getElementById('kpi-volume-m3'),
    volumeLiters: document.getElementById('kpi-volume-liters'),
    catchmentArea: document.getElementById('kpi-catchment-area'),
    catchmentHa: document.getElementById('kpi-catchment-ha'),
    pondLat: document.getElementById('kpi-pond-lat'),
    pondLon: document.getElementById('kpi-pond-lon'),
    pondElev: document.getElementById('kpi-pond-elev'),
    pondCells: document.getElementById('kpi-pond-cells'),
    pondDepth: document.getElementById('kpi-pond-depth'),
    pondSurface: document.getElementById('kpi-pond-surface'),
    pondCapacity: document.getElementById('kpi-pond-capacity'),
    meanSlope: document.getElementById('kpi-mean-slope'),
    maxSlope: document.getElementById('kpi-max-slope'),
    relief: document.getElementById('kpi-relief'),
    rainfall: document.getElementById('kpi-rainfall'),
    // Modal
    uploadModal: document.getElementById('upload-modal'),
    btnCloseModal: document.getElementById('btn-close-modal'),
    dropZone: document.getElementById('drop-zone'),
    fileInput: document.getElementById('file-input'),
    btnBrowse: document.getElementById('btn-browse'),
    fileInfo: document.getElementById('selected-file-info'),
    filenameLabel: document.getElementById('selected-filename'),
    btnSubmitUpload: document.getElementById('btn-submit-upload')
};

// ── Initialize Map & Tile Layers ──
function initMap() {
    // Esri World Imagery (Satellite)
    state.layers.satellite = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        {
            maxZoom: 19,
            attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
        }
    );

    // CartoDB Voyager (Street / Topo)
    state.layers.osm = L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
        {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        }
    );

    // Default center near IIT Bhilai / Chhattisgarh sample contour coordinates
    const defaultCenter = [21.2444, 81.2910];
    map = L.map('map', {
        center: defaultCenter,
        zoom: 15,
        layers: [state.layers.satellite]
    });

    // Basemap toggle buttons
    dom.btnLayerSat.addEventListener('click', () => {
        if (!map.hasLayer(state.layers.satellite)) {
            map.removeLayer(state.layers.osm);
            map.addLayer(state.layers.satellite);
            dom.btnLayerSat.classList.add('active');
            dom.btnLayerOsm.classList.remove('active');
        }
    });

    dom.btnLayerOsm.addEventListener('click', () => {
        if (!map.hasLayer(state.layers.osm)) {
            map.removeLayer(state.layers.satellite);
            map.addLayer(state.layers.osm);
            dom.btnLayerOsm.classList.add('active');
            dom.btnLayerSat.classList.remove('active');
        }
    });

    setupMapSelectionDrawing();
    fetchDatasetBounds();
}

// ── Fetch Server Dataset Bounds & Center ──
async function fetchDatasetBounds() {
    try {
        const res = await fetch('/api/dataset-bounds');
        if (!res.ok) return;
        const data = await res.json();
        state.datasetBounds = data;

        // Fit map view to preloaded dataset extent
        const southWest = L.latLng(data.min_lat, data.min_lon);
        const northEast = L.latLng(data.max_lat, data.max_lon);
        const bounds = L.latLngBounds(southWest, northEast);
        map.fitBounds(bounds, { padding: [50, 50] });

        // Add subtle boundary outline of available village dataset
        L.rectangle(bounds, {
            color: '#38bdf8',
            weight: 1.5,
            dashArray: '4, 6',
            fill: false,
            opacity: 0.5
        }).addTo(map);

        setStatus('idle', `Village dataset loaded (${data.total_contours} contours)`);
    } catch (e) {
        console.warn('Could not load preloaded bounds:', e);
    }
}

// ── Interactive Land Selection Tool ──
function setupMapSelectionDrawing() {
    dom.btnDrawArea.addEventListener('click', () => {
        startDrawingMode();
    });

    dom.toastCancel.addEventListener('click', () => {
        stopDrawingMode();
    });

    map.on('mousedown', onMapMouseDown);
    map.on('mousemove', onMapMouseMove);
    map.on('mouseup', onMapMouseUp);
}

function startDrawingMode() {
    state.isDrawing = true;
    map.dragging.disable();
    map.getContainer().style.cursor = 'crosshair';
    dom.mapToast.classList.remove('hidden');
    dom.toastText.textContent = 'Click and drag on the map to define the land boundary';
    setStatus('busy', 'Drawing custom land selection...');
}

function stopDrawingMode() {
    state.isDrawing = false;
    state.drawStartLatLng = null;
    map.dragging.enable();
    map.getContainer().style.cursor = '';
    dom.mapToast.classList.add('hidden');
    if (!state.lastAnalysisResult) {
        setStatus('idle', 'Ready for Land Selection');
    }
}

function onMapMouseDown(e) {
    if (!state.isDrawing) return;
    state.drawStartLatLng = e.latlng;

    if (state.dragRect) {
        map.removeLayer(state.dragRect);
    }

    state.dragRect = L.rectangle([e.latlng, e.latlng], {
        color: '#f59e0b',
        weight: 2,
        dashArray: '5, 5',
        fillColor: '#f59e0b',
        fillOpacity: 0.15
    }).addTo(map);
}

function onMapMouseMove(e) {
    if (!state.isDrawing || !state.drawStartLatLng || !state.dragRect) return;
    const currentLatLng = e.latlng;
    const bounds = L.latLngBounds(state.drawStartLatLng, currentLatLng);
    state.dragRect.setBounds(bounds);
}

function onMapMouseUp(e) {
    if (!state.isDrawing || !state.drawStartLatLng) return;

    const bounds = L.latLngBounds(state.drawStartLatLng, e.latlng);
    const min_lat = bounds.getSouth();
    const max_lat = bounds.getNorth();
    const min_lon = bounds.getWest();
    const max_lon = bounds.getEast();

    // Check if drawn box is meaningful (> 10 meters)
    if (Math.abs(max_lat - min_lat) < 0.0001 || Math.abs(max_lon - min_lon) < 0.0001) {
        if (state.dragRect) map.removeLayer(state.dragRect);
        stopDrawingMode();
        return;
    }

    stopDrawingMode();
    runAreaAnalysis({ min_lat, min_lon, max_lat, max_lon });
}

// ── Run Analysis for Selected Land Area ──
async function runAreaAnalysis(bounds) {
    state.currentSelectionBounds = bounds;
    showLoading(true);
    setStatus('busy', 'Computing flow vectors & watershed catchment...');

    const payload = {
        min_lat: bounds.min_lat,
        min_lon: bounds.min_lon,
        max_lat: bounds.max_lat,
        max_lon: bounds.max_lon,
        resolution_m: parseFloat(dom.inputResM.value),
        min_catchment_area_m2: 500.0,
        runoff_coefficient: parseFloat(dom.inputRunoffC.value)
    };

    try {
        const response = await fetch('/analyzeArea', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Analysis request failed.');
        }

        renderAnalysisResults(data, bounds);
        setStatus('done', `Delineated catchment & estimated water volume in ${data.processing_time_ms}ms`);
    } catch (err) {
        console.error(err);
        alert(`Analysis Error: ${err.message}`);
        setStatus('idle', 'Analysis failed — please try selecting an area overlapping contour lines.');
    } finally {
        showLoading(false);
    }
}

// ── Full Village Area Preset Analysis ──
dom.btnFullArea.addEventListener('click', async () => {
    if (!state.datasetBounds) {
        await fetchDatasetBounds();
    }
    if (state.datasetBounds) {
        runAreaAnalysis({
            min_lat: state.datasetBounds.min_lat,
            min_lon: state.datasetBounds.min_lon,
            max_lat: state.datasetBounds.max_lat,
            max_lon: state.datasetBounds.max_lon
        });
    }
});

// ── Render Results on Map & Dashboard ──
function renderAnalysisResults(data, selectedBounds) {
    state.lastAnalysisResult = data;
    clearOverlays();

    // 1. Draw Selected Area Bounding Box
    if (selectedBounds) {
        const rectBounds = [
            [selectedBounds.min_lat, selectedBounds.min_lon],
            [selectedBounds.max_lat, selectedBounds.max_lon]
        ];
        state.layers.selectionBox = L.rectangle(rectBounds, {
            color: '#38bdf8',
            weight: 2,
            dashArray: '6, 6',
            fillColor: '#38bdf8',
            fillOpacity: 0.08
        }).addTo(map);
    }

    // 2. Overlay Catchment Area GeoJSON Polygon
    if (data.catchment && data.catchment.boundary_geojson) {
        state.layers.catchmentPolygon = L.geoJSON(data.catchment.boundary_geojson, {
            style: {
                color: '#06b6d4',
                weight: 3,
                opacity: 0.9,
                fillColor: '#0891b2',
                fillOpacity: 0.35
            }
        }).addTo(map);

        state.layers.catchmentPolygon.bindTooltip(
            `<strong>Watershed Catchment:</strong> ${(data.catchment.area_hectares).toFixed(2)} ha<br><strong>Expected Runoff:</strong> ${(data.water_volume.expected_water_volume_m3).toLocaleString()} m³`,
            { sticky: true, className: 'catchment-tooltip' }
        );
    }

    // 3. Place Suggested Pond Location Marker
    if (data.pond_site) {
        const pondIcon = L.divIcon({
            className: 'custom-pond-marker',
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });

        state.layers.pondMarker = L.marker([data.pond_site.lat, data.pond_site.lon], { icon: pondIcon }).addTo(map);

        const popupContent = `
            <div style="font-family: var(--font-sans); padding: 4px;">
                <h4 style="color: #38bdf8; margin: 0 0 6px 0; font-size: 1rem; display: flex; align-items: center; gap: 4px;">
                    📍 Recommended Pond Site
                </h4>
                <div style="font-size: 0.82rem; line-height: 1.5; color: #cbd5e1;">
                    <div><strong>Elevation:</strong> ${data.pond_site.elevation_m.toFixed(1)} m</div>
                    <div><strong>Coordinates:</strong> ${data.pond_site.lat.toFixed(6)}°, ${data.pond_site.lon.toFixed(6)}°</div>
                    <div><strong>Catchment Area:</strong> ${(data.catchment.area_hectares).toFixed(2)} ha (${data.catchment.area_m2.toLocaleString()} m²)</div>
                    <div><strong>Expected Water Harvest:</strong> <span style="color:#38bdf8; font-weight:700;">${(data.water_volume.expected_water_volume_m3).toLocaleString()} m³</span></div>
                    <div><strong>Rec. Depth:</strong> ${data.water_volume.pond_sizing.recommended_depth_m} m | <strong>Surface Area:</strong> ${data.water_volume.pond_sizing.surface_area_m2.toLocaleString()} m²</div>
                </div>
            </div>
        `;
        state.layers.pondMarker.bindPopup(popupContent).openPopup();
    }

    // Zoom map smoothly to encompass the catchment and pond site
    if (state.layers.catchmentPolygon) {
        map.fitBounds(state.layers.catchmentPolygon.getBounds(), { padding: [40, 40], maxZoom: 17 });
    }

    // 4. Update Dashboard KPI Cards
    updateDashboardUI(data);
}

// ── Update Dashboard Metrics ──
function updateDashboardUI(data) {
    dom.perfTime.textContent = `${data.processing_time_ms} ms`;

    // Water Volume
    const volM3 = data.water_volume.expected_water_volume_m3;
    const volLiters = data.water_volume.expected_water_volume_liters;
    dom.volumeM3.textContent = volM3.toLocaleString();
    dom.volumeLiters.textContent = volLiters.toLocaleString();

    // Catchment Area
    dom.catchmentArea.textContent = Math.round(data.catchment.area_m2).toLocaleString();
    dom.catchmentHa.textContent = data.catchment.area_hectares.toFixed(2);

    // Pond Location
    dom.pondLat.textContent = `${data.pond_site.lat.toFixed(5)}° N`;
    dom.pondLon.textContent = `${data.pond_site.lon.toFixed(5)}° E`;
    dom.pondElev.textContent = `${data.pond_site.elevation_m.toFixed(1)} m`;
    dom.pondCells.textContent = `${data.pond_site.flow_accumulation_cells} cells`;

    // Pond Sizing
    dom.pondDepth.textContent = `${data.water_volume.pond_sizing.recommended_depth_m} m`;
    dom.pondSurface.textContent = `${Math.round(data.water_volume.pond_sizing.surface_area_m2).toLocaleString()} m²`;
    dom.pondCapacity.textContent = `${Math.round(data.water_volume.pond_sizing.storage_capacity_m3).toLocaleString()} m³`;

    // Terrain
    dom.meanSlope.textContent = `${data.catchment.mean_slope_pct.toFixed(2)}%`;
    dom.maxSlope.textContent = `${data.catchment.max_slope_pct.toFixed(2)}%`;
    dom.relief.textContent = `${data.catchment.relief_m.toFixed(1)} m`;
    dom.rainfall.textContent = `${data.water_volume.annual_rainfall_mm} mm`;

    // Enable Export
    dom.btnExportGeoJSON.disabled = false;
}

// ── Clear All Map Overlays ──
function clearOverlays() {
    if (state.layers.selectionBox) {
        map.removeLayer(state.layers.selectionBox);
        state.layers.selectionBox = null;
    }
    if (state.layers.catchmentPolygon) {
        map.removeLayer(state.layers.catchmentPolygon);
        state.layers.catchmentPolygon = null;
    }
    if (state.layers.pondMarker) {
        map.removeLayer(state.layers.pondMarker);
        state.layers.pondMarker = null;
    }
    if (state.dragRect) {
        map.removeLayer(state.dragRect);
        state.dragRect = null;
    }
}

dom.btnClear.addEventListener('click', () => {
    clearOverlays();
    stopDrawingMode();
    dom.btnExportGeoJSON.disabled = true;
    state.lastAnalysisResult = null;
    state.currentSelectionBounds = null;
    setStatus('idle', 'Ready for Land Selection');

    // Reset KPI displays
    dom.volumeM3.textContent = '—';
    dom.volumeLiters.textContent = '—';
    dom.catchmentArea.textContent = '—';
    dom.catchmentHa.textContent = '—';
    dom.pondLat.textContent = '—';
    dom.pondLon.textContent = '—';
    dom.pondElev.textContent = '—';
    dom.pondCells.textContent = '—';
    dom.pondDepth.textContent = '—';
    dom.pondSurface.textContent = '—';
    dom.pondCapacity.textContent = '—';
    dom.meanSlope.textContent = '—';
    dom.maxSlope.textContent = '—';
    dom.relief.textContent = '—';
    dom.perfTime.textContent = '0 ms';
});

// ── Export GeoJSON FeatureCollection ──
dom.btnExportGeoJSON.addEventListener('click', () => {
    if (!state.lastAnalysisResult || !state.lastAnalysisResult.catchment) return;

    const data = state.lastAnalysisResult;
    const exportObject = {
        type: 'FeatureCollection',
        properties: {
            project: 'AI Pond Planner Phase 3',
            generated_at: new Date().toISOString(),
            expected_water_volume_m3: data.water_volume.expected_water_volume_m3,
            catchment_area_m2: data.catchment.area_m2,
            pond_site_lat: data.pond_site.lat,
            pond_site_lon: data.pond_site.lon,
            outlet_elevation_m: data.pond_site.elevation_m
        },
        features: [
            {
                type: 'Feature',
                properties: {
                    name: 'Catchment Watershed Area',
                    area_m2: data.catchment.area_m2,
                    area_hectares: data.catchment.area_hectares,
                    mean_slope_pct: data.catchment.mean_slope_pct
                },
                geometry: data.catchment.boundary_geojson
            },
            {
                type: 'Feature',
                properties: {
                    name: 'Recommended Pond Outlet Location',
                    elevation_m: data.pond_site.elevation_m,
                    flow_cells: data.pond_site.flow_accumulation_cells
                },
                geometry: {
                    type: 'Point',
                    coordinates: [data.pond_site.lon, data.pond_site.lat]
                }
            }
        ]
    };

    const blob = new Blob([JSON.stringify(exportObject, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pond_catchment_analysis_${Date.now()}.geojson`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
});

// ── Parameter Change Handlers ──
dom.inputRunoffC.addEventListener('input', (e) => {
    dom.valRunoffC.textContent = parseFloat(e.target.value).toFixed(2);
    // If analysis already ran, quickly re-calculate volume live
    if (state.lastAnalysisResult) {
        const c = parseFloat(e.target.value);
        const area = state.lastAnalysisResult.catchment.area_m2;
        const rain_m = state.lastAnalysisResult.water_volume.annual_rainfall_mm / 1000.0;
        const vol = Math.round(area * rain_m * c);
        dom.volumeM3.textContent = vol.toLocaleString();
        dom.volumeLiters.textContent = (vol * 1000).toLocaleString();
    }
});

dom.inputResM.addEventListener('input', (e) => {
    dom.valResM.textContent = `${e.target.value} m`;
});

// ── Upload Modal & Custom KML Processing ──
dom.btnUploadModal.addEventListener('click', () => {
    dom.uploadModal.classList.remove('hidden');
});

dom.btnCloseModal.addEventListener('click', () => {
    dom.uploadModal.classList.add('hidden');
});

dom.btnBrowse.addEventListener('click', (e) => {
    e.stopPropagation();
    dom.fileInput.click();
});

dom.fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelected(e.target.files[0]);
    }
});

dom.dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dom.dropZone.classList.add('dragover');
});

dom.dropZone.addEventListener('dragleave', () => {
    dom.dropZone.classList.remove('dragover');
});

dom.dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dom.dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
        handleFileSelected(e.dataTransfer.files[0]);
    }
});

let selectedFile = null;
function handleFileSelected(file) {
    selectedFile = file;
    dom.filenameLabel.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    dom.fileInfo.classList.remove('hidden');
}

dom.btnSubmitUpload.addEventListener('click', async () => {
    if (!selectedFile) return;

    dom.uploadModal.classList.add('hidden');
    showLoading(true);
    setStatus('busy', `Processing uploaded file ${selectedFile.name}...`);

    const formData = new FormData();
    formData.append('contour_map', selectedFile);
    formData.append('resolution_m', dom.inputResM.value);
    formData.append('runoff_coefficient', dom.inputRunoffC.value);

    try {
        const response = await fetch('/analyzeContour', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to process uploaded file.');
        }

        renderAnalysisResults(data, null);
        setStatus('done', `Uploaded contour analyzed in ${data.processing_time_ms}ms`);
    } catch (err) {
        console.error(err);
        alert(`Upload Analysis Error: ${err.message}`);
        setStatus('idle', 'Upload analysis failed.');
    } finally {
        showLoading(false);
    }
});

// ── UI Helpers ──
function showLoading(show) {
    if (show) {
        dom.loadingOverlay.classList.remove('hidden');
    } else {
        dom.loadingOverlay.classList.add('hidden');
    }
}

function setStatus(type, label) {
    dom.statusDot.className = `dot dot-${type}`;
    dom.statusLabel.textContent = label;
}

// ── Application Startup ──
document.addEventListener('DOMContentLoaded', () => {
    initMap();
});
