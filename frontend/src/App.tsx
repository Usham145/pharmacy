import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler } from 'chart.js';
import { Line } from 'react-chartjs-2';

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler);

type Summary = {
    medicines: number;
    batches: number;
    total_units: number;
    low_stock_items: number;
    near_expiry_batches: number;
    monthly_consumption: number;
    forecast_signal: string;
};

type User = {
    id: number;
    username: string;
    full_name: string;
    email?: string | null;
    role: 'admin' | 'pharmacist' | string;
};

type UserFormState = { id?: number; username: string; full_name: string; email: string; role: string; password: string };
type Page = 'welcome' | 'dashboard' | 'medicines' | 'batches' | 'expiry' | 'dispense' | 'sales' | 'finance' | 'import' | 'suppliers' | 'transactions' | 'departments' | 'reports' | 'reference' | 'users' | 'procurement';

const pageNames: Page[] = ['welcome', 'dashboard', 'medicines', 'batches', 'expiry', 'dispense', 'sales', 'finance', 'import', 'suppliers', 'transactions', 'departments', 'reports', 'reference', 'users', 'procurement'];
const translations = {
    en: { workspace: 'My workspace', dashboard: 'Dashboard', medicines: 'Medicines', batches: 'Batches', expiry: 'Expiry & waste', dispense: 'FEFO Dispensing', import: 'Import CSV', suppliers: 'Suppliers', transactions: 'Transactions', reference: 'Reference Data', users: 'Team & Access', reports: 'Reports', signOut: 'Sign out', control: 'ArogyaMitra Control Centre', language: 'Language' },
    hi: { workspace: 'मेरा कार्यक्षेत्र', dashboard: 'डैशबोर्ड', medicines: 'दवाइयाँ', batches: 'बैच', expiry: 'समाप्ति व अपशिष्ट', dispense: 'FEFO वितरण', import: 'CSV आयात', suppliers: 'आपूर्तिकर्ता', transactions: 'लेन-देन', reference: 'संदर्भ डेटा', users: 'टीम और पहुँच', reports: 'रिपोर्ट', signOut: 'लॉग आउट', control: 'आरोग्यमित्र नियंत्रण केंद्र', language: 'भाषा' },
    bn: { workspace: 'আমার কর্মক্ষেত্র', dashboard: 'ড্যাশবোর্ড', medicines: 'ওষুধ', batches: 'ব্যাচ', expiry: 'মেয়াদ ও বর্জ্য', dispense: 'FEFO বিতরণ', import: 'CSV আমদানি', suppliers: 'সরবরাহকারী', transactions: 'লেনদেন', reference: 'রেফারেন্স তথ্য', users: 'দল ও প্রবেশাধিকার', reports: 'রিপোর্ট', signOut: 'লগ আউট', control: 'আরোগ্যমিত্র নিয়ন্ত্রণ কেন্দ্র', language: 'ভাষা' },
} as const;

type Medicine = {
    id: number;
    name: string;
    sku: string;
    category: string;
    unit: string;
    reorder_level: number;
    ideal_stock: number;
    active: boolean;
    description?: string | null;
};

type Supplier = {
    id: number;
    company_name: string;
    contact_person: string;
    phone: string;
    email: string;
    gst_number: string;
    address: string;
    active: boolean;
    waste_vendor?: boolean;
    waste_license_number?: string | null;
};

type Department = {
    id: number;
    name: string;
    floor: string;
    contact_extension: string;
};

type Location = {
    id: number;
    code: string;
    name: string;
    temperature_zone: string;
    notes?: string | null;
};

type PurchaseOrder = {
    id: number;
    po_number: string;
    supplier_name: string;
    order_date: string;
    total_amount: number;
    status: string;
};

type ProcurementRequest = {
    id: number;
    request_number: string;
    supplier_name: string;
    supplier_email: string;
    trigger_summary: string;
    item_lines: { medicine_id: number; medicine_name: string; sku: string; quantity: number; unit_price: number; line_total: number; reason: string }[];
    estimated_total: number;
    status: string;
    admin_notified_at?: string | null;
    sent_at?: string | null;
    invoice_number?: string | null;
};

type Transaction = {
    id: number;
    transaction_date: string;
    medicine_id: number;
    medicine_name?: string | null;
    transaction_type: string;
    quantity: number;
    reference: string;
    department?: string | null;
    note?: string | null;
};

type Category = {
    id: number;
    name: string;
    description?: string | null;
};

type Insight = {
    total_medicines: number;
    total_batches: number;
    total_suppliers: number;
    total_transactions: number;
    total_purchase_orders: number;
    total_departments: number;
    total_locations: number;
};

type Batch = {
    id: number;
    medicine_id: number;
    medicine_name?: string | null;
    batch_number: string;
    supplier: string;
    quantity: number;
    unit_price: number;
    recovery_unit_price: number;
    received_on: string;
    expiry_date: string;
    location: string;
    disposal_status?: string;
    disposal_method?: string | null;
    disposal_reference?: string | null;
    disposed_on?: string | null;
};
type ExpiryBand = 'green' | 'yellow' | 'red' | 'black';
type ExpiryBatch = Batch & { daysLeft: number; expiryBand: ExpiryBand; expiryLabel: string };
type ExpirySupplier = { supplier: string; totalBatches: number; expiredBatches: number; nearExpiryBatches: number; totalQuantity: number; nextExpiry: string | null };
type DepartmentInventory = { id: number; department: string; medicine_id: number; medicine_name: string; batch_number: string; quantity: number; updated_at: string };
type FinancialSummary = { sales_total: number; sales_count: number; purchases_total: number; purchase_count: number };

type Pharmacy = { id: number; name: string; hospital_name?: string | null; licence_number?: string | null; address?: string | null };
type Equipment = { id: number; name: string; asset_number: string; equipment_type: string; waste_category: string; quantity: number; unit: string; expiry_date?: string | null; condition: string; waste_status: string; location: string };
type WastePickup = { id: number; pickup_number: string; vendor_name: string; vendor_contact: string; scheduled_date: string; waste_category: string; item_summary: string; status: string; manifest_number?: string | null; certificate_reference?: string | null; notes?: string | null };

type SmtpStatus = { configured: boolean; host: string; port: number; use_tls: boolean; username_configured: boolean; from_email: string };
type ExpiryCompanyTransfer = { id: number; quote_number: string; invoice_number?: string | null; batch_id: number; medicine_name: string; batch_number: string; company_name: string; company_contact: string; quantity: number; recovery_unit_price: number; total_amount: number; status: string; quoted_on: string; transferred_on?: string | null; transfer_reference?: string | null };

type AlertItem = {
    id: number;
    medicine_id: number;
    medicine_name: string;
    batch_id?: number | null;
    batch_number?: string | null;
    alert_type: 'low_stock' | 'near_expiry';
    severity: 'low' | 'medium' | 'high';
    message: string;
    due_on?: string | null;
    quantity: number;
};

type Forecast = {
    medicine_id: number;
    medicine_name: string;
    recent_daily_avg: number;
    points: { horizon_days: number; predicted_quantity: number }[];
    recommendation: number;
};

type SaleInvoice = {
    invoice_number: string;
    buyer_name: string;
    buyer_phone?: string | null;
    medicine_name: string;
    sku: string;
    batch_number: string;
    quantity: number;
    unit_price: number;
    total_amount: number;
    sold_by: string;
    sold_at: string;
};

type LoginResponse = {
    access_token: string;
    token_type: string;
    user: User;
};

type AuthMeResponse = {
    user: User;
};

type MedicineFormState = {
    id?: number;
    name: string;
    sku: string;
    category: string;
    unit: string;
    reorder_level: string;
    ideal_stock: string;
    active: boolean;
    description: string;
};

type BatchFormState = {
    id?: number;
    medicine_id: string;
    batch_number: string;
    supplier: string;
    quantity: string;
    unit_price: string;
    recovery_unit_price: string;
    received_on: string;
    expiry_date: string;
    location: string;
};

type DashboardData = {
    summary: Summary;
    insights: Insight;
    medicines: Medicine[];
    batches: Batch[];
    alerts: AlertItem[];
    forecast: Forecast | null;
    suppliers: Supplier[];
    departments: Department[];
    locations: Location[];
    purchaseOrders: PurchaseOrder[];
    transactions: Transaction[];
    categories: Category[];
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1';
const TOKEN_KEY = 'pharmacy_auth_token';
const USER_KEY = 'pharmacy_auth_user';
const rolePresets = [
    { username: 'admin', password: 'admin123', label: 'Admin' },
    { username: 'pharmacist', password: 'pharmacist123', label: 'Pharmacist' },
    { username: 'platformadmin', password: 'platform123', label: 'Platform Admin' },
];

const emptyMedicineForm: MedicineFormState = {
    name: '',
    sku: '',
    category: '',
    unit: 'tablet',
    reorder_level: '25',
    ideal_stock: '100',
    active: true,
    description: '',
};

const emptyBatchForm: BatchFormState = {
    medicine_id: '',
    batch_number: '',
    supplier: '',
    quantity: '0',
    unit_price: '50',
    recovery_unit_price: '5',
    received_on: new Date().toISOString().slice(0, 10),
    expiry_date: new Date(Date.now() + 1000 * 60 * 60 * 24 * 90).toISOString().slice(0, 10),
    location: 'Main Store',
};

async function apiRequest<T>(path: string, token: string | null, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(init?.headers ?? {}),
        },
    });

    if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Request failed with status ${response.status}`);
    }

    if (response.status === 204) {
        return undefined as T;
    }

    return response.json() as Promise<T>;
}

async function downloadFile(path: string, token: string | null) {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = path.split('/').pop() ?? 'report';
    anchor.click();
    URL.revokeObjectURL(url);
}

function getExpirySnapshot(expiryDate: string, disposalStatus?: string) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const expiry = new Date(`${expiryDate}T00:00:00`);
    const daysLeft = Math.round((expiry.getTime() - today.getTime()) / 86400000);
    if (disposalStatus === 'disposed') {
        return { daysLeft, expiryBand: 'black' as const, expiryLabel: 'Disposed' };
    }
    if (daysLeft < 0) {
        return { daysLeft, expiryBand: 'black' as const, expiryLabel: 'Expired' };
    }
    if (daysLeft <= 90) {
        return { daysLeft, expiryBand: 'red' as const, expiryLabel: 'Under 3 months' };
    }
    if (daysLeft <= 180) {
        return { daysLeft, expiryBand: 'yellow' as const, expiryLabel: '3-6 months' };
    }
    return { daysLeft, expiryBand: 'green' as const, expiryLabel: 'Healthy' };
}

export default function App() {
    const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
    const [sessionChecked, setSessionChecked] = useState(() => !localStorage.getItem(TOKEN_KEY));
    const [currentUser, setCurrentUser] = useState<User | null>(() => {
        const stored = localStorage.getItem(USER_KEY);
        return stored ? (JSON.parse(stored) as User) : null;
    });
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState('Ready');
    const [authUsername, setAuthUsername] = useState('admin');
    const [authPassword, setAuthPassword] = useState('admin123');
    const [selectedMedicineId, setSelectedMedicineId] = useState<number | null>(null);
    const [inspectedSupplierName, setInspectedSupplierName] = useState<string | null>(null);
    const [medicineSearch, setMedicineSearch] = useState('');
    const [activeTab, setActiveTab] = useState<Page>(() => {
        const page = window.location.pathname.replace(/^\//, '') as Page;
        return pageNames.includes(page) ? page : 'welcome';
    });
    const [language, setLanguage] = useState<'en' | 'hi' | 'bn'>('en');
    const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
    const [medicineForm, setMedicineForm] = useState<MedicineFormState>(emptyMedicineForm);
    const [batchForm, setBatchForm] = useState<BatchFormState>(emptyBatchForm);
    const [editingMedicineId, setEditingMedicineId] = useState<number | null>(null);
    const [editingBatchId, setEditingBatchId] = useState<number | null>(null);
    const [suppliers, setSuppliers] = useState<Supplier[]>([]);
    const [departments, setDepartments] = useState<Department[]>([]);
    const [locations, setLocations] = useState<Location[]>([]);
    const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([]);
    const [sales, setSales] = useState<SaleInvoice[]>([]);
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [departmentInventory, setDepartmentInventory] = useState<DepartmentInventory[]>([]);
    const [categories, setCategories] = useState<Category[]>([]);
    const [insights, setInsights] = useState<Insight | null>(null);
    const [users, setUsers] = useState<User[]>([]);
    const [procurementRequests, setProcurementRequests] = useState<ProcurementRequest[]>([]);
    const [smtpStatus, setSmtpStatus] = useState<SmtpStatus | null>(null);
    const [smtpRecipient, setSmtpRecipient] = useState('');
    const [smtpSubject, setSmtpSubject] = useState('Pharmacy communication test');
    const [smtpBody, setSmtpBody] = useState('This is a test email from the pharmacy communication workspace.');
    const [userForm, setUserForm] = useState<UserFormState>({ username: '', full_name: '', email: '', role: 'pharmacist', password: '' });
    const [importFile, setImportFile] = useState<File | null>(null);
    const [dispenseLookup, setDispenseLookup] = useState('');
    const [dispenseQuantity, setDispenseQuantity] = useState('1');
    const [dispenseDepartment, setDispenseDepartment] = useState('Emergency');
    const [dispenseNote, setDispenseNote] = useState('');
    const [saleLookup, setSaleLookup] = useState('');
    const [saleQuantity, setSaleQuantity] = useState('1');
    const [salePrice, setSalePrice] = useState('0');
    const [saleSearch, setSaleSearch] = useState('');
    const [selectedSaleBatchId, setSelectedSaleBatchId] = useState<number | null>(null);
    const [buyerName, setBuyerName] = useState('');
    const [buyerPhone, setBuyerPhone] = useState('');
    const [latestBill, setLatestBill] = useState<SaleInvoice | null>(null);
    const [financials, setFinancials] = useState<FinancialSummary | null>(null);
    const [pharmacies, setPharmacies] = useState<Pharmacy[]>([]);
    const [equipment, setEquipment] = useState<Equipment[]>([]);
    const [wastePickups, setWastePickups] = useState<WastePickup[]>([]);
    const workspaceRequestRef = useRef(0);
    const [expiryTransfers, setExpiryTransfers] = useState<ExpiryCompanyTransfer[]>([]);
    const [expiryCompanyForm, setExpiryCompanyForm] = useState({ batchId: '', companyName: '', companyContact: '', quantity: '1', recoveryUnitPrice: '' });
    const [equipmentForm, setEquipmentForm] = useState({ name: '', asset_number: '', equipment_type: 'Medical equipment', waste_category: 'General equipment', quantity: '1', unit: 'piece', expiry_date: '', condition: 'usable', location: 'Main Store' });
    const [pickupForm, setPickupForm] = useState({ vendor_name: '', vendor_contact: '', scheduled_date: new Date().toISOString().slice(0, 10), waste_category: 'Expired medicines', item_summary: '', notes: '' });
    const [pharmacyForm, setPharmacyForm] = useState({ name: '', hospital_name: '', licence_number: '', address: '', admin_username: '', admin_full_name: '', admin_email: '', admin_password: '' });
    const t = translations[language];

    function navigate(page: Page) {
        window.history.pushState({ page }, '', `/${page}`);
        setActiveTab(page);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    useEffect(() => {
        const syncPage = () => {
            const page = window.location.pathname.replace(/^\//, '') as Page;
            setActiveTab(pageNames.includes(page) ? page : 'welcome');
        };
        window.addEventListener('popstate', syncPage);
        return () => window.removeEventListener('popstate', syncPage);
    }, []);

    useEffect(() => {
        if (!token) {
            setSessionChecked(true);
            return;
        }
        setSessionChecked(false);
        void restoreSession();
    }, [token]);

    useEffect(() => {
        if (token && sessionChecked && currentUser) {
            if (currentUser?.role === 'platform_admin') void loadPharmacies();
            else void loadWorkspace(null);
        }
    }, [token, sessionChecked, currentUser?.role]);

    useEffect(() => {
        if (!token || !sessionChecked || !currentUser || currentUser.role === 'platform_admin' || !selectedMedicineId) {
            return;
        }
        void refreshForecast(selectedMedicineId);
    }, [token, sessionChecked, currentUser?.role, selectedMedicineId]);

    const selectedMedicine = useMemo(
        () => dashboardData?.medicines.find((medicine) => medicine.id === selectedMedicineId) ?? null,
        [dashboardData, selectedMedicineId],
    );

    const medicineRows = useMemo(() => {
        if (!dashboardData) return [];
        const query = medicineSearch.trim().toLowerCase();
        const rows = dashboardData.medicines.map((medicine) => {
            const batches = dashboardData.batches.filter((batch) => batch.medicine_id === medicine.id);
            const activeBatches = batches.filter((batch) => batch.disposal_status === 'active' && batch.expiry_date >= new Date().toISOString().slice(0, 10));
            const nextExpiry = batches.filter((batch) => batch.disposal_status !== 'disposed').sort((left, right) => left.expiry_date.localeCompare(right.expiry_date))[0]?.expiry_date ?? null;
            return { medicine, stock: activeBatches.reduce((total, batch) => total + batch.quantity, 0), batchCount: batches.length, nextExpiry };
        });
        return rows.filter(({ medicine }) => !query || `${medicine.name} ${medicine.sku} ${medicine.category}`.toLowerCase().includes(query)).sort((left, right) => left.medicine.name.localeCompare(right.medicine.name));
    }, [dashboardData, medicineSearch]);

    const inspectedMedicine = dashboardData?.medicines.find((medicine) => medicine.id === selectedMedicineId) ?? null;
    const inspectedMedicineBatches = inspectedMedicine ? dashboardData?.batches.filter((batch) => batch.medicine_id === inspectedMedicine.id) ?? [] : [];
    const inspectedSupplier = suppliers.find((supplier) => supplier.company_name === inspectedSupplierName) ?? null;
    const inspectedSupplierBatches = inspectedSupplier ? (dashboardData?.batches.filter((batch) => batch.supplier === inspectedSupplier.company_name) ?? []) : [];

    function inspectMedicine(medicineId: number) {
        const medicine = dashboardData?.medicines.find((item) => item.id === medicineId);
        if (!medicine) return;
        setSelectedMedicineId(medicineId);
        setInspectedSupplierName(null);
        startMedicineEdit(medicine);
        setStatus(`${medicine.name} details loaded into the medicine form`);
    }

    function inspectSupplier(supplierName: string) {
        setInspectedSupplierName(supplierName);
        navigate('batches');
        setEditingBatchId(null);
        setBatchForm((previous) => ({ ...previous, supplier: supplierName }));
        setStatus(`${supplierName} loaded into the batch supplier field`);
    }

    const forecastChartData = useMemo(
        () => ({
            labels: dashboardData?.forecast?.points.map((point) => `${point.horizon_days}d`) ?? [],
            datasets: [
                {
                    label: 'Predicted consumption',
                    data: dashboardData?.forecast?.points.map((point) => point.predicted_quantity) ?? [],
                    borderColor: '#183153',
                    backgroundColor: 'rgba(24, 49, 83, 0.18)',
                    fill: true,
                    tension: 0.35,
                },
            ],
        }),
        [dashboardData],
    );

    async function restoreSession() {
        try {
            const data = await apiRequest<AuthMeResponse>('/auth/me', token, { method: 'GET' });
            if (!['admin', 'pharmacist', 'platform_admin'].includes(data.user.role)) {
                throw new Error('This account role is no longer supported. Sign in with an admin or pharmacist account.');
            }
            setCurrentUser(data.user);
            localStorage.setItem(USER_KEY, JSON.stringify(data.user));
            setStatus(`Signed in as ${data.user.full_name}`);
        } catch {
            clearSession();
        } finally {
            setSessionChecked(true);
        }
    }

    async function loadWorkspace(medicineId?: number | null, roleOverride?: string) {
        if (!token) {
            return;
        }
        const requestId = ++workspaceRequestRef.current;
        setLoading(true);
        try {
            const role = roleOverride ?? currentUser?.role;
            const [summary, medicines, batches, alerts, suppliersData, departmentsData, locationsData, purchaseOrdersData, salesData, transactionsData, departmentInventoryData, categoriesData, insightsData, financialSummary, equipmentData, pickupsData, smtpStatusData, expiryTransfersData] = await Promise.all([
                apiRequest<Summary>('/dashboard/summary', token),
                apiRequest<Medicine[]>('/medicines', token),
                apiRequest<Batch[]>('/batches', token),
                apiRequest<AlertItem[]>('/alerts', token),
                apiRequest<Supplier[]>('/suppliers', token),
                apiRequest<Department[]>('/departments', token),
                apiRequest<Location[]>('/locations', token),
                apiRequest<PurchaseOrder[]>('/purchase-orders', token),
                apiRequest<SaleInvoice[]>('/sales', token),
                apiRequest<Transaction[]>('/transactions', token),
                apiRequest<DepartmentInventory[]>('/department-inventory', token),
                apiRequest<Category[]>('/categories', token),
                apiRequest<Insight>('/dashboard/insights', token),
                apiRequest<FinancialSummary>('/reports/financial-summary', token),
                apiRequest<Equipment[]>('/waste/equipment', token),
                apiRequest<WastePickup[]>('/waste/pickups', token),
                apiRequest<SmtpStatus>('/communications/smtp-status', token),
                apiRequest<ExpiryCompanyTransfer[]>('/expiry-company-transfers', token),
            ]);
            const forecast = medicines[0] ? await apiRequest<Forecast>(`/forecasts/${medicineId ?? medicines[0].id}`, token) : null;
            if (requestId !== workspaceRequestRef.current) return;
            setDashboardData({ summary, medicines, batches, alerts, forecast, suppliers: suppliersData, departments: departmentsData, locations: locationsData, purchaseOrders: purchaseOrdersData, transactions: transactionsData, categories: categoriesData, insights: insightsData });
            setSuppliers(suppliersData);
            setDepartments(departmentsData);
            setLocations(locationsData);
            setPurchaseOrders(purchaseOrdersData);
            setSales(salesData);
            setTransactions(transactionsData);
            setDepartmentInventory(departmentInventoryData);
            setFinancials(financialSummary);
            setEquipment(equipmentData);
            setWastePickups(pickupsData);
            setSmtpStatus(smtpStatusData);
            setExpiryTransfers(expiryTransfersData);
            setCategories(categoriesData);
            setInsights(insightsData);
            if (currentUser?.role === 'admin') {
                const [usersData, requestsData] = await Promise.all([apiRequest<User[]>('/users', token), apiRequest<ProcurementRequest[]>('/procurement/requests', token)]);
                setUsers(usersData);
                setProcurementRequests(requestsData);
            }
            setSelectedMedicineId((previous) => previous ?? medicines[0]?.id ?? null);
            if (!editingMedicineId && medicines[0]) {
                setMedicineForm((previous) => (previous.id ? previous : { ...previous, active: true }));
            }
            if (!editingBatchId && medicines[0]) {
                setBatchForm((previous) => (previous.id ? previous : { ...previous, medicine_id: String(medicines[0].id) }));
            }
            setStatus('Data refreshed');
        } catch (error) {
            setStatus(error instanceof Error ? error.message : 'Failed to load workspace');
        } finally {
            if (requestId === workspaceRequestRef.current) setLoading(false);
        }
    }

    async function refreshForecast(medicineId: number) {
        if (!token) return;
        try {
            const forecast = await apiRequest<Forecast>(`/forecasts/${medicineId}`, token);
            setDashboardData((previous) => previous ? { ...previous, forecast } : previous);
        } catch (error) {
            setStatus(error instanceof Error ? error.message : 'Forecast refresh failed');
        }
    }

    async function handleLogin() {
        setLoading(true);
        try {
            const data = await apiRequest<LoginResponse>('/auth/login', null, {
                method: 'POST',
                body: JSON.stringify({ username: authUsername, password: authPassword }),
            });
            if (!['admin', 'pharmacist', 'platform_admin'].includes(data.user.role)) {
                throw new Error('This account role is no longer supported. Sign in with an admin or pharmacist account.');
            }
            setToken(data.access_token);
            setSessionChecked(true);
            setCurrentUser(data.user);
            localStorage.setItem(TOKEN_KEY, data.access_token);
            localStorage.setItem(USER_KEY, JSON.stringify(data.user));
            setStatus(`Signed in as ${data.user.full_name}`);
            setSelectedMedicineId(null);
            navigate('welcome');
            await loadWorkspace(null, data.user.role);
        } catch (error) {
            setStatus(error instanceof Error ? error.message : 'Login failed');
        } finally {
            setLoading(false);
        }
    }

    async function saveUser() {
        if (!token) return;
        try {
            const payload = { full_name: userForm.full_name, email: userForm.email || null, role: userForm.role, ...(userForm.id ? (userForm.password ? { password: userForm.password } : {}) : { username: userForm.username, password: userForm.password }) };
            await apiRequest(userForm.id ? `/users/${userForm.id}` : '/users', token, { method: userForm.id ? 'PUT' : 'POST', body: JSON.stringify(payload) });
            setUserForm({ username: '', full_name: '', email: '', role: 'pharmacist', password: '' });
            await loadWorkspace(selectedMedicineId);
            setStatus('User account saved');
        } catch (error) { setStatus(error instanceof Error ? error.message : 'User save failed'); }
    }

    async function deleteUser(id: number) {
        if (!token || !window.confirm('Delete this user account?')) return;
        try { await apiRequest(`/users/${id}`, token, { method: 'DELETE' }); await loadWorkspace(selectedMedicineId); setStatus('User deleted'); }
        catch (error) { setStatus(error instanceof Error ? error.message : 'User delete failed'); }
    }

    async function loadPharmacies() {
        if (!token) return;
        try { setPharmacies(await apiRequest<Pharmacy[]>('/pharmacies', token)); }
        catch (error) { setStatus(error instanceof Error ? error.message : 'Could not load pharmacies'); }
    }

    async function createPharmacy() {
        if (!token) return;
        if (!pharmacyForm.name.trim() || !pharmacyForm.admin_username.trim() || !pharmacyForm.admin_full_name.trim() || !pharmacyForm.admin_password) { setStatus('Enter the pharmacy name and all first administrator credentials'); return; }
        setLoading(true);
        try {
            await apiRequest<Pharmacy>('/pharmacies', token, { method: 'POST', body: JSON.stringify(pharmacyForm) });
            setPharmacyForm({ name: '', hospital_name: '', licence_number: '', address: '', admin_username: '', admin_full_name: '', admin_email: '', admin_password: '' });
            await loadPharmacies(); setStatus('Pharmacy created and its administrator account is ready');
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Could not create pharmacy'); }
        finally { setLoading(false); }
    }

    async function disposeExpiredBatch(batch: Batch) {
        if (!token) return;
        const method = window.prompt('Collection route: supplier/company representative return OR licensed biomedical-waste collector', 'supplier/company representative return');
        if (!method) return;
        const pickup_contact = window.prompt('Collector/company contact name or phone:');
        if (!pickup_contact) return;
        try {
            await apiRequest<Batch>(`/batches/${batch.id}/collection-request`, token, { method: 'POST', body: JSON.stringify({ method, pickup_contact }) });
            setStatus(`${batch.batch_number} quarantined; collection request recorded`);
            await loadWorkspace(selectedMedicineId);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Disposal recording failed'); }
    }

    async function confirmCollection(batch: Batch) {
        if (!token) return;
        const handover_reference = window.prompt('Enter the signed return challan / biomedical-waste manifest number:');
        if (!handover_reference) return;
        try {
            await apiRequest<Batch>(`/batches/${batch.id}/confirm-collection`, token, { method: 'POST', body: JSON.stringify({ handover_reference }) });
            setStatus(`${batch.batch_number} collection confirmed; custody record closed`);
            await loadWorkspace(selectedMedicineId);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Collection confirmation failed'); }
    }

    async function emailSupplierForReturn(batch: Batch) {
        if (!token) return;
        try {
            const result = await apiRequest<{ detail: string }>(`/batches/${batch.id}/email-supplier-return`, token, { method: 'POST' });
            setStatus(result.detail);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Supplier return email failed'); }
    }

    async function emailSupplierForExpiry(batch: Batch) {
        if (!token) return;
        try {
            const result = await apiRequest<{ detail: string }>(`/batches/${batch.id}/email-expiry-reminder`, token, { method: 'POST' });
            setStatus(result.detail);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Supplier reminder email failed'); }
    }

    async function testSmtp() {
        if (!token) return;
        try {
            const result = await apiRequest<{ detail: string }>('/communications/test-email', token, { method: 'POST', body: JSON.stringify({ recipient: smtpRecipient || null, subject: smtpSubject, body: smtpBody }) });
            setStatus(result.detail);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'SMTP test failed'); }
    }

    async function createExpiryCompanyQuote() {
        if (!token || !expiryCompanyForm.batchId) { setStatus('Select an expired batch for the company quote'); return; }
        try {
            const quote = await apiRequest<ExpiryCompanyTransfer>(`/batches/${expiryCompanyForm.batchId}/expiry-company-quote`, token, { method: 'POST', body: JSON.stringify({ company_name: expiryCompanyForm.companyName, company_contact: expiryCompanyForm.companyContact, quantity: Number(expiryCompanyForm.quantity), recovery_unit_price: expiryCompanyForm.recoveryUnitPrice ? Number(expiryCompanyForm.recoveryUnitPrice) : null }) });
            setExpiryTransfers((previous) => [quote, ...previous]);
            setExpiryCompanyForm({ batchId: '', companyName: '', companyContact: '', quantity: '1', recoveryUnitPrice: '' });
            setStatus(`${quote.quote_number} created for ${quote.company_name}`);
            await loadWorkspace(selectedMedicineId);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Expiry company quote failed'); }
    }

    async function confirmExpiryCompanyTransfer(transfer: ExpiryCompanyTransfer) {
        if (!token) return;
        const transferReference = window.prompt('Enter the company receipt / recovery certificate reference:');
        if (!transferReference) return;
        try {
            const updated = await apiRequest<ExpiryCompanyTransfer>(`/expiry-company-transfers/${transfer.id}/confirm`, token, { method: 'POST', body: JSON.stringify({ transfer_reference: transferReference }) });
            setExpiryTransfers((previous) => previous.map((item) => item.id === updated.id ? updated : item));
            setStatus(`${updated.invoice_number} recorded for ${updated.company_name}`);
            await loadWorkspace(selectedMedicineId);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Expiry company transfer failed'); }
    }

    async function saveEquipment() {
        if (!token || !equipmentForm.name.trim() || !equipmentForm.asset_number.trim()) { setStatus('Enter the equipment name and asset number'); return; }
        try {
            const created = await apiRequest<Equipment>('/waste/equipment', token, { method: 'POST', body: JSON.stringify({ ...equipmentForm, quantity: Number(equipmentForm.quantity), expiry_date: equipmentForm.expiry_date || null }) });
            setEquipment((previous) => [created, ...previous]);
            setEquipmentForm({ name: '', asset_number: '', equipment_type: 'Medical equipment', waste_category: 'General equipment', quantity: '1', unit: 'piece', expiry_date: '', condition: 'usable', location: 'Main Store' });
            setStatus('Medical equipment added to the waste register');
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Equipment save failed'); }
    }

    async function scheduleWastePickup() {
        if (!token || !pickupForm.vendor_name.trim() || !pickupForm.item_summary.trim()) { setStatus('Enter the licensed vendor and waste items'); return; }
        try {
            const created = await apiRequest<WastePickup>('/waste/pickups', token, { method: 'POST', body: JSON.stringify(pickupForm) });
            setWastePickups((previous) => [created, ...previous]);
            setPickupForm({ vendor_name: '', vendor_contact: '', scheduled_date: new Date().toISOString().slice(0, 10), waste_category: 'Expired medicines', item_summary: '', notes: '' });
            setStatus(`${created.pickup_number} scheduled; manifest can be recorded after handover`);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Pickup scheduling failed'); }
    }

    async function updateWastePickup(pickup: WastePickup, status: string) {
        if (!token) return;
        const reference = window.prompt(status === 'collected' ? 'Enter manifest / handover reference:' : 'Enter certificate of destruction reference:');
        if (!reference) return;
        try {
            const updated = await apiRequest<WastePickup>(`/waste/pickups/${pickup.id}`, token, { method: 'PUT', body: JSON.stringify({ status, ...(status === 'collected' ? { manifest_number: reference } : { certificate_reference: reference }) }) });
            setWastePickups((previous) => previous.map((item) => item.id === updated.id ? updated : item));
            setStatus(`${updated.pickup_number} updated with compliance reference`);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Waste record update failed'); }
    }

    async function scanProcurement() {
        if (!token) return;
        try {
            const created = await apiRequest<ProcurementRequest[]>('/procurement/scan', token, { method: 'POST' });
            setProcurementRequests((previous) => [...created, ...previous]);
            setStatus(created.length ? `${created.length} procurement request(s) created and emailed for review` : 'No new procurement actions are needed');
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Procurement scan failed'); }
    }

    async function sendProcurement(id: number) {
        if (!token) return;
        try {
            const updated = await apiRequest<ProcurementRequest>(`/procurement/requests/${id}/send`, token, { method: 'POST' });
            setProcurementRequests((previous) => previous.map((request) => request.id === id ? updated : request));
            setStatus(`${updated.request_number} sent to supplier; ${updated.invoice_number} generated`);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Supplier order was not sent'); }
    }

    async function uploadMedicines() {
        if (!token || !importFile) { setStatus('Select a CSV file first'); return; }
        try {
            const body = new FormData(); body.append('file', importFile);
            const response = await fetch(`${API_BASE}/imports/medicines`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body });
            const result = await response.json() as { created?: number; updated?: number; skipped?: number; detail?: string };
            if (!response.ok) throw new Error(result.detail || 'Import failed');
            setStatus(`Import complete: ${result.created} created, ${result.updated} updated, ${result.skipped} skipped`);
            setImportFile(null); await loadWorkspace(selectedMedicineId);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Import failed'); }
    }

    async function dispenseMedicine() {
        if (!token) return;
        try {
            const batch = await apiRequest<Batch>('/dispense', token, { method: 'POST', body: JSON.stringify({ lookup: dispenseLookup, quantity: Number(dispenseQuantity), department: dispenseDepartment, note: dispenseNote || null }) });
            setStatus(`Dispensed using FEFO batch ${batch.batch_number}; ${batch.quantity} units remain`);
            setDispenseLookup(''); setDispenseQuantity('1'); setDispenseNote(''); await loadWorkspace(selectedMedicineId);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Dispensing failed'); }
    }

    async function sellMedicine() {
        if (!token || !buyerName.trim()) { setStatus('Enter the buyer name before generating the bill'); return; }
        if (!saleLookup.trim()) { setStatus('Select an available medicine or batch before generating the bill'); return; }
        try {
            const bill = await apiRequest<SaleInvoice>('/sales', token, { method: 'POST', body: JSON.stringify({ lookup: saleLookup, quantity: Number(saleQuantity), buyer_name: buyerName, buyer_phone: buyerPhone || null }) });
            setLatestBill(bill);
            setSaleLookup(''); setSelectedSaleBatchId(null); setSaleQuantity('1'); setSalePrice('0'); setBuyerName(''); setBuyerPhone('');
            setStatus(`Bill ${bill.invoice_number} generated`);
            await loadWorkspace(selectedMedicineId);
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Unable to complete the sale'); }
    }

    function clearSession() {
        setToken(null);
        setSessionChecked(true);
        setCurrentUser(null);
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        setDashboardData(null);
        setStatus('Signed out');
    }

    async function saveMedicine() {
        if (!token) {
            return;
        }
        const payload = {
            name: medicineForm.name,
            sku: medicineForm.sku,
            category: medicineForm.category,
            unit: medicineForm.unit,
            reorder_level: Number(medicineForm.reorder_level),
            ideal_stock: Number(medicineForm.ideal_stock),
            active: medicineForm.active,
            description: medicineForm.description || null,
        };
        try {
            if (editingMedicineId) {
                await apiRequest(`/medicines/${editingMedicineId}`, token, { method: 'PUT', body: JSON.stringify(payload) });
            } else {
                await apiRequest('/medicines', token, { method: 'POST', body: JSON.stringify(payload) });
            }
            setMedicineForm(emptyMedicineForm);
            setEditingMedicineId(null);
            await loadWorkspace(selectedMedicineId);
            setStatus('Medicine saved');
        } catch (error) {
            setStatus(error instanceof Error ? error.message : 'Medicine save failed');
        }
    }

    async function deleteMedicine(id: number) {
        if (!token || !window.confirm('Delete this medicine and its batches?')) {
            return;
        }
        try {
            await apiRequest(`/medicines/${id}`, token, { method: 'DELETE' });
            if (selectedMedicineId === id) {
                setSelectedMedicineId(null);
            }
            await loadWorkspace();
            setStatus('Medicine deleted');
        } catch (error) {
            setStatus(error instanceof Error ? error.message : 'Medicine delete failed');
        }
    }

    async function saveBatch() {
        if (!token) {
            return;
        }
        const payload = {
            medicine_id: Number(batchForm.medicine_id),
            batch_number: batchForm.batch_number,
            supplier: batchForm.supplier,
            quantity: Number(batchForm.quantity),
            unit_price: Number(batchForm.unit_price),
            recovery_unit_price: Number(batchForm.recovery_unit_price),
            received_on: batchForm.received_on,
            expiry_date: batchForm.expiry_date,
            location: batchForm.location,
        };
        try {
            if (editingBatchId) {
                await apiRequest(`/batches/${editingBatchId}`, token, { method: 'PUT', body: JSON.stringify(payload) });
            } else {
                await apiRequest('/batches', token, { method: 'POST', body: JSON.stringify(payload) });
            }
            setBatchForm(emptyBatchForm);
            setEditingBatchId(null);
            await loadWorkspace(selectedMedicineId);
            setStatus('Batch saved');
        } catch (error) {
            setStatus(error instanceof Error ? error.message : 'Batch save failed');
        }
    }

    async function deleteBatch(id: number) {
        if (!token || !window.confirm('Delete this batch?')) {
            return;
        }
        try {
            await apiRequest(`/batches/${id}`, token, { method: 'DELETE' });
            await loadWorkspace(selectedMedicineId);
            setStatus('Batch deleted');
        } catch (error) {
            setStatus(error instanceof Error ? error.message : 'Batch delete failed');
        }
    }

    function startMedicineEdit(medicine: Medicine) {
        setActiveTab('medicines');
        setEditingMedicineId(medicine.id);
        setMedicineForm({
            id: medicine.id,
            name: medicine.name,
            sku: medicine.sku,
            category: medicine.category,
            unit: medicine.unit,
            reorder_level: String(medicine.reorder_level),
            ideal_stock: String(medicine.ideal_stock),
            active: medicine.active,
            description: medicine.description ?? '',
        });
    }

    function startBatchEdit(batch: Batch) {
        navigate('batches');
        setEditingBatchId(batch.id);
        setBatchForm({
            id: batch.id,
            medicine_id: String(batch.medicine_id),
            batch_number: batch.batch_number,
            supplier: batch.supplier,
            quantity: String(batch.quantity),
            unit_price: String(batch.unit_price),
            recovery_unit_price: String(batch.recovery_unit_price),
            received_on: batch.received_on,
            expiry_date: batch.expiry_date,
            location: batch.location,
        });
    }

    const availableSaleBatches = (dashboardData?.batches ?? [])
        .filter((batch) => batch.quantity > 0 && batch.disposal_status === 'active' && new Date(batch.expiry_date) >= new Date(new Date().toISOString().slice(0, 10)))
        .slice()
        .sort((left, right) => new Date(left.expiry_date).getTime() - new Date(right.expiry_date).getTime());

    const medicineById = new Map((dashboardData?.medicines ?? []).map((medicine) => [medicine.id, medicine]));
    const saleBatchIndex = new Map(availableSaleBatches.map((batch) => [batch.id, batch]));
    const selectedSaleBatch = saleBatchIndex.get(selectedSaleBatchId ?? -1) ?? availableSaleBatches.find((batch) => batch.batch_number === saleLookup) ?? null;

    const saleMedicineCards = Array.from(
        availableSaleBatches.reduce((grouped, batch) => {
            const current = grouped.get(batch.medicine_id);
            const medicine = medicineById.get(batch.medicine_id);
            if (!current) {
                grouped.set(batch.medicine_id, { medicineName: batch.medicine_name ?? medicine?.name ?? 'Unknown medicine', medicineSku: medicine?.sku ?? '', batches: [batch] });
                return grouped;
            }
            current.batches.push(batch);
            return grouped;
        }, new Map<number, { medicineName: string; medicineSku: string; batches: Batch[] }>()),
    )
        .map(([medicineId, entry]) => {
            const orderedBatches = entry.batches.slice().sort((left, right) => new Date(left.expiry_date).getTime() - new Date(right.expiry_date).getTime());
            const nextBatch = orderedBatches[0];
            return {
                medicineId,
                medicineName: entry.medicineName,
                medicineSku: entry.medicineSku,
                batchCount: orderedBatches.length,
                availableQuantity: nextBatch.quantity,
                nextBatch,
            };
        })
        .filter((entry) => {
            const query = saleSearch.trim().toLowerCase();
            if (!query) {
                return true;
            }
            return `${entry.medicineName} ${entry.medicineSku} ${entry.nextBatch.batch_number} ${entry.nextBatch.supplier}`.toLowerCase().includes(query);
        })
        .sort((left, right) => left.medicineName.localeCompare(right.medicineName));

    function selectSaleBatch(batch: Batch) {
        setSelectedSaleBatchId(batch.id);
        setSaleLookup(batch.batch_number);
        setSalePrice(String(batch.unit_price));
        setStatus(`${batch.medicine_name} selected from batch ${batch.batch_number}`);
    }

    function selectSaleMedicine(medicineId: number) {
        const medicineEntry = saleMedicineCards.find((entry) => entry.medicineId === medicineId);
        if (!medicineEntry) {
            return;
        }
        selectSaleBatch(medicineEntry.nextBatch);
    }

    const canEdit = currentUser?.role === 'admin' || currentUser?.role === 'pharmacist';
    const visiblePages: { page: Page; label: string; icon: string; roles: string[] }[] = [
        { page: 'finance', label: 'Sales & purchases', icon: '₹', roles: ['admin', 'pharmacist'] },
        { page: 'expiry', label: t.expiry, icon: '!', roles: ['admin', 'pharmacist'] },
        { page: 'welcome', label: t.workspace, icon: '⌂', roles: ['admin', 'pharmacist'] },
        { page: 'dashboard', label: t.dashboard, icon: '◫', roles: ['admin', 'pharmacist'] },
        { page: 'medicines', label: t.medicines, icon: '✚', roles: ['admin', 'pharmacist'] },
        { page: 'batches', label: t.batches, icon: '▣', roles: ['admin', 'pharmacist'] },
        { page: 'dispense', label: t.dispense, icon: '↗', roles: ['admin', 'pharmacist'] },
        { page: 'sales', label: 'Sales & Billing', icon: '₹', roles: ['admin', 'pharmacist'] },
        { page: 'import', label: t.import, icon: '⇧', roles: ['admin', 'pharmacist'] },
        { page: 'suppliers', label: t.suppliers, icon: '♧', roles: ['admin', 'pharmacist'] },
        { page: 'transactions', label: t.transactions, icon: '↻', roles: ['admin', 'pharmacist'] },
        { page: 'departments', label: 'Department Stock', icon: '⌁', roles: ['admin', 'pharmacist'] },
        { page: 'reference', label: 'Storage map', icon: '◌', roles: ['admin', 'pharmacist'] },
        { page: 'users', label: t.users, icon: '♙', roles: ['admin'] },
        { page: 'procurement', label: 'Procurement', icon: '✉', roles: ['admin'] },
        { page: 'reports', label: t.reports, icon: '▤', roles: ['admin', 'pharmacist'] },
    ];

    useEffect(() => {
        if (currentUser && !visiblePages.some((item) => item.page === activeTab && item.roles.includes(currentUser.role))) {
            navigate('welcome');
        }
    }, [activeTab, currentUser?.role]);

    if (!token || !currentUser) {
        return (
            <div className="shell login-shell">
                <aside className="hero-panel login-hero">
                    <section className="login-copy">
                        <div className="brand"><span className="brand-mark">+</span><span>ArogyaMitra<small>HEALTH SYSTEMS</small></span></div>
                        <div className="badge">SMART PHARMACY PLATFORM</div>
                        <h1>Medicine operations, made reassuringly simple.</h1>
                        <p>One calm place to protect medicine availability, reduce expiry risk, and keep every ward moving.</p>
                        <div className="login-benefits"><span><b>●</b> Batch-level safety</span><span><b>●</b> FEFO dispensing</span><span><b>●</b> Live stock visibility</span></div>
                    </section>

                    <div className="login-card">
                        <div className="login-card-heading"><span className="section-title">Welcome back</span><h2>Sign in to your workspace</h2><p>Choose a demo role or enter your account details.</p></div>
                        <div className="preset-row">
                            {rolePresets.map((preset) => (
                                <button key={preset.username} className={authUsername === preset.username ? 'preset active' : 'preset'} onClick={() => { setAuthUsername(preset.username); setAuthPassword(preset.password); }}>{preset.label}</button>
                            ))}
                        </div>
                        <label>Username<input value={authUsername} onChange={(event) => setAuthUsername(event.target.value)} /></label>
                        <label>Password<input type="password" value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} /></label>
                        <button className="primary" onClick={handleLogin} disabled={loading}>{loading ? 'Signing in...' : 'Sign in securely →'}</button>
                        <div className="login-help">Demo access only · Your role controls what you can see.</div>
                    </div>
                </aside>

                <main className="content empty-state">
                    <div className="topbar">
                        <div>
                            <div className="eyebrow">Access required</div>
                            <h2>Sign in to manage medicines, batches, and reports</h2>
                        </div>
                        <div className="status-chip">{status}</div>
                    </div>
                </main>
            </div>
        );
    }

    if (currentUser.role !== 'platform_admin' && (!sessionChecked || !dashboardData)) {
        return (
            <div className="shell workspace-loading-shell">
                <main className="content workspace-loading">
                    <div className="loading-mark">+</div>
                    <div className="eyebrow">ArogyaMitra workspace</div>
                    <h2>Loading the latest pharmacy data</h2>
                    <p>Checking your session, stock, expiry records, and operational totals.</p>
                </main>
            </div>
        );
    }

    if (currentUser.role === 'platform_admin') {
        return <div className="shell"><aside className="hero-panel sticky-panel"><div className="brand"><span className="brand-mark">+</span><span>ArogyaMitra<small>HEALTH SYSTEMS</small></span></div><div className="badge">PLATFORM ADMIN</div><h1>Hospital & Pharmacy Setup</h1><p>Create each organisation, appoint its first pharmacy administrator, then let that team manage its own stock.</p><button className="logout-button" onClick={clearSession}>Sign out</button></aside><main className="content"><header className="topbar"><div><div className="eyebrow">Central administration</div><h2>Add a hospital or pharmacy</h2></div><div className="status-chip">{status}</div></header><section className="workspace-grid"><div className="panel"><div className="section-title">Step 1 · Organisation</div><FormGrid><Field label="Pharmacy name" value={pharmacyForm.name} onChange={(value) => setPharmacyForm(p => ({ ...p, name: value }))} /><Field label="Hospital name" value={pharmacyForm.hospital_name} onChange={(value) => setPharmacyForm(p => ({ ...p, hospital_name: value }))} /><Field label="Licence number" value={pharmacyForm.licence_number} onChange={(value) => setPharmacyForm(p => ({ ...p, licence_number: value }))} /><Field label="Address" value={pharmacyForm.address} onChange={(value) => setPharmacyForm(p => ({ ...p, address: value }))} /></FormGrid><div className="section-title">Step 2 · First pharmacy administrator</div><FormGrid><Field label="Admin full name" value={pharmacyForm.admin_full_name} onChange={(value) => setPharmacyForm(p => ({ ...p, admin_full_name: value }))} /><Field label="Admin username" value={pharmacyForm.admin_username} onChange={(value) => setPharmacyForm(p => ({ ...p, admin_username: value }))} /><Field label="Admin email" value={pharmacyForm.admin_email} onChange={(value) => setPharmacyForm(p => ({ ...p, admin_email: value }))} type="email" /><Field label="Temporary password" value={pharmacyForm.admin_password} onChange={(value) => setPharmacyForm(p => ({ ...p, admin_password: value }))} type="password" /></FormGrid><button className="primary inline" onClick={createPharmacy} disabled={loading}>{loading ? 'Creating workspace…' : 'Create pharmacy workspace'}</button></div><div className="panel"><div className="section-title">Registered organisations</div><table className="data-table"><thead><tr><th>Pharmacy</th><th>Hospital</th><th>Licence</th></tr></thead><tbody>{pharmacies.map(pharmacy => <tr key={pharmacy.id}><td>{pharmacy.name}</td><td>{pharmacy.hospital_name || '-'}</td><td>{pharmacy.licence_number || '-'}</td></tr>)}</tbody></table></div></section></main></div>;
    }

    return (
        <div className="shell">
            <aside className="hero-panel sticky-panel">
                <div className="brand"><span className="brand-mark">+</span><span>ArogyaMitra<small>HEALTH SYSTEMS</small></span></div>
                <div className="badge">LIVE OPERATIONS</div>
                <h1>Pharmacy Operations</h1>
                <p>
                    Track batch-level stock, catch near-expiry medicines early, and use forecast-driven reorder recommendations to keep critical drugs available.
                </p>

                <div className="nav-stack">
                    {visiblePages.filter((item) => item.roles.includes(currentUser.role)).map((item) => <button key={item.page} className={activeTab === item.page ? 'nav-pill active' : 'nav-pill'} onClick={() => navigate(item.page)}><span className="nav-icon">{item.icon}</span>{item.label}</button>)}
                </div>

                <div className="muted">{status}</div>
            </aside>

            <main className="content">
                <header className="topbar">
                    <div>
                        <div className="eyebrow">{t.control}</div>
                        <h2>{activeTab === 'welcome' ? `Good to see you, ${currentUser.full_name.split(' ')[0]}` : t[activeTab as keyof typeof t] ?? 'Workspace'}</h2>
                    </div>
                    <div className="top-actions">
                        <label className="language-picker">{t.language}<select value={language} onChange={(event) => setLanguage(event.target.value as 'en' | 'hi' | 'bn')}><option value="en">English</option><option value="hi">हिन्दी</option><option value="bn">বাংলা</option></select></label>
                        <div className="account-chip"><span>{currentUser.full_name}</span><small>{currentUser.role === 'pharmacist' ? 'Pharmacy Officer' : 'Pharmacy Administrator'}</small></div>
                        <button className="logout-button" onClick={clearSession}>{t.signOut}</button>
                        <div className="status-chip">{loading ? 'Loading...' : dashboardData?.summary.forecast_signal ?? 'Ready'}</div>
                    </div>
                </header>

                {activeTab === 'welcome' && dashboardData && (
                    <section className="workspace-grid single-column">
                        <div className="panel welcome-panel">
                            <div className="section-title">Your workspace</div>
                            <h2>Everything your pharmacy needs, in one view.</h2>
                            <p className="lead">You are signed in as a <strong>{displayRole(currentUser.role)}</strong>. This system keeps hospital medicines available, safe to use, and traceable from supplier to ward.</p>
                            <div className="role-grid">
                                <ActionCard title="Today's operations" description={currentUser.role === 'admin' ? 'Maintain team access, catalogue controls, reports, and operational oversight.' : currentUser.role === 'pharmacist' ? 'Receive stock, manage batches, issue medicines using FEFO, and act on expiry alerts.' : 'Review stock availability, expiry risk, forecasts, and operational reports.'} action="Open dashboard" onClick={() => navigate('dashboard')} />
                                {currentUser.role !== 'viewer' && <ActionCard title="Medicine safety" description="Review batch records, storage locations, expiry dates, and alert priorities." action="Review batches" onClick={() => navigate('batches')} />}
                                {currentUser.role === 'admin' && <ActionCard title="Supply continuity" description="Review automated supplier requests and approve only the orders that are needed." action="Open procurement" onClick={() => navigate('procurement')} />}
                                {currentUser.role === 'viewer' && <ActionCard title="Read-only overview" description="Your view is limited to high-level medicine safety and availability signals." action="View dashboard" onClick={() => navigate('dashboard')} />}
                            </div>
                            <div className="action-row"><button className="primary inline" onClick={() => navigate('dashboard')}>Open operations dashboard <span>→</span></button>{canEdit && <button className="secondary inline" onClick={() => navigate('dispense')}>Start dispensing</button>}</div>
                        </div>
                    </section>
                )}

                {activeTab === 'dashboard' && dashboardData && (
                    <>
                        <section className="stats-grid">
                            {currentUser.role === 'viewer' ? <>
                                <StatCard label="Critical stock alerts" value={dashboardData.summary.low_stock_items} tone="red" />
                                <StatCard label="Near-expiry alerts" value={dashboardData.summary.near_expiry_batches} tone="gold" />
                                <StatCard label="Safety status" value={dashboardData.summary.forecast_signal === 'Stable' ? 'Clear' : 'Review'} tone="teal" />
                            </> : <>
                                <StatCard label="Medicines" value={dashboardData.summary.medicines} tone="blue" />
                                <StatCard label="Batches" value={dashboardData.summary.batches} tone="gold" />
                                <StatCard label="Total units" value={dashboardData.summary.total_units} tone="teal" />
                                <StatCard label="Near-expiry batches" value={dashboardData.summary.near_expiry_batches} tone="red" />
                            </>}
                        </section>

                        {currentUser.role !== 'viewer' && <section className="stats-grid compact-grid">
                            <StatCard label="Suppliers" value={dashboardData.insights.total_suppliers} tone="blue" />
                            <StatCard label="Departments" value={dashboardData.insights.total_departments} tone="gold" />
                            <StatCard label="Transactions" value={dashboardData.insights.total_transactions} tone="teal" />
                            <StatCard label="Purchase orders" value={dashboardData.insights.total_purchase_orders} tone="red" />
                        </section>}

                        <section className={currentUser.role === 'viewer' ? 'layout-grid single-dashboard-panel' : 'layout-grid'}>
                            {currentUser.role !== 'viewer' && <div className="panel">
                                <div className="panel-header">
                                    <div>
                                        <div className="section-title">Forecast</div>
                                        <h3>{dashboardData.forecast?.medicine_name ?? 'Select a medicine'}</h3>
                                    </div>
                                    <div className="recommendation">Reorder {dashboardData.forecast?.recommendation ?? 0}</div>
                                </div>
                                <div className="chart-wrap">
                                    <Line data={forecastChartData} />
                                </div>
                                <div className="forecast-copy">
                                    Recent daily average: {dashboardData.forecast?.recent_daily_avg.toFixed(1) ?? '0.0'} units. Predictions shown for 30, 60, and 90 days.
                                </div>
                            </div>}

                            {currentUser.role === 'viewer' ? <div className="panel restricted-overview">
                                <div className="section-title">Restricted safety view</div>
                                <h3>Hospital operational details are protected</h3>
                                <p className="muted">This account can view only high-level safety signals. Medicine records, supplier details, storage locations, ward activity, and order information are not available to this role.</p>
                            </div> : <div className="panel">
                                <div className="panel-header">
                                    <div>
                                        <div className="section-title">Medicines</div>
                                        <h3>Catalogue and reorder levels</h3>
                                    </div>
                                </div>
                                <div className="list-box">
                                    {dashboardData.medicines.map((medicine) => (
                                        <button
                                            key={medicine.id}
                                            className={medicine.id === selectedMedicineId ? 'medicine-row active' : 'medicine-row'}
                                            onClick={() => setSelectedMedicineId(medicine.id)}
                                        >
                                            <span>
                                                <strong>{medicine.name}</strong>
                                                <small>{medicine.category} · SKU {medicine.sku}</small>
                                            </span>
                                            <span>{medicine.reorder_level} min</span>
                                        </button>
                                    ))}
                                </div>
                            </div>}
                        </section>

                        {currentUser.role !== 'viewer' && <section className="layout-grid bottom-grid">
                            <div className="panel">
                                <div className="panel-header">
                                    <div>
                                        <div className="section-title">Alerts</div>
                                        <h3>Near-expiry and low-stock watchlist</h3>
                                    </div>
                                </div>
                                <div className="alert-list">
                                    {dashboardData.alerts.map((alert) => (
                                        <article key={alert.id} className={`alert-card ${alert.severity}`}>
                                            <div>
                                                <strong>{alert.medicine_name}</strong>
                                                <p>{alert.message}</p>
                                            </div>
                                            <div className="alert-meta">
                                                <span>{alert.alert_type.replace('_', ' ')}</span>
                                                <span>{alert.due_on ?? 'stock'}</span>
                                            </div>
                                        </article>
                                    ))}
                                </div>
                            </div>

                            <div className="panel">
                                <div className="panel-header">
                                    <div>
                                        <div className="section-title">Operations</div>
                                        <h3>Role-based portal</h3>
                                    </div>
                                </div>
                                <div className="role-cards">
                                    <RoleCard title="Admin" description="Full inventory, user, and reporting access." />
                                    <RoleCard title="Pharmacist" description="Manage batches, alerts, and reorder workflows." />
                                    <RoleCard title="Viewer" description="Read-only dashboard for supervisors and auditors." />
                                </div>
                                <div className="footer-note">Export endpoints: inventory CSV, alerts CSV, and alerts PDF are available from the backend.</div>
                            </div>
                        </section>}

                        {currentUser.role !== 'viewer' && <section className="layout-grid">
                            <div className="panel">
                                <div className="panel-header">
                                    <div>
                                        <div className="section-title">Reference</div>
                                        <h3>Categories and storage zones</h3>
                                    </div>
                                </div>
                                <div className="tag-cloud">
                                    {dashboardData.categories.slice(0, 12).map((category) => (
                                        <span key={category.id} className="tag">{category.name}</span>
                                    ))}
                                </div>
                                <div className="reference-list">
                                    {dashboardData.locations.map((location) => (
                                        <div key={location.id} className="reference-row">
                                            <strong>{location.code}</strong>
                                            <span>{location.name}</span>
                                            <small>{location.temperature_zone}</small>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="panel">
                                <div className="panel-header">
                                    <div>
                                        <div className="section-title">Hospital units</div>
                                        <h3>Departments and order pipeline</h3>
                                    </div>
                                </div>
                                <div className="reference-list">
                                    {dashboardData.departments.map((department) => (
                                        <div key={department.id} className="reference-row">
                                            <strong>{department.name}</strong>
                                            <span>Floor {department.floor}</span>
                                            <small>Ext {department.contact_extension}</small>
                                        </div>
                                    ))}
                                </div>
                                <div className="reference-list">
                                    {dashboardData.purchaseOrders.map((order) => (
                                        <div key={order.id} className="reference-row">
                                            <strong>{order.po_number}</strong>
                                            <span>{order.supplier_name}</span>
                                            <small>₹{order.total_amount.toLocaleString()} · {order.status}</small>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </section>}
                    </>
                )}

                {activeTab === 'medicines' && dashboardData && (
                    <section className="workspace-grid">
                        <div className="panel">
                            <div className="panel-header">
                                <div>
                                    <div className="section-title">Medicine CRUD</div>
                                    <h3>{editingMedicineId ? 'Edit medicine' : 'Create medicine'}</h3>
                                </div>
                                <div className="recommendation">{canEdit ? 'Editable' : 'Read only'}</div>
                            </div>
                            <FormGrid>
                                <Field label="Name" value={medicineForm.name} onChange={(value) => setMedicineForm((previous) => ({ ...previous, name: value }))} disabled={!canEdit} />
                                <Field label="SKU" value={medicineForm.sku} onChange={(value) => setMedicineForm((previous) => ({ ...previous, sku: value }))} disabled={!canEdit} />
                                <Field label="Category" value={medicineForm.category} onChange={(value) => setMedicineForm((previous) => ({ ...previous, category: value }))} disabled={!canEdit} />
                                <Field label="Unit" value={medicineForm.unit} onChange={(value) => setMedicineForm((previous) => ({ ...previous, unit: value }))} disabled={!canEdit} />
                                <Field label="Reorder level" value={medicineForm.reorder_level} onChange={(value) => setMedicineForm((previous) => ({ ...previous, reorder_level: value }))} disabled={!canEdit} />
                                <Field label="Ideal stock" value={medicineForm.ideal_stock} onChange={(value) => setMedicineForm((previous) => ({ ...previous, ideal_stock: value }))} disabled={!canEdit} />
                                <Field label="Description" value={medicineForm.description} onChange={(value) => setMedicineForm((previous) => ({ ...previous, description: value }))} disabled={!canEdit} textarea />
                                <label className="switch-field">
                                    <input type="checkbox" checked={medicineForm.active} onChange={(event) => setMedicineForm((previous) => ({ ...previous, active: event.target.checked }))} disabled={!canEdit} />
                                    <span>Active</span>
                                </label>
                            </FormGrid>
                            <div className="action-row">
                                <button className="primary inline" onClick={saveMedicine} disabled={!canEdit}>Save medicine</button>
                                <button
                                    className="secondary inline"
                                    onClick={() => {
                                        setEditingMedicineId(null);
                                        setMedicineForm(emptyMedicineForm);
                                    }}
                                >
                                    Reset
                                </button>
                            </div>
                        </div>

                        <div className="panel">
                            <div className="panel-header">
                                <div>
                                    <div className="section-title">Catalogue</div>
                                    <h3>Medicines and live stock</h3>
                                </div>
                            </div>
                            <div className="catalogue-toolbar"><input value={medicineSearch} onChange={(event) => setMedicineSearch(event.target.value)} placeholder="Search medicine, SKU, or category..." /><span>{medicineRows.length} of {dashboardData.medicines.length} medicines</span></div>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>SKU</th>
                                        <th>Category</th>
                                        <th>Usable stock</th>
                                        <th>Next expiry</th>
                                        <th>Reorder</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {medicineRows.map(({ medicine, stock, batchCount, nextExpiry }) => (
                                        <tr key={medicine.id}>
                                            <td><button className="inline-link" onClick={() => inspectMedicine(medicine.id)}><strong>{medicine.name}</strong></button><small className="muted"> · {batchCount} batch{batchCount === 1 ? '' : 'es'}</small></td>
                                            <td>{medicine.sku}</td>
                                            <td>{medicine.category}</td>
                                            <td className={stock <= medicine.reorder_level ? 'stock-low' : 'stock-healthy'}>{stock.toLocaleString()} {medicine.unit}</td>
                                            <td>{nextExpiry ?? 'No batch'}</td>
                                            <td>{medicine.reorder_level}</td>
                                            <td>
                                                <div className="table-actions">
                                                    <button className="ghost" onClick={() => startMedicineEdit(medicine)} disabled={!canEdit}>Edit</button>
                                                    <button className="ghost danger" onClick={() => deleteMedicine(medicine.id)} disabled={!canEdit}>Delete</button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>
                )}

                {activeTab === 'batches' && dashboardData && (
                    <section className="workspace-grid">
                        <div className="panel">
                            <div className="panel-header">
                                <div>
                                    <div className="section-title">Batch CRUD</div>
                                    <h3>{editingBatchId ? 'Edit batch' : 'Create batch'}</h3>
                                </div>
                                <div className="recommendation">{canEdit ? 'Editable' : 'Read only'}</div>
                            </div>
                            <FormGrid>
                                <Field label="Medicine" value={batchForm.medicine_id} onChange={(value) => setBatchForm((previous) => ({ ...previous, medicine_id: value }))} disabled={!canEdit} select options={dashboardData.medicines.map((medicine) => ({ label: `${medicine.name} (${medicine.sku})`, value: String(medicine.id) }))} />
                                <Field label="Batch number" value={batchForm.batch_number} onChange={(value) => setBatchForm((previous) => ({ ...previous, batch_number: value }))} disabled={!canEdit} />
                                <Field label="Supplier" value={batchForm.supplier} onChange={(value) => setBatchForm((previous) => ({ ...previous, supplier: value }))} disabled={!canEdit} />
                                <Field label="Quantity" value={batchForm.quantity} onChange={(value) => setBatchForm((previous) => ({ ...previous, quantity: value }))} disabled={!canEdit} />
                                <Field label="Selling price (₹)" value={batchForm.unit_price} onChange={(value) => setBatchForm((previous) => ({ ...previous, unit_price: value }))} disabled={!canEdit} type="number" />
                                <Field label="Expiry recovery price (₹/unit)" value={batchForm.recovery_unit_price} onChange={(value) => setBatchForm((previous) => ({ ...previous, recovery_unit_price: value }))} disabled={!canEdit} type="number" />
                                <Field label="Received on" value={batchForm.received_on} onChange={(value) => setBatchForm((previous) => ({ ...previous, received_on: value }))} disabled={!canEdit} type="date" />
                                <Field label="Expiry date" value={batchForm.expiry_date} onChange={(value) => setBatchForm((previous) => ({ ...previous, expiry_date: value }))} disabled={!canEdit} type="date" />
                                <Field label="Storage location" value={batchForm.location} onChange={(value) => setBatchForm((previous) => ({ ...previous, location: value }))} disabled={!canEdit} select options={locations.map((location) => ({ label: `${location.code} — ${location.name}`, value: location.code }))} />
                            </FormGrid>
                            <div className="action-row">
                                <button className="primary inline" onClick={saveBatch} disabled={!canEdit}>Save batch</button>
                                <button
                                    className="secondary inline"
                                    onClick={() => {
                                        setEditingBatchId(null);
                                        setBatchForm(emptyBatchForm);
                                    }}
                                >
                                    Reset
                                </button>
                            </div>
                        </div>

                        <div className="panel">
                            <div className="panel-header">
                                <div>
                                    <div className="section-title">Batch stock</div>
                                    <h3>Batch and expiry tracking</h3>
                                </div>
                            </div>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Medicine</th>
                                        <th>Batch</th>
                                        <th>Qty</th>
                                        <th>Expiry</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {dashboardData.batches.map((batch) => (
                                        <tr key={batch.id}>
                                            <td><button className="inline-link" onClick={() => startBatchEdit(batch)}>{batch.medicine_name ?? batch.medicine_id}</button></td>
                                            <td>{batch.batch_number}</td>
                                            <td>{batch.quantity}</td>
                                            <td>{batch.expiry_date}{batch.disposal_status === 'collection_requested' && <small className="muted"> · pickup requested</small>}{batch.disposal_status === 'disposed' && <small className="muted"> · collected</small>}</td>
                                            <td>
                                                <div className="table-actions">
                                                    <button className="ghost" onClick={() => startBatchEdit(batch)} disabled={!canEdit}>Edit</button>
                                                    {batch.expiry_date < new Date().toISOString().slice(0, 10) && batch.disposal_status !== 'disposed' && batch.disposal_status !== 'collection_requested' && <button className="ghost danger" onClick={() => disposeExpiredBatch(batch)} disabled={!canEdit}>Request collection</button>}
                                                    {batch.expiry_date < new Date().toISOString().slice(0, 10) && batch.disposal_status !== 'disposed' && <button className="ghost" onClick={() => emailSupplierForReturn(batch)} disabled={!canEdit}>Email supplier</button>}
                                                    {batch.disposal_status === 'collection_requested' && <button className="ghost" onClick={() => confirmCollection(batch)} disabled={!canEdit}>Confirm collection</button>}
                                                    <button className="ghost danger" onClick={() => deleteBatch(batch.id)} disabled={!canEdit}>Delete</button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>
                )}

                {activeTab === 'expiry' && dashboardData && (
                    <section className="workspace-grid single-column">
                        <div className="panel">
                            <div className="panel-header"><div><div className="section-title">Expiry & waste control</div><h3>Prevent expiry loss and ensure safe collection</h3><p className="muted">Green: over 6 months. Yellow: 3-6 months, prioritise FEFO or ask supplier for credit. Red: under 3 months, review for return. Black: expired, quarantine and arrange signed collection.</p></div><span className={smtpStatus?.configured ? 'status-label' : 'status-label status-warning'}>{smtpStatus?.configured ? 'SMTP ready' : 'SMTP not configured'}</span></div>
                            <table className="data-table"><thead><tr><th>Zone</th><th>Medicine</th><th>Batch</th><th>Supplier</th><th>Quantity</th><th>Expiry</th><th>Recovery value</th><th>Action</th></tr></thead><tbody>{dashboardData.batches.map((batch) => { const info = getExpirySnapshot(batch.expiry_date, batch.disposal_status); return <tr key={batch.id}><td>{info.expiryBand.toUpperCase()}</td><td>{batch.medicine_name ?? batch.medicine_id}</td><td>{batch.batch_number}</td><td>{batch.supplier}</td><td>{batch.quantity}</td><td>{batch.expiry_date}<small className="muted"> · {info.expiryLabel}</small></td><td>₹{(batch.quantity * batch.recovery_unit_price).toLocaleString()}<small className="muted"> · ₹{batch.recovery_unit_price}/unit</small></td><td><div className="table-actions">{(info.expiryBand === 'yellow' || info.expiryBand === 'red') && <button className="ghost" onClick={() => emailSupplierForExpiry(batch)} disabled={!canEdit}>Email supplier</button>}{info.expiryBand === 'black' && batch.disposal_status !== 'disposed' && <button className="ghost" onClick={() => emailSupplierForReturn(batch)} disabled={!canEdit}>Email return request</button>}{info.expiryBand === 'black' && batch.disposal_status !== 'collection_requested' && batch.disposal_status !== 'recovery_quoted' && batch.disposal_status !== 'disposed' && <button className="ghost danger" onClick={() => disposeExpiredBatch(batch)} disabled={!canEdit}>Request collection</button>}{batch.disposal_status === 'collection_requested' && <button className="ghost" onClick={() => confirmCollection(batch)} disabled={!canEdit}>Confirm collection</button>}{batch.disposal_status === 'recovery_quoted' && <span>Company quote open</span>}{batch.disposal_status === 'disposed' && <span>Collection recorded</span>}</div></td></tr>; })}</tbody></table>
                        </div>
                        <div className="expiry-control-grid">
                            <div className="panel expiry-quote-panel"><div className="panel-header"><div><div className="section-title">Company recovery</div><h3>Quote expired stock to a licensed company</h3><p className="muted">This is separate from normal sales. The batch stays non-saleable until the transfer is confirmed with a company receipt or recovery certificate.</p></div></div><FormGrid><Field label="Expired batch" value={expiryCompanyForm.batchId} onChange={(value) => { const batch = dashboardData.batches.find((item) => String(item.id) === value); setExpiryCompanyForm((previous) => ({ ...previous, batchId: value, recoveryUnitPrice: batch ? String(batch.recovery_unit_price) : previous.recoveryUnitPrice })); }} disabled={!canEdit} select options={dashboardData.batches.filter((batch) => new Date(batch.expiry_date) < new Date() && batch.quantity > 0 && batch.disposal_status === 'active').map((batch) => ({ label: `${batch.medicine_name} · ${batch.batch_number} · ${batch.quantity} units`, value: String(batch.id) }))} /><Field label="Company name" value={expiryCompanyForm.companyName} onChange={(value) => setExpiryCompanyForm((previous) => ({ ...previous, companyName: value }))} disabled={!canEdit} /><Field label="Company contact / licence" value={expiryCompanyForm.companyContact} onChange={(value) => setExpiryCompanyForm((previous) => ({ ...previous, companyContact: value }))} disabled={!canEdit} /><Field label="Quantity" value={expiryCompanyForm.quantity} onChange={(value) => setExpiryCompanyForm((previous) => ({ ...previous, quantity: value }))} disabled={!canEdit} type="number" /><Field label="Recovery price per unit (₹)" value={expiryCompanyForm.recoveryUnitPrice} onChange={(value) => setExpiryCompanyForm((previous) => ({ ...previous, recoveryUnitPrice: value }))} disabled={!canEdit} type="number" /></FormGrid><div className="action-row"><button className="primary inline" onClick={createExpiryCompanyQuote} disabled={!canEdit}>Generate company quote</button></div></div>
                            <div className="panel communication-panel"><div className="panel-header"><div><div className="section-title">Communication centre</div><h3>SMTP delivery check</h3><p className="muted">Supplier reminders and expiry return requests use the configured sender. Test delivery before relying on notifications.</p></div></div><div className="smtp-status-line"><strong>{smtpStatus?.configured ? 'Configured' : 'Not configured'}</strong><span>{smtpStatus?.host || 'Set SMTP_HOST in .env'}</span><span>{smtpStatus?.from_email || 'No sender address'}</span></div><FormGrid><Field label="Test recipient" value={smtpRecipient} onChange={setSmtpRecipient} disabled={!canEdit} type="email" /><Field label="Subject" value={smtpSubject} onChange={setSmtpSubject} disabled={!canEdit} /><Field label="Message" value={smtpBody} onChange={setSmtpBody} disabled={!canEdit} textarea /></FormGrid><div className="action-row"><button className="secondary inline" onClick={testSmtp} disabled={!canEdit}>Send test email</button></div></div>
                        </div>
                        <div className="panel"><div className="panel-header"><div><div className="section-title">Expiry document register</div><h3>Quotes, recovery bills, and transfer references</h3><p className="muted">Every company recovery quote becomes a recorded recovery invoice only after the handover reference is confirmed.</p></div></div><table className="data-table"><thead><tr><th>Quote</th><th>Batch</th><th>Company</th><th>Qty</th><th>Total</th><th>Status</th><th>Document / action</th></tr></thead><tbody>{expiryTransfers.length ? expiryTransfers.map((transfer) => <tr key={transfer.id}><td><strong>{transfer.quote_number}</strong><small className="muted"> · {transfer.quoted_on}</small></td><td>{transfer.medicine_name}<small className="muted"> · {transfer.batch_number}</small></td><td>{transfer.company_name}<small className="muted"> · {transfer.company_contact}</small></td><td>{transfer.quantity}</td><td>₹{transfer.total_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td><td><span className={transfer.status === 'transferred' ? 'status-label' : 'status-label status-warning'}>{transfer.status}</span></td><td>{transfer.status === 'quoted' ? <button className="ghost" onClick={() => confirmExpiryCompanyTransfer(transfer)} disabled={!canEdit}>Confirm handover</button> : <><strong>{transfer.invoice_number}</strong><small className="muted"> · {transfer.transfer_reference}</small></>}</td></tr>) : <tr><td colSpan={7} className="empty-table">No expiry-company quotes yet.</td></tr>}</tbody></table></div>
                        <div className="workspace-grid">
                            <div className="panel">
                                <div className="panel-header"><div><div className="section-title">Equipment waste register</div><h3>Track devices and non-drug items</h3><p className="muted">Register expired, damaged, sharps, infectious, cytotoxic, or general equipment separately from medicine batches.</p></div></div>
                                <FormGrid>
                                    <Field label="Equipment name" value={equipmentForm.name} onChange={(value) => setEquipmentForm((previous) => ({ ...previous, name: value }))} disabled={!canEdit} />
                                    <Field label="Asset / barcode number" value={equipmentForm.asset_number} onChange={(value) => setEquipmentForm((previous) => ({ ...previous, asset_number: value }))} disabled={!canEdit} />
                                    <Field label="Equipment type" value={equipmentForm.equipment_type} onChange={(value) => setEquipmentForm((previous) => ({ ...previous, equipment_type: value }))} disabled={!canEdit} />
                                    <Field label="Waste category" value={equipmentForm.waste_category} onChange={(value) => setEquipmentForm((previous) => ({ ...previous, waste_category: value }))} disabled={!canEdit} select options={['Expired medicines', 'Sharps / needles', 'Cytotoxic', 'Infectious', 'Chemical', 'General equipment'].map((value) => ({ label: value, value }))} />
                                    <Field label="Quantity" value={equipmentForm.quantity} onChange={(value) => setEquipmentForm((previous) => ({ ...previous, quantity: value }))} disabled={!canEdit} type="number" />
                                    <Field label="Expiry date (optional)" value={equipmentForm.expiry_date} onChange={(value) => setEquipmentForm((previous) => ({ ...previous, expiry_date: value }))} disabled={!canEdit} type="date" />
                                    <Field label="Condition" value={equipmentForm.condition} onChange={(value) => setEquipmentForm((previous) => ({ ...previous, condition: value }))} disabled={!canEdit} select options={['usable', 'damaged', 'expired', 'contaminated'].map((value) => ({ label: value, value }))} />
                                    <Field label="Quarantine location" value={equipmentForm.location} onChange={(value) => setEquipmentForm((previous) => ({ ...previous, location: value }))} disabled={!canEdit} />
                                </FormGrid>
                                <div className="action-row"><button className="primary inline" onClick={saveEquipment} disabled={!canEdit}>Add to waste register</button></div>
                                <table className="data-table"><thead><tr><th>Item</th><th>Asset</th><th>Category</th><th>Qty</th><th>Condition</th><th>Status</th></tr></thead><tbody>{equipment.map((item) => <tr key={item.id}><td>{item.name}<small className="muted"> · {item.equipment_type}</small></td><td>{item.asset_number}</td><td>{item.waste_category}</td><td>{item.quantity} {item.unit}</td><td>{item.condition}</td><td>{item.waste_status}</td></tr>)}</tbody></table>
                            </div>
                            <div className="panel">
                                <div className="panel-header"><div><div className="section-title">Licensed waste collection</div><h3>Pickup, manifest, and destruction proof</h3><p className="muted">Schedule a certified biomedical-waste vendor, then record the manifest and certificate of destruction to close custody.</p></div></div>
                                <FormGrid>
                                    <Field label="Licensed vendor" value={pickupForm.vendor_name} onChange={(value) => { const vendor = suppliers.find((item) => item.company_name === value); setPickupForm((previous) => ({ ...previous, vendor_name: value, vendor_contact: vendor ? `${vendor.contact_person} · ${vendor.waste_license_number ?? vendor.phone}` : previous.vendor_contact })); }} disabled={!canEdit} select options={suppliers.filter((supplier) => supplier.waste_vendor).map((supplier) => ({ label: `${supplier.company_name} (${supplier.waste_license_number})`, value: supplier.company_name }))} />
                                    <Field label="Vendor contact / licence" value={pickupForm.vendor_contact} onChange={(value) => setPickupForm((previous) => ({ ...previous, vendor_contact: value }))} disabled={!canEdit} />
                                    <Field label="Pickup date" value={pickupForm.scheduled_date} onChange={(value) => setPickupForm((previous) => ({ ...previous, scheduled_date: value }))} disabled={!canEdit} type="date" />
                                    <Field label="Waste stream" value={pickupForm.waste_category} onChange={(value) => setPickupForm((previous) => ({ ...previous, waste_category: value }))} disabled={!canEdit} select options={['Expired medicines', 'Sharps / needles', 'Cytotoxic', 'Infectious', 'Chemical', 'General equipment'].map((value) => ({ label: value, value }))} />
                                    <Field label="Items / quantities" value={pickupForm.item_summary} onChange={(value) => setPickupForm((previous) => ({ ...previous, item_summary: value }))} disabled={!canEdit} />
                                    <Field label="Notes" value={pickupForm.notes} onChange={(value) => setPickupForm((previous) => ({ ...previous, notes: value }))} disabled={!canEdit} />
                                </FormGrid>
                                <div className="action-row"><button className="primary inline" onClick={scheduleWastePickup} disabled={!canEdit}>Schedule pickup</button></div>
                                <table className="data-table"><thead><tr><th>Pickup</th><th>Vendor / stream</th><th>Date</th><th>Status</th><th>Compliance</th></tr></thead><tbody>{wastePickups.map((pickup) => <tr key={pickup.id}><td>{pickup.pickup_number}<small className="muted"> · {pickup.item_summary}</small></td><td>{pickup.vendor_name}<small className="muted"> · {pickup.waste_category}</small></td><td>{pickup.scheduled_date}</td><td>{pickup.status}</td><td><div className="table-actions">{pickup.status === 'scheduled' && <button className="ghost" onClick={() => updateWastePickup(pickup, 'collected')} disabled={!canEdit}>Record manifest</button>}{pickup.status === 'collected' && <button className="ghost" onClick={() => updateWastePickup(pickup, 'destroyed')} disabled={!canEdit}>Add destruction certificate</button>}{pickup.manifest_number && <small>{pickup.manifest_number}</small>}{pickup.certificate_reference && <small>{pickup.certificate_reference}</small>}</div></td></tr>)}</tbody></table>
                            </div>
                        </div>
                    </section>
                )}

                {activeTab === 'dispense' && dashboardData && (
                    <section className="workspace-grid">
                        <div className="panel">
                            <div className="panel-header"><div><div className="section-title">Barcode / QR assisted issue</div><h3>Dispense using FEFO</h3></div><div className="recommendation">{canEdit ? 'Editable' : 'Read only'}</div></div>
                            <p className="muted">Scan or enter a medicine SKU (for example MED-001), batch number, or QR barcode value. The system chooses the valid batch with the earliest expiry date.</p>
                            <FormGrid>
                                <Field label="Scanned SKU or batch number" value={dispenseLookup} onChange={setDispenseLookup} disabled={!canEdit} />
                                <Field label="Quantity to issue" value={dispenseQuantity} onChange={setDispenseQuantity} disabled={!canEdit} type="number" />
                                <Field label="Department" value={dispenseDepartment} onChange={setDispenseDepartment} disabled={!canEdit} select options={departments.map((department) => ({ label: department.name, value: department.name }))} />
                                <Field label="Note (optional)" value={dispenseNote} onChange={setDispenseNote} disabled={!canEdit} />
                            </FormGrid>
                            <div className="action-row"><button className="primary inline" onClick={dispenseMedicine} disabled={!canEdit}>Dispense FEFO stock</button></div>
                        </div>
                        <div className="panel"><div className="panel-header"><div><div className="section-title">FEFO queue</div><h3>Next eligible batches</h3></div></div>
                            <table className="data-table"><thead><tr><th>Medicine</th><th>Batch / QR value</th><th>Expiry</th><th>Available</th></tr></thead><tbody>{dashboardData.batches.filter((batch) => batch.quantity > 0 && batch.disposal_status === 'active' && batch.expiry_date >= new Date().toISOString().slice(0, 10)).slice(0, 12).map((batch) => <tr key={batch.id}><td>{batch.medicine_name}</td><td>{batch.batch_number}</td><td>{batch.expiry_date}</td><td>{batch.quantity}</td></tr>)}</tbody></table>
                        </div>
                    </section>
                )}

                {activeTab === 'sales' && dashboardData && (
                    <section className="workspace-grid sales-workspace">
                        <div className="panel sales-panel">
                            <div className="panel-header"><div><div className="section-title">Pharmacy counter</div><h3>Select medicine, then complete the buyer details</h3><p className="muted">Choose an available batch below. Medicine, batch number and approved price are filled automatically.</p></div><span className="recommendation">FEFO protected</span></div>
                            <div className="sale-search"><input value={saleSearch} onChange={(event) => setSaleSearch(event.target.value)} placeholder="Search available medicine, SKU, or batch number..." /><span>{availableSaleBatches.length} batches available</span></div>
                            <div className="sale-selected-banner">
                                {selectedSaleBatch ? (
                                    <>
                                        <div>
                                            <span className="section-title">Selected for billing</span>
                                            <strong>{selectedSaleBatch.medicine_name}</strong>
                                            <small>Batch {selectedSaleBatch.batch_number} · Expires {selectedSaleBatch.expiry_date}</small>
                                        </div>
                                        <div>
                                            <strong>₹{selectedSaleBatch.unit_price.toFixed(2)}</strong>
                                            <small>{selectedSaleBatch.quantity} units available</small>
                                        </div>
                                    </>
                                ) : (
                                    <span>Select a medicine below to prefill batch number and price.</span>
                                )}
                            </div>
                            <div className="sale-catalogue">
                                {saleMedicineCards.slice(0, 16).map((entry) => (
                                    <button key={entry.medicineId} className={selectedSaleBatch?.medicine_id === entry.medicineId ? 'sale-medicine selected' : 'sale-medicine'} onClick={() => selectSaleMedicine(entry.medicineId)}>
                                        <span>
                                            <strong>{entry.medicineName}</strong>
                                            <small>{entry.batchCount} batch{entry.batchCount > 1 ? 'es' : ''} available · Next expiry {entry.nextBatch.expiry_date}</small>
                                        </span>
                                        <span>
                                            <b>{entry.availableQuantity} available in FEFO batch</b>
                                            <em>FEFO batch {entry.nextBatch.batch_number}</em>
                                        </span>
                                    </button>
                                ))}
                            </div>
                            <FormGrid>
                                <Field label="Medicine" value={selectedSaleBatch?.medicine_name ?? ''} onChange={() => { }} disabled />
                                <Field label="Selected batch number" value={saleLookup} onChange={() => { }} disabled />
                                <Field label="Unit price (₹)" value={salePrice} onChange={() => { }} type="number" disabled />
                                <Field label="Quantity" value={saleQuantity} onChange={setSaleQuantity} type="number" />
                                <Field label="Buyer name" value={buyerName} onChange={setBuyerName} />
                                <Field label="Buyer phone (optional)" value={buyerPhone} onChange={setBuyerPhone} />
                            </FormGrid>
                            <div className="action-row"><button className="primary inline" onClick={sellMedicine}>Complete sale & generate bill</button><button className="secondary inline" onClick={() => { setLatestBill(null); setSaleSearch(''); setSaleLookup(''); setSelectedSaleBatchId(null); setSalePrice('0'); }}>Clear bill</button></div>
                        </div>
                        <aside className="panel bill-preview">
                            <div className="panel-header"><div><div className="section-title">Buyer bill</div><h3>{latestBill ? latestBill.invoice_number : 'Ready to generate'}</h3></div>{latestBill && <button className="ghost" onClick={() => window.print()}>Print bill</button>}</div>
                            {latestBill ? <div className="invoice-sheet"><div className="invoice-brand">ArogyaMitra Pharmacy <span>PAID</span></div><p><strong>Buyer:</strong> {latestBill.buyer_name}<br />{latestBill.buyer_phone && <><strong>Phone:</strong> {latestBill.buyer_phone}<br /></>}<strong>Date:</strong> {new Date(latestBill.sold_at).toLocaleString()}</p><div className="invoice-line"><span>{latestBill.medicine_name}<small>{latestBill.sku} · Batch {latestBill.batch_number}</small></span><b>{latestBill.quantity} × ₹{latestBill.unit_price.toFixed(2)}</b></div><div className="invoice-total"><span>Total paid</span><strong>₹{latestBill.total_amount.toFixed(2)}</strong></div><small>Sold by {latestBill.sold_by} · Please retain this bill for your records.</small></div> : <div className="bill-empty">Complete a sale to create an itemised, printable buyer bill.</div>}
                        </aside>
                    </section>
                )}

                {activeTab === 'import' && (
                    <section className="workspace-grid single-column"><div className="panel">
                        <div className="panel-header"><div><div className="section-title">Data import</div><h3>Upload your medicine catalogue</h3></div><div className="recommendation">{canEdit ? 'Editable' : 'Read only'}</div></div>
                        <p className="muted">Upload a UTF-8 CSV. Required columns: <strong>name, sku</strong>. Optional: category, unit, reorder_level, ideal_stock, description. Existing SKUs are updated; new SKUs are created.</p>
                        <div className="action-row"><input type="file" accept=".csv,text/csv" disabled={!canEdit} onChange={(event) => setImportFile(event.target.files?.[0] ?? null)} /><button className="primary inline" onClick={uploadMedicines} disabled={!canEdit || !importFile}>Upload catalogue</button></div>
                    </div></section>
                )}

                {activeTab === 'reports' && (
                    <section className="workspace-grid single-column">
                        <div className="panel">
                            <div className="panel-header">
                                <div>
                                    <div className="section-title">Reports</div>
                                    <h3>Download inventory and alert exports</h3>
                                </div>
                            </div>
                            <div className="report-grid">
                                <button className="report-card" onClick={() => downloadFile('/reports/inventory.csv', token)}>Inventory CSV</button>
                                <button className="report-card" onClick={() => downloadFile('/reports/alerts.csv', token)}>Alerts CSV</button>
                                <button className="report-card" onClick={() => downloadFile('/reports/alerts.pdf', token)}>Alerts PDF</button>
                            </div>
                        </div>
                    </section>
                )}

                {activeTab === 'procurement' && currentUser.role === 'admin' && (
                    <section className="workspace-grid single-column">
                        <div className="panel procurement-hero">
                            <div className="panel-header"><div><div className="section-title">Automated procurement</div><h3>Safety alerts → admin review → supplier order → pro forma invoice</h3><p className="muted">A scan groups low-stock and near-expiry risks into reviewable requests. Nothing is sent to a supplier until you explicitly approve it.</p></div><button className="primary inline" onClick={scanProcurement}>Run safety scan</button></div>
                        </div>
                        <div className="procurement-list">
                            {procurementRequests.length === 0 && <div className="panel empty-procurement"><strong>No requests yet.</strong><span>Run a safety scan to prepare reviewable supplier orders from current alerts.</span></div>}
                            {procurementRequests.map((request) => (
                                <article className={`procurement-card ${request.status}`} key={request.id}>
                                    <div className="procurement-top"><div><span className="request-number">{request.request_number}</span><h3>{request.item_lines.map((line) => line.medicine_name).join(', ')}</h3><p>{request.trigger_summary}</p></div><span className={`procurement-status ${request.status}`}>{request.status === 'sent' ? 'Sent to supplier' : 'Awaiting approval'}</span></div>
                                    <div className="procurement-line"><span>{request.item_lines[0]?.quantity} units · {request.item_lines[0]?.reason}</span><strong>₹{request.estimated_total.toLocaleString()}</strong></div>
                                    <div className="procurement-footer"><span>Supplier: <button className="inline-link" onClick={() => inspectSupplier(request.supplier_name)}>{request.supplier_name}</button> · {request.supplier_email}</span>{request.status === 'sent' ? <span className="invoice-badge">{request.invoice_number} generated</span> : <button className="primary inline" onClick={() => sendProcurement(request.id)}>Approve & send order</button>}</div>
                                </article>
                            ))}
                        </div>
                    </section>
                )}

                {activeTab === 'suppliers' && dashboardData && (
                    <section className="workspace-grid single-column">
                        <div className="panel">
                            <div className="panel-header">
                                <div>
                                    <div className="section-title">Suppliers</div>
                                    <h3>Approved hospital distributors</h3>
                                </div>
                            </div>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Company</th>
                                        <th>Contact</th>
                                        <th>Phone</th>
                                        <th>GST</th>
                                        <th>Address</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {suppliers.map((supplier) => (
                                        <tr key={supplier.id}>
                                            <td><button className="inline-link" onClick={() => inspectSupplier(supplier.company_name)}>{supplier.company_name}</button></td>
                                            <td>{supplier.contact_person}</td>
                                            <td>{supplier.phone}</td>
                                            <td>{supplier.gst_number}</td>
                                            <td>{supplier.address}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>
                )}

                {activeTab === 'transactions' && dashboardData && (
                    <section className="workspace-grid single-column">
                        <div className="panel">
                            <div className="panel-header">
                                <div>
                                    <div className="section-title">Transactions</div>
                                    <h3>Purchase and issue movements</h3>
                                </div>
                            </div>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Date</th>
                                        <th>Medicine</th>
                                        <th>Type</th>
                                        <th>Qty</th>
                                        <th>Reference</th>
                                        <th>Department</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {transactions.slice(0, 40).map((transaction) => (
                                        <tr key={transaction.id}>
                                            <td>{transaction.transaction_date}</td>
                                            <td><button className="inline-link" onClick={() => inspectMedicine(transaction.medicine_id)}>{transaction.medicine_name ?? transaction.medicine_id}</button></td>
                                            <td>{transaction.transaction_type}</td>
                                            <td>{transaction.quantity}</td>
                                            <td>{transaction.reference}</td>
                                            <td>{transaction.department ?? '-'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>
                )}

                {activeTab === 'finance' && dashboardData && <section className="finance-page">
                    <div className="finance-intro"><div><div className="section-title">Cash movement</div><h3>Sales and purchases</h3><p className="muted">A clear view of money received at the counter and money committed to suppliers.</p></div><div className="finance-updated">Showing the latest {Math.max(sales.length, purchaseOrders.length)} records</div></div>
                    <section className="finance-summary">
                        <StatCard label="Sales received" value={`₹${(financials?.sales_total ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} tone="teal" />
                        <StatCard label="Purchase committed" value={`₹${(financials?.purchases_total ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} tone="gold" />
                        <StatCard label="Bills issued" value={financials?.sales_count ?? 0} tone="blue" />
                        <StatCard label="Orders placed" value={financials?.purchase_count ?? 0} tone="red" />
                    </section>
                    <section className="finance-ledgers">
                        <div className="panel finance-ledger"><div className="panel-header"><div><div className="section-title">Incoming</div><h3>Recent sales</h3></div><strong className="ledger-total">₹{(financials?.sales_total ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong></div><div className="table-scroll"><table className="data-table"><thead><tr><th>Bill</th><th>Buyer</th><th>Medicine</th><th>Qty</th><th>Amount</th><th>Sold at</th></tr></thead><tbody>{sales.length ? sales.map(sale => <tr key={sale.invoice_number}><td><strong>{sale.invoice_number}</strong></td><td>{sale.buyer_name}</td><td>{sale.medicine_name}<small className="table-subtext">{sale.sku} · Batch {sale.batch_number}</small></td><td>{sale.quantity}</td><td className="amount-positive">₹{sale.total_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td><td>{new Date(sale.sold_at).toLocaleString()}</td></tr>) : <tr><td colSpan={6} className="empty-table">No sales recorded yet.</td></tr>}</tbody></table></div></div>
                        <div className="panel finance-ledger"><div className="panel-header"><div><div className="section-title">Outgoing</div><h3>Purchase orders</h3></div><strong className="ledger-total purchase">₹{(financials?.purchases_total ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong></div><div className="table-scroll"><table className="data-table"><thead><tr><th>Order</th><th>Supplier</th><th>Date</th><th>Amount</th><th>Status</th></tr></thead><tbody>{purchaseOrders.length ? purchaseOrders.map(order => <tr key={order.id}><td><strong>{order.po_number}</strong></td><td>{order.supplier_name}</td><td>{order.order_date}</td><td className="amount-purchase">₹{order.total_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td><td><span className="status-label">{order.status}</span></td></tr>) : <tr><td colSpan={5} className="empty-table">No purchase orders recorded yet.</td></tr>}</tbody></table></div></div>
                    </section>
                </section>}

                {activeTab === 'departments' && dashboardData && <section className="workspace-grid single-column"><div className="panel"><div className="panel-header"><div><div className="section-title">Department custody</div><h3>Medicine currently held by each department</h3><p className="muted">Every dispense transfers a batch here. If an issued batch is expired, notify its original supplier and return it to the pharmacy quarantine store for collection.</p></div></div><table className="data-table"><thead><tr><th>Department</th><th>Medicine</th><th>Batch</th><th>Quantity</th><th>Last transfer</th><th>Action</th></tr></thead><tbody>{departmentInventory.length ? departmentInventory.map(item => { const batch = dashboardData.batches.find(entry => entry.batch_number === item.batch_number); const expired = batch && new Date(batch.expiry_date) < new Date(); return <tr key={item.id}><td>{item.department}</td><td>{item.medicine_name}</td><td>{item.batch_number}</td><td>{item.quantity}</td><td>{new Date(item.updated_at).toLocaleString()}</td><td>{expired && batch ? <button className="ghost" onClick={() => emailSupplierForReturn(batch)}>Email supplier</button> : 'Active stock'}</td></tr>; }) : <tr><td colSpan={6}>No department issues yet.</td></tr>}</tbody></table></div></section>}

                {activeTab === 'reference' && dashboardData && (
                    <section className="workspace-grid single-column">
                        <div className="panel storage-map-panel">
                            <div className="panel-header"><div><div className="section-title">Storage map</div><h3>Where medicines are stored</h3><p className="muted">Use the code on every batch to find its exact drawer, refrigerator, cabinet, or controlled store.</p></div></div>
                            <div className="storage-section-heading"><span>01</span><div><strong>Medicine location directory</strong><small>Search the medicine name, then follow the highlighted location code.</small></div></div>
                            <div className="medicine-directory-grid">
                                {dashboardData.batches.map((batch) => {
                                    const location = locations.find((item) => item.code === batch.location);
                                    return <article className="medicine-location-card" key={batch.id}><span className="storage-icon">{storageIcon(location?.temperature_zone ?? '', location?.name ?? '')}</span><div><span className="storage-code">{batch.location}</span><strong>{batch.medicine_name}</strong><small>Batch {batch.batch_number} · {batch.quantity} available</small><p>{location ? `${location.name} — ${location.temperature_zone}` : 'Storage location needs to be assigned'}</p></div></article>;
                                })}
                            </div>
                            <div className="storage-section-heading"><span>02</span><div><strong>Storage station guide</strong><small>Use these stations to identify drawers, refrigerators, and controlled storage.</small></div></div>
                            <div className="storage-grid">
                                {locations.map((location) => (
                                    <article key={location.id} className="storage-card">
                                        <span className="storage-icon">{storageIcon(location.temperature_zone, location.name)}</span>
                                        <div><span className="storage-code">{location.code}</span><h3>{location.name}</h3><p>{location.temperature_zone} · {location.notes || 'Follow standard pharmacy storage protocol.'}</p></div>
                                    </article>
                                ))}
                            </div>
                        </div>
                    </section>
                )}

                {activeTab === 'users' && dashboardData && (
                    <section className="workspace-grid single-column">
                        <div className="panel">
                            <div className="panel-header">
                                <div>
                                    <div className="section-title">Users & Roles</div>
                                    <h3>Access policy for the demo system</h3>
                                </div>
                            </div>
                            <div className="role-grid">
                                <RoleCard title="Admin" description="Create, update, delete, view everything, and export reports." />
                                <RoleCard title="Pharmacist" description="Manage medicines, batches, stock movements, and alerts." />
                                <RoleCard title="Viewer" description="Restricted read-only access to high-level medicine safety signals." />
                            </div>
                            {currentUser.role === 'admin' && (
                                <>
                                    <div className="panel-header"><div><div className="section-title">Account management</div><h3>{userForm.id ? 'Edit account' : 'Create account'}</h3></div></div>
                                    <FormGrid>
                                        <Field label="Username" value={userForm.username} onChange={(value) => setUserForm((previous) => ({ ...previous, username: value }))} disabled={Boolean(userForm.id)} />
                                        <Field label="Full name" value={userForm.full_name} onChange={(value) => setUserForm((previous) => ({ ...previous, full_name: value }))} />
                                        <Field label="Alert email" value={userForm.email} onChange={(value) => setUserForm((previous) => ({ ...previous, email: value }))} type="email" />
                                        <Field label="Role" value={userForm.role} onChange={(value) => setUserForm((previous) => ({ ...previous, role: value }))} select options={[{ label: 'Admin', value: 'admin' }, { label: 'Pharmacist', value: 'pharmacist' }]} />
                                        <Field label={userForm.id ? 'New password (optional)' : 'Password'} value={userForm.password} onChange={(value) => setUserForm((previous) => ({ ...previous, password: value }))} type="password" />
                                    </FormGrid>
                                    <div className="action-row"><button className="primary inline" onClick={saveUser}>{userForm.id ? 'Update user' : 'Create user'}</button><button className="secondary inline" onClick={() => setUserForm({ username: '', full_name: '', email: '', role: 'pharmacist', password: '' })}>Reset</button></div>
                                </>
                            )}
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Username</th>
                                        <th>Full Name</th>
                                        <th>Alert Email</th>
                                        <th>Role</th>
                                        {currentUser.role === 'admin' && <th>Actions</th>}
                                    </tr>
                                </thead>
                                <tbody>
                                    {(currentUser.role === 'admin' ? users : [currentUser]).map((user) => (
                                        <tr key={user.id}>
                                            <td>{user.username}</td>
                                            <td>{user.full_name}</td>
                                            <td>{user.email ?? 'Not set'}</td>
                                            <td>{displayRole(user.role)}</td>
                                            {currentUser.role === 'admin' && <td><div className="table-actions"><button className="ghost" onClick={() => setUserForm({ id: user.id, username: user.username, full_name: user.full_name, email: user.email ?? '', role: user.role, password: '' })}>Edit</button><button className="ghost danger" disabled={user.id === currentUser.id} onClick={() => deleteUser(user.id)}>Delete</button></div></td>}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>
                )}
            </main>
        </div>
    );
}

function StatCard({ label, value, tone }: { label: string; value: number | string; tone: 'blue' | 'gold' | 'teal' | 'red' }) {
    return (
        <article className={`stat-card ${tone}`}>
            <span>{label}</span>
            <strong>{typeof value === 'number' ? value.toLocaleString() : value}</strong>
        </article>
    );
}

function RoleCard({ title, description }: { title: string; description: string }) {
    return (
        <article className="role-card">
            <strong>{title}</strong>
            <p>{description}</p>
        </article>
    );
}

function ActionCard({ title, description, action, onClick }: { title: string; description: string; action: string; onClick: () => void }) {
    return <article className="role-card action-card"><strong>{title}</strong><p>{description}</p><button className="card-link" onClick={onClick}>{action} <span>→</span></button></article>;
}

function displayRole(role: string) {
    return role === 'pharmacist' ? 'Pharmacy Officer' : 'Pharmacy Administrator';
}

function storageIcon(temperatureZone: string, name: string) {
    const label = `${temperatureZone} ${name}`.toLowerCase();
    if (label.includes('cold') || label.includes('refriger') || label.includes('2-8')) return '❄';
    if (label.includes('controlled') || label.includes('lock')) return '◈';
    if (label.includes('drawer')) return '▤';
    return '▣';
}

function Field({
    label,
    value,
    onChange,
    disabled,
    type = 'text',
    textarea = false,
    select = false,
    options = [],
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    disabled?: boolean;
    type?: string;
    textarea?: boolean;
    select?: boolean;
    options?: { label: string; value: string }[];
}) {
    return (
        <label className="field">
            <span>{label}</span>
            {select ? (
                <select value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled}>
                    <option value="">Select one</option>
                    {options.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                </select>
            ) : textarea ? (
                <textarea value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} rows={3} />
            ) : (
                <input type={type} value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled || label.includes('Unit price')} />
            )}
        </label>
    );
}

function FormGrid({ children }: { children: ReactNode }) {
    return <div className="form-grid">{children}</div>;
}
