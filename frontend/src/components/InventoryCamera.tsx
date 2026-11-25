import type { IScannerControls } from '@zxing/browser';
import { useEffect, useRef, useState } from 'react';

type MedicineOption = { id: number; name: string; sku: string; unit: string };
type BatchOption = {
    id: number;
    medicine_id: number;
    batch_number: string;
    quantity: number;
    expiry_date: string;
    disposal_status?: string;
};
type CameraMode = 'barcode' | 'opencv';
type Candidate = { x: number; y: number; width: number; height: number; confidence: number };
type ShapeCountResult = {
    count: number;
    image_width: number;
    image_height: number;
    candidates: Candidate[];
    method: string;
};
type BarcodeLookup = {
    barcode: string;
    medicine_id: number;
    medicine_name: string;
    medicine_sku: string;
    medicine_unit: string;
    units_per_package: number;
};
type ReconciliationResult = {
    barcode: string;
    package_count: number;
    medicine_name: string;
    medicine_unit: string;
    batch_number: string;
    units_per_package: number;
    previous_quantity: number;
    new_quantity: number;
    quantity_change: number;
};
type OpenCvReconciliationResult = {
    detected_count: number;
    medicine_name: string;
    medicine_unit: string;
    batch_number: string;
    units_per_package: number;
    previous_quantity: number;
    new_quantity: number;
    quantity_change: number;
};

type InventoryCameraProps = {
    apiBase: string;
    token: string;
    medicines: MedicineOption[];
    batches: BatchOption[];
    onInventoryUpdated: (medicineId: number) => Promise<boolean>;
};

export default function InventoryCamera({ apiBase, token, medicines, batches, onInventoryUpdated }: InventoryCameraProps) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const scannerControlsRef = useRef<IScannerControls | null>(null);
    const barcodeHandledRef = useRef(false);
    const liveCountActiveRef = useRef(false);
    const liveCountTimerRef = useRef<number | null>(null);
    const liveCountRequestRef = useRef<AbortController | null>(null);
    const liveCountGenerationRef = useRef(0);
    const [mode, setMode] = useState<CameraMode>('barcode');
    const [stream, setStream] = useState<MediaStream | null>(null);
    const [barcodeScanning, setBarcodeScanning] = useState(false);
    const [liveCounting, setLiveCounting] = useState(false);
    const [selectedMedicine, setSelectedMedicine] = useState('');
    const [selectedBatchId, setSelectedBatchId] = useState('');
    const [unitsPerPackage, setUnitsPerPackage] = useState('1');
    const [barcodeLookup, setBarcodeLookup] = useState<BarcodeLookup | null>(null);
    const [unknownBarcode, setUnknownBarcode] = useState('');
    const [activeBarcode, setActiveBarcode] = useState('');
    const [scannedPackages, setScannedPackages] = useState(0);
    const [reconciliation, setReconciliation] = useState<ReconciliationResult | null>(null);
    const [capturedImage, setCapturedImage] = useState<string | null>(null);
    const [shapeResult, setShapeResult] = useState<ShapeCountResult | null>(null);
    const [openCvReconciliation, setOpenCvReconciliation] = useState<OpenCvReconciliationResult | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    useEffect(() => {
        if (!selectedMedicine && medicines.length) {
            setSelectedMedicine(String(medicines[0].id));
        }
    }, [medicines, selectedMedicine]);

    const availableBatches = batches.filter((batch) =>
        batch.medicine_id === Number(selectedMedicine)
        && batch.disposal_status !== 'disposed'
        && batch.disposal_status !== 'collection_requested',
    );

    useEffect(() => {
        if (!availableBatches.some((batch) => String(batch.id) === selectedBatchId)) {
            setSelectedBatchId(String(availableBatches[0]?.id ?? ''));
        }
    }, [availableBatches, selectedBatchId]);

    useEffect(() => {
        if (videoRef.current && stream) {
            videoRef.current.srcObject = stream;
        }
    }, [stream]);

    useEffect(() => () => {
        liveCountActiveRef.current = false;
        liveCountGenerationRef.current += 1;
        if (liveCountTimerRef.current !== null) {
            window.clearTimeout(liveCountTimerRef.current);
        }
        liveCountRequestRef.current?.abort();
        scannerControlsRef.current?.stop();
        stream?.getTracks().forEach((track) => track.stop());
    }, [stream]);

    const medicine = medicines.find((item) => String(item.id) === selectedMedicine);
    const batch = availableBatches.find((item) => String(item.id) === selectedBatchId);
    const unitsForActiveBarcode = barcodeLookup?.barcode === activeBarcode
        ? barcodeLookup.units_per_package
        : Number(unitsPerPackage);
    const proposedQuantity = scannedPackages * unitsForActiveBarcode;
    const canReconcile = Number.isSafeInteger(unitsForActiveBarcode)
        && unitsForActiveBarcode > 0
        && Number.isSafeInteger(proposedQuantity)
        && proposedQuantity <= 1_000_000;
    const unitsPerDetectedPackage = Number(unitsPerPackage);
    const proposedOpenCvQuantity = (shapeResult?.count ?? 0) * unitsPerDetectedPackage;
    const canReconcileOpenCv = Boolean(shapeResult?.count)
        && Number.isSafeInteger(unitsPerDetectedPackage)
        && unitsPerDetectedPackage > 0
        && Number.isSafeInteger(proposedOpenCvQuantity)
        && proposedOpenCvQuantity <= 1_000_000;

    function clearCount() {
        setBarcodeLookup(null);
        setUnknownBarcode('');
        setActiveBarcode('');
        setScannedPackages(0);
        setReconciliation(null);
        setCapturedImage(null);
        setShapeResult(null);
        setOpenCvReconciliation(null);
        setError('');
        setSuccess('');
    }

    function stopLiveCount() {
        liveCountActiveRef.current = false;
        liveCountGenerationRef.current += 1;
        if (liveCountTimerRef.current !== null) {
            window.clearTimeout(liveCountTimerRef.current);
            liveCountTimerRef.current = null;
        }
        liveCountRequestRef.current?.abort();
        liveCountRequestRef.current = null;
        setLiveCounting(false);
    }

    function stopCamera() {
        stopLiveCount();
        scannerControlsRef.current?.stop();
        scannerControlsRef.current = null;
        stream?.getTracks().forEach((track) => track.stop());
        setStream(null);
        setBarcodeScanning(false);
    }

    function changeMode(nextMode: CameraMode) {
        stopCamera();
        clearCount();
        setMode(nextMode);
    }

    async function lookupBarcode(barcode: string) {
        try {
            const response = await fetch(`${apiBase.replace(/\/$/, '')}/vision/barcodes/lookup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                body: JSON.stringify({ barcode }),
            });
            if (response.status === 404) {
                setUnknownBarcode(barcode);
                setBarcodeLookup(null);
                setError('This barcode is not mapped in your inventory yet. Verify the package label before mapping it.');
                return;
            }
            if (!response.ok) {
                throw new Error(await response.text() || `Barcode lookup failed (${response.status})`);
            }
            const lookup = await response.json() as BarcodeLookup;
            if (lookup.medicine_id !== Number(selectedMedicine)) {
                setError(`Scanned code belongs to ${lookup.medicine_name}, not the selected medicine. No package was added.`);
                return;
            }
            if (activeBarcode && activeBarcode !== lookup.barcode) {
                setError('This code differs from the packages already counted. Reset the count before scanning a different pack size.');
                return;
            }
            setBarcodeLookup(lookup);
            setUnknownBarcode('');
            setActiveBarcode(lookup.barcode);
            setScannedPackages((count) => count + 1);
            setError('');
            setSuccess('');
        } catch (lookupError) {
            setError(lookupError instanceof Error ? lookupError.message : 'Barcode lookup failed.');
        }
    }

    async function startBarcodeScan() {
        if (!videoRef.current || !navigator.mediaDevices?.getUserMedia) {
            setError('Barcode camera access requires a secure browser context such as localhost or HTTPS.');
            return;
        }
        barcodeHandledRef.current = false;
        setError('');
        setSuccess('');
        setBarcodeScanning(true);
        try {
            const { BrowserMultiFormatReader } = await import('@zxing/browser');
            const reader = new BrowserMultiFormatReader();
            const controls = await reader.decodeFromVideoDevice(
                undefined,
                videoRef.current,
                (result, scanError, scanControls) => {
                    scannerControlsRef.current = scanControls;
                    if (result && !barcodeHandledRef.current) {
                        barcodeHandledRef.current = true;
                        scanControls.stop();
                        scannerControlsRef.current = null;
                        setBarcodeScanning(false);
                        void lookupBarcode(result.getText());
                    } else if (scanError && !['NotFoundException', 'ChecksumException', 'FormatException'].includes(scanError.name)) {
                        setError(scanError.message || 'Barcode scanning failed.');
                    }
                },
            );
            scannerControlsRef.current = controls;
        } catch (cameraError) {
            setBarcodeScanning(false);
            setError(cameraError instanceof Error ? cameraError.message : 'Could not start the barcode camera.');
        }
    }

    async function registerUnknownBarcode() {
        if (!medicine || !unknownBarcode || !Number.isSafeInteger(Number(unitsPerPackage)) || Number(unitsPerPackage) < 1) {
            setError('Choose a medicine and enter a valid number of inventory units per package.');
            return;
        }
        if (activeBarcode && activeBarcode !== unknownBarcode) {
            setError('This code differs from packages already counted. Reset the count before mapping another package size.');
            return;
        }
        const units = Number(unitsPerPackage);
        if (!window.confirm(`Verify that barcode ${unknownBarcode} is on the ${medicine.name} package, then map it as ${units} ${medicine.unit}(s) per package?`)) {
            return;
        }

        setBusy(true);
        setError('');
        try {
            const response = await fetch(`${apiBase.replace(/\/$/, '')}/vision/barcodes`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    barcode: unknownBarcode,
                    medicine_id: medicine.id,
                    units_per_package: units,
                }),
            });
            if (!response.ok) {
                const message = await response.text();
                let detail = message;
                try {
                    detail = (JSON.parse(message) as { detail?: string }).detail ?? message;
                } catch {
                    detail = message;
                }
                throw new Error(detail || `Barcode mapping failed (${response.status})`);
            }
            const mapped = await response.json() as BarcodeLookup;
            setBarcodeLookup(mapped);
            setActiveBarcode(mapped.barcode);
            setUnknownBarcode('');
            setScannedPackages((count) => count + 1);
            setError('');
            setSuccess(`Code mapped to ${medicine.name}; the verified first package was counted.`);
            await onInventoryUpdated(medicine.id);
        } catch (mappingError) {
            setError(mappingError instanceof Error ? mappingError.message : 'Could not map barcode.');
        } finally {
            setBusy(false);
        }
    }

    async function confirmBarcodeCount() {
        if (!medicine || !batch || !barcodeLookup || !activeBarcode || !canReconcile || scannedPackages < 1) {
            setError('Scan at least one package with the selected medicine barcode before reconciling.');
            return;
        }
        if (!window.confirm(`Set ${medicine.name}, batch ${batch.batch_number}, to ${proposedQuantity} ${medicine.unit}(s)? Current quantity: ${batch.quantity}.`)) {
            return;
        }

        setBusy(true);
        setError('');
        setSuccess('');
        try {
            const response = await fetch(`${apiBase.replace(/\/$/, '')}/vision/barcode-reconcile`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    barcode: activeBarcode,
                    medicine_id: medicine.id,
                    batch_id: batch.id,
                    expected_quantity: batch.quantity,
                    package_count: scannedPackages,
                }),
            });
            if (!response.ok) {
                const message = await response.text();
                let detail = message;
                try {
                    detail = (JSON.parse(message) as { detail?: string }).detail ?? message;
                } catch {
                    detail = message;
                }
                throw new Error(detail || `Inventory reconciliation failed (${response.status})`);
            }
            const reconciled = await response.json() as ReconciliationResult;
            setReconciliation(reconciled);
            setSuccess(
                `Batch ${reconciled.batch_number} saved at ${reconciled.new_quantity} ${reconciled.medicine_unit}(s).`,
            );
            const refreshed = await onInventoryUpdated(medicine.id);
            if (!refreshed) {
                setError('Count saved, but inventory views could not refresh. Refresh the workspace before another count.');
            }
        } catch (reconcileError) {
            setError(reconcileError instanceof Error ? reconcileError.message : 'Inventory reconciliation failed.');
        } finally {
            setBusy(false);
        }
    }

    async function startOpenCvCamera() {
        clearCount();
        if (!navigator.mediaDevices?.getUserMedia) {
            setError('Camera access requires a secure browser context such as localhost or HTTPS.');
            return;
        }
        try {
            const cameraStream = await navigator.mediaDevices.getUserMedia({
                audio: false,
                video: { facingMode: 'environment' },
            });
            setStream(cameraStream);
        } catch (cameraError) {
            setError(cameraError instanceof Error ? cameraError.message : 'Camera access was denied or unavailable.');
        }
    }

    function captureOpenCvFrame() {
        const video = videoRef.current;
        if (!video || !video.videoWidth || !video.videoHeight) {
            setError('Wait for the camera preview before capturing an image.');
            return null;
        }
        const scale = Math.min(1, 1280 / video.videoWidth);
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);
        const context = canvas.getContext('2d');
        if (!context) {
            setError('This browser could not prepare the camera image.');
            return null;
        }

        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL('image/jpeg', 0.82);
    }

    async function requestOpenCvCount(imageUrl: string, signal?: AbortSignal) {
        const response = await fetch(`${apiBase.replace(/\/$/, '')}/vision/count`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ image_base64: imageUrl.split(',')[1] }),
            signal,
        });
        if (!response.ok) {
            throw new Error(await response.text() || `Shape count failed (${response.status})`);
        }
        return await response.json() as ShapeCountResult;
    }

    async function countOpenCvShapes() {
        const imageUrl = captureOpenCvFrame();
        if (!imageUrl) {
            return;
        }
        setCapturedImage(imageUrl);
        setShapeResult(null);
        setOpenCvReconciliation(null);
        setSuccess('');
        setBusy(true);
        setError('');
        try {
            setShapeResult(await requestOpenCvCount(imageUrl));
        } catch (countError) {
            setError(countError instanceof Error ? countError.message : 'Shape count failed.');
        } finally {
            setBusy(false);
        }
    }

    async function sampleOpenCvVideo(generation: number) {
        if (!liveCountActiveRef.current || generation !== liveCountGenerationRef.current) {
            return;
        }
        const imageUrl = captureOpenCvFrame();
        if (!imageUrl) {
            stopLiveCount();
            return;
        }

        const controller = new AbortController();
        liveCountRequestRef.current = controller;
        try {
            const result = await requestOpenCvCount(imageUrl, controller.signal);
            if (liveCountActiveRef.current && generation === liveCountGenerationRef.current) {
                setCapturedImage(imageUrl);
                setShapeResult(result);
                setOpenCvReconciliation(null);
                setError('');
            }
        } catch (countError) {
            if (!controller.signal.aborted && generation === liveCountGenerationRef.current) {
                setError(countError instanceof Error ? countError.message : 'Live video count failed.');
                stopLiveCount();
            }
        } finally {
            if (liveCountRequestRef.current === controller) {
                liveCountRequestRef.current = null;
            }
        }

        if (liveCountActiveRef.current && generation === liveCountGenerationRef.current) {
            liveCountTimerRef.current = window.setTimeout(() => {
                void sampleOpenCvVideo(generation);
            }, 900);
        }
    }

    function startLiveCount() {
        if (!stream || !medicine || !batch) {
            setError('Start the camera and choose an active medicine batch before live counting.');
            return;
        }
        stopLiveCount();
        setCapturedImage(null);
        setShapeResult(null);
        setOpenCvReconciliation(null);
        setError('');
        setSuccess('');
        liveCountActiveRef.current = true;
        const generation = ++liveCountGenerationRef.current;
        setLiveCounting(true);
        void sampleOpenCvVideo(generation);
    }

    async function confirmOpenCvCount() {
        if (!medicine || !batch || !shapeResult || !capturedImage || !canReconcileOpenCv) {
            setError('Capture an image with detected package shapes and choose an active medicine batch before updating inventory.');
            return;
        }
        if (!window.confirm(
            `The trained detector estimates ${shapeResult.count} visible medicine package(s). Set ${medicine.name}, batch ${batch.batch_number}, to ${proposedOpenCvQuantity} ${medicine.unit}(s)? Current quantity: ${batch.quantity}.`,
        )) {
            return;
        }

        setBusy(true);
        setError('');
        setSuccess('');
        try {
            const response = await fetch(`${apiBase.replace(/\/$/, '')}/vision/opencv-reconcile`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    image_base64: capturedImage.split(',')[1],
                    medicine_id: medicine.id,
                    batch_id: batch.id,
                    expected_quantity: batch.quantity,
                    units_per_package: unitsPerDetectedPackage,
                }),
            });
            if (!response.ok) {
                const message = await response.text();
                let detail = message;
                try {
                    detail = (JSON.parse(message) as { detail?: string }).detail ?? message;
                } catch {
                    detail = message;
                }
                throw new Error(detail || `OpenCV inventory update failed (${response.status})`);
            }
            const result = await response.json() as OpenCvReconciliationResult;
            setOpenCvReconciliation(result);
            setSuccess(
                `OpenCV estimate confirmed. Batch ${result.batch_number} saved at ${result.new_quantity} ${result.medicine_unit}(s).`,
            );
            const refreshed = await onInventoryUpdated(medicine.id);
            if (!refreshed) {
                setError('Count saved, but inventory views could not refresh. Refresh the workspace before another count.');
            }
        } catch (reconcileError) {
            setError(reconcileError instanceof Error ? reconcileError.message : 'OpenCV inventory update failed.');
        } finally {
            setBusy(false);
        }
    }

    return (
        <section className="camera-workspace">
            <div className="panel camera-intro">
                <div className="section-title">{mode === 'barcode' ? 'Medicine identification' : 'Video inventory count'}</div>
                <h3>{mode === 'barcode' ? 'Scan known package barcodes' : 'Count visible medicine packages'}</h3>
                <p>{mode === 'barcode'
                    ? 'Barcode matching identifies a product only after its code is verified and mapped to your catalogue medicine.'
                    : 'Live mode checks the current video frame about once per second. It counts only the packages visible now, not a running total across frames.'}</p>
                <div className="camera-demo-notice">
                    {mode === 'barcode'
                        ? 'GS1 DataKart is not connected: its published integration requires solution-provider registration. This workflow uses barcode mappings saved in this pharmacy, not an external medicine database or trained image model. A barcode identifies a product, not a particular batch or individual physical pack.'
                        : 'The trained detector outlines visible medicine packages but does not identify medicine names. Keep only the selected medicine in view, separate packages where possible, keep every pack fully in frame, and review the boxes before confirming an inventory change.'}
                </div>
                <div className="camera-controls">
                    <label>
                        Medicine in inventory
                        <select value={selectedMedicine} onChange={(event) => { setSelectedMedicine(event.target.value); setSelectedBatchId(''); clearCount(); }} disabled={!medicines.length || busy || barcodeScanning || liveCounting}>
                            {medicines.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.sku}</option>)}
                        </select>
                    </label>
                    <label>
                        Batch / lot to reconcile
                        <select value={selectedBatchId} onChange={(event) => { setSelectedBatchId(event.target.value); clearCount(); }} disabled={!availableBatches.length || busy || barcodeScanning || liveCounting}>
                            {availableBatches.map((item) => <option key={item.id} value={item.id}>{item.batch_number} · current {item.quantity} {medicine?.unit ?? 'units'} · expires {item.expiry_date}</option>)}
                        </select>
                    </label>
                    {mode === 'barcode' && !barcodeLookup && <label>
                        Inventory units per package
                        <input type="number" min="1" max="1000000" step="1" value={unitsPerPackage} onChange={(event) => setUnitsPerPackage(event.target.value)} disabled={busy || barcodeScanning || liveCounting} />
                        <small>Enter 1 if inventory is counted in strips/bottles, or the tablet/capsule count per package.</small>
                    </label>}
                </div>
                {!medicines.length && <p className="camera-error">Add a medicine to the catalogue before scanning.</p>}
                {medicines.length > 0 && !availableBatches.length && <p className="camera-error">This medicine has no active batch available to reconcile.</p>}
                <div className="camera-mode-tabs" role="group" aria-label="Camera mode">
                    <button className={mode === 'barcode' ? 'primary inline' : 'secondary inline'} onClick={() => changeMode('barcode')} disabled={busy || liveCounting}>Barcode stock count</button>
                    <button className={mode === 'opencv' ? 'primary inline' : 'secondary inline'} onClick={() => changeMode('opencv')} disabled={busy || liveCounting}>OpenCV visual count</button>
                </div>
            </div>

            <div className="panel camera-panel">
                <div className="camera-preview">
                    {mode === 'opencv' && stream ? (
                        <div className="camera-captured">
                            <video
                                ref={videoRef}
                                autoPlay
                                muted
                                playsInline
                                aria-label="Medicine package camera preview"
                                style={{ display: capturedImage && !liveCounting ? 'none' : 'block' }}
                            />
                            {capturedImage && !liveCounting && <img src={capturedImage} alt="Captured packages for OpenCV visual count" />}
                            {shapeResult && <svg viewBox={`0 0 ${shapeResult.image_width} ${shapeResult.image_height}`} role="img" aria-label={`${shapeResult.count} possible medicine packages`}>
                                {shapeResult.candidates.map((box, index) => <g key={index}>
                                    <rect x={box.x} y={box.y} width={box.width} height={box.height} />
                                    <text x={box.x} y={Math.max(box.y - 6, 14)}>{Math.round(box.confidence * 100)}%</text>
                                </g>)}
                            </svg>}
                        </div>
                    ) : mode === 'opencv' && capturedImage ? (
                        <div className="camera-captured">
                            <img src={capturedImage} alt="Captured packages for OpenCV visual count" />
                            {shapeResult && <svg viewBox={`0 0 ${shapeResult.image_width} ${shapeResult.image_height}`} role="img" aria-label={`${shapeResult.count} possible medicine packages`}>
                                {shapeResult.candidates.map((box, index) => <g key={index}>
                                    <rect x={box.x} y={box.y} width={box.width} height={box.height} />
                                    <text x={box.x} y={Math.max(box.y - 6, 14)}>{Math.round(box.confidence * 100)}%</text>
                                </g>)}
                            </svg>}
                        </div>
                    ) : mode === 'barcode' ? (
                        <>
                            <video ref={videoRef} autoPlay muted playsInline aria-label="Barcode scanning camera preview" />
                            {!barcodeScanning && <div className="camera-scan-overlay">Start a scan to read one package barcode</div>}
                        </>
                    ) : (
                        <div className="camera-placeholder">Camera preview will appear here</div>
                    )}
                </div>

                {mode === 'barcode' ? (
                    <>
                        <div className="action-row camera-actions">
                            <button className="primary inline" onClick={() => void startBarcodeScan()} disabled={barcodeScanning || busy || !medicine || !batch}>
                                {barcodeScanning ? 'Scanning barcode…' : scannedPackages ? 'Scan next package' : 'Scan package barcode'}
                            </button>
                            {barcodeScanning && <button className="secondary inline" onClick={stopCamera}>Stop scan</button>}
                            {scannedPackages > 0 && !reconciliation && <button className="secondary inline" onClick={() => {
                                if (scannedPackages <= 1) {
                                    setScannedPackages(0);
                                    setBarcodeLookup(null);
                                    setActiveBarcode('');
                                } else {
                                    setScannedPackages(scannedPackages - 1);
                                }
                                setError('');
                            }} disabled={busy || barcodeScanning}>Remove last scan</button>}
                            {scannedPackages > 0 && <button className="secondary inline" onClick={clearCount} disabled={busy || barcodeScanning}>Reset count</button>}
                        </div>
                        {unknownBarcode && (
                            <div className="camera-result">
                                <strong>Unmapped barcode: {unknownBarcode}</strong>
                                <span>Only register it after checking that the physical package label matches {medicine?.name ?? 'the selected medicine'}.</span>
                                <button className="primary inline" onClick={() => void registerUnknownBarcode()} disabled={busy || !medicine}>
                                    {busy ? 'Saving mapping…' : `Verify & map to ${medicine?.name ?? 'medicine'}`}
                                </button>
                            </div>
                        )}
                        {barcodeLookup && scannedPackages > 0 && batch && medicine && (
                            <div className="camera-result" aria-live="polite">
                                <strong>{scannedPackages} package barcode scan{scannedPackages === 1 ? '' : 's'} recorded</strong>
                                <span>Verified code for {barcodeLookup.medicine_name} · {barcodeLookup.barcode}</span>
                                <span>{batch.batch_number}: {batch.quantity} current → {proposedQuantity} proposed {medicine.unit}(s), using {barcodeLookup.units_per_package} unit(s) per package.</span>
                                {reconciliation ? (
                                    <span>Confirmed: {reconciliation.quantity_change > 0 ? `increased by ${reconciliation.quantity_change}` : reconciliation.quantity_change < 0 ? `decreased by ${Math.abs(reconciliation.quantity_change)}` : 'no stock change'}.</span>
                                ) : (
                                    <button className="primary inline" onClick={() => void confirmBarcodeCount()} disabled={busy || !canReconcile}>
                                        {busy ? 'Saving count…' : 'Confirm count & update inventory'}
                                    </button>
                                )}
                            </div>
                        )}
                    </>
                ) : (
                    <>
                        <div className="camera-controls camera-demo-controls">
                            <label>
                                Inventory units per detected package
                                <input type="number" min="1" max="1000000" step="1" value={unitsPerPackage} onChange={(event) => setUnitsPerPackage(event.target.value)} disabled={busy || barcodeScanning || liveCounting || Boolean(openCvReconciliation)} />
                                <small>Use 1 if inventory is counted in packs, or enter the tablet/capsule count per pack when inventory is counted as individual units.</small>
                            </label>
                        </div>
                        <div className="action-row camera-actions">
                            {!stream
                                ? <button className="primary inline" onClick={() => void startOpenCvCamera()} disabled={busy || !medicine || !batch}>Start camera</button>
                                : <>
                                    {!liveCounting && <button className="primary inline" onClick={() => void countOpenCvShapes()} disabled={busy || !medicine || !batch}>{busy ? 'Counting…' : 'Capture & count packages'}</button>}
                                    {!liveCounting && <button className="secondary inline" onClick={startLiveCount} disabled={busy || !medicine || !batch}>Start live count</button>}
                                    {liveCounting && <button className="secondary inline" onClick={stopLiveCount}>Stop live count</button>}
                                    <button className="secondary inline" onClick={stopCamera} disabled={busy}>Stop camera</button>
                                </>}
                        </div>
                        {liveCounting && <p className="camera-success" role="status">Live estimate updates from the current video frame about once per second. It replaces the prior estimate; objects in later frames are not added again. Stop live count to review and apply the last estimate.</p>}
                        {shapeResult && batch && medicine && <div className="camera-result" aria-live="polite">
                            <strong>{shapeResult.count} medicine package{shapeResult.count === 1 ? '' : 's'} detected</strong>
                            <span>The detector counts visible packages only; it does not identify the medicine or batch. Keep only the selected medicine in view, keep packages fully in frame, and check each highlighted box.</span>
                            <span>{batch.batch_number}: {batch.quantity} current → {proposedOpenCvQuantity} proposed {medicine.unit}(s), using {unitsPerDetectedPackage} unit(s) per detected package.</span>
                            {liveCounting ? (
                                <span>Live estimate: {shapeResult.count} visible package shape(s). Stop the video count to freeze this frame before applying it.</span>
                            ) : openCvReconciliation ? (
                                <span>Confirmed: {openCvReconciliation.quantity_change > 0 ? `increased by ${openCvReconciliation.quantity_change}` : openCvReconciliation.quantity_change < 0 ? `decreased by ${Math.abs(openCvReconciliation.quantity_change)}` : 'no stock change'}.</span>
                            ) : shapeResult.count === 0 ? (
                                <span>No packages were detected. Inventory was not changed; adjust the view and capture again.</span>
                            ) : (
                                <button className="primary inline" onClick={() => void confirmOpenCvCount()} disabled={busy || liveCounting || !canReconcileOpenCv}>
                                    {busy ? 'Saving count…' : 'Confirm estimate & update inventory'}
                                </button>
                            )}
                        </div>}
                    </>
                )}
                {error && <p className="camera-error" role="alert">{error}</p>}
                {success && <p className="camera-success" role="status">{success}</p>}
            </div>
        </section>
    );
}
