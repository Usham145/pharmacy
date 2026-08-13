import { useEffect, useMemo, useState, type ReactNode } from 'react';
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

type SmtpStatus = { configured: boolean; host: string; port: number; use_tls: boolean; username_configured: boolean; from_email: string };

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
    const [currentUser, setCurrentUser] = useState<User | null>(() => {
        const stored = localStorage.getItem(USER_KEY);
        return stored ? (JSON.parse(stored) as User) : null;
    });
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState('Ready');
    const [authUsername, setAuthUsername] = useState('admin');
    const [authPassword, setAuthPassword] = useState('admin123');
    const [selectedMedicineId, setSelectedMedicineId] = useState<number | null>(null);
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
            return;
        }
        void restoreSession();
    }, [token]);

    useEffect(() => {
        if (token) {
            if (currentUser?.role === 'platform_admin') void loadPharmacies();
            else void loadWorkspace(selectedMedicineId);
        }
    }, [token, selectedMedicineId, currentUser?.role]);

    const selectedMedicine = useMemo(
        () => dashboardData?.medicines.find((medicine) => medicine.id === selectedMedicineId) ?? null,
        [dashboardData, selectedMedicineId],
    );

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
            setCurrentUser(data.user);
            localStorage.setItem(USER_KEY, JSON.stringify(data.user));
            setStatus(`Signed in as ${data.user.full_name}`);
        } catch {
            clearSession();
        }
    }

    async function loadWorkspace(medicineId?: number | null, roleOverride?: string) {
        if (!token) {
            return;
        }
        setLoading(true);
        try {
            const role = roleOverride ?? currentUser?.role;
            const query = medicineId ? `?medicine_id=${medicineId}` : '';
            const [summary, medicines, batches, alerts, suppliersData, departmentsData, locationsData, purchaseOrdersData, transactionsData, departmentInventoryData, categoriesData, insightsData, financialSummary] = await Promise.all([
                apiRequest<Summary>('/dashboard/summary', token),
                apiRequest<Medicine[]>('/medicines', token),
                apiRequest<Batch[]>(`/batches${query}`, token),
                apiRequest<AlertItem[]>('/alerts', token),
                apiRequest<Supplier[]>('/suppliers', token),
                apiRequest<Department[]>('/departments', token),
                apiRequest<Location[]>('/locations', token),
                apiRequest<PurchaseOrder[]>('/purchase-orders', token),
                apiRequest<Transaction[]>('/transactions', token),
                apiRequest<DepartmentInventory[]>('/department-inventory', token),
                apiRequest<Category[]>('/categories', token),
                apiRequest<Insight>('/dashboard/insights', token),
                apiRequest<FinancialSummary>('/reports/financial-summary', token),
            ]);
            const forecast = medicines[0] ? await apiRequest<Forecast>(`/forecasts/${medicineId ?? medicines[0].id}`, token) : null;
            setDashboardData({ summary, medicines, batches, alerts, forecast, suppliers: suppliersData, departments: departmentsData, locations: locationsData, purchaseOrders: purchaseOrdersData, transactions: transactionsData, categories: categoriesData, insights: insightsData });
            setSuppliers(suppliersData);
            setDepartments(departmentsData);
            setLocations(locationsData);
            setPurchaseOrders(purchaseOrdersData);
            setTransactions(transactionsData);
            setDepartmentInventory(departmentInventoryData);
            setFinancials(financialSummary);
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
            if (medicineId && medicines.find((medicine) => medicine.id === medicineId)) {
                const refreshedForecast = await apiRequest<Forecast>(`/forecasts/${medicineId}`, token);
                setDashboardData((previous) => previous ? { ...previous, forecast: refreshedForecast } : previous);
            }
            setStatus('Data refreshed');
        } catch (error) {
            setStatus(error instanceof Error ? error.message : 'Failed to load workspace');
        } finally {
            setLoading(false);
        }
    }

    async function handleLogin() {
        setLoading(true);
        try {
            const data = await apiRequest<LoginResponse>('/auth/login', null, {
                method: 'POST',
                body: JSON.stringify({ username: authUsername, password: authPassword }),
            });
            setToken(data.access_token);
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
            received_on: batch.received_on,
            expiry_date: batch.expiry_date,
            location: batch.location,
        });
    }

    const availableSaleBatches = (dashboardData?.batches ?? [])
        .filter((batch) => batch.quantity > 0)
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
                availableQuantity: orderedBatches.reduce((total, batch) => total + batch.quantity, 0),
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
                                    <h3>Medicines and stock policy</h3>
                                </div>
                            </div>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>SKU</th>
                                        <th>Category</th>
                                        <th>Reorder</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {dashboardData.medicines.map((medicine) => (
                                        <tr key={medicine.id}>
                                            <td>{medicine.name}</td>
                                            <td>{medicine.sku}</td>
                                            <td>{medicine.category}</td>
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
                                            <td>{batch.medicine_name ?? batch.medicine_id}</td>
                                            <td>{batch.batch_number}</td>
                                            <td>{batch.quantity}</td>
                                            <td>{batch.expiry_date}{batch.disposal_status === 'collection_requested' && <small className="muted"> · pickup requested</small>}{batch.disposal_status === 'disposed' && <small className="muted"> · collected</small>}</td>
                                            <td>
                                                <div className="table-actions">
                                                    <button className="ghost" onClick={() => startBatchEdit(batch)} disabled={!canEdit}>Edit</button>
                                                    {new Date(batch.expiry_date) < new Date() && batch.disposal_status !== 'disposed' && batch.disposal_status !== 'collection_requested' && <button className="ghost danger" onClick={() => disposeExpiredBatch(batch)} disabled={!canEdit}>Request collection</button>}
                                                    {new Date(batch.expiry_date) < new Date() && batch.disposal_status !== 'disposed' && <button className="ghost" onClick={() => emailSupplierForReturn(batch)} disabled={!canEdit}>Email supplier</button>}
                                                    {batch.disposal_status === 'collection_requested' && <button className="ghost" onClick={() => confirmCollection(batch)} disabled={!canEdit}>Confirm collection</button>}
                                                    {new Date(batch.expiry_date) < new Date() && <button className="ghost" onClick={() => emailSupplierForReturn(batch)} disabled={!canEdit}>Email original supplier</button>}
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
                            <div className="panel-header"><div><div className="section-title">Expiry & waste control</div><h3>Prevent expiry loss and ensure safe collection</h3><p className="muted">Green: over 6 months. Yellow: 3-6 months, prioritise FEFO or ask supplier for credit. Red: under 3 months, review for return. Black: expired, quarantine and arrange signed collection.</p></div></div>
                            <table className="data-table"><thead><tr><th>Zone</th><th>Medicine</th><th>Batch</th><th>Supplier</th><th>Quantity</th><th>Expiry</th><th>Action</th></tr></thead><tbody>{dashboardData.batches.map((batch) => { const info = getExpirySnapshot(batch.expiry_date, batch.disposal_status); return <tr key={batch.id}><td>{info.expiryBand.toUpperCase()}</td><td>{batch.medicine_name ?? batch.medicine_id}</td><td>{batch.batch_number}</td><td>{batch.supplier}</td><td>{batch.quantity}</td><td>{batch.expiry_date}<small className="muted"> · {info.expiryLabel}</small></td><td><div className="table-actions">{(info.expiryBand === 'yellow' || info.expiryBand === 'red') && <button className="ghost" onClick={() => emailSupplierForExpiry(batch)} disabled={!canEdit}>Email supplier</button>}{info.expiryBand === 'black' && batch.disposal_status !== 'disposed' && <button className="ghost" onClick={() => emailSupplierForReturn(batch)} disabled={!canEdit}>Email return request</button>}{info.expiryBand === 'black' && batch.disposal_status !== 'collection_requested' && batch.disposal_status !== 'disposed' && <button className="ghost danger" onClick={() => disposeExpiredBatch(batch)} disabled={!canEdit}>Request collection</button>}{batch.disposal_status === 'collection_requested' && <button className="ghost" onClick={() => confirmCollection(batch)} disabled={!canEdit}>Confirm collection</button>}{batch.disposal_status === 'disposed' && <span>Collection recorded</span>}</div></td></tr>; })}</tbody></table>
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
                            <table className="data-table"><thead><tr><th>Medicine</th><th>Batch / QR value</th><th>Expiry</th><th>Available</th></tr></thead><tbody>{dashboardData.batches.filter((batch) => batch.quantity > 0).slice(0, 12).map((batch) => <tr key={batch.id}><td>{batch.medicine_name}</td><td>{batch.batch_number}</td><td>{batch.expiry_date}</td><td>{batch.quantity}</td></tr>)}</tbody></table>
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
                                            <b>{entry.availableQuantity} total in stock</b>
                                            <em>FEFO batch {entry.nextBatch.batch_number}</em>
                                        </span>
                                    </button>
                                ))}
                            </div>
                            <FormGrid>
                                <Field label="Medicine" value={selectedSaleBatch?.medicine_name ?? ''} onChange={() => {}} disabled />
                                <Field label="Selected batch number" value={saleLookup} onChange={() => {}} disabled />
                                <Field label="Unit price (₹)" value={salePrice} onChange={() => {}} type="number" disabled />
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
                                    <div className="procurement-footer"><span>Supplier: <strong>{request.supplier_name}</strong> · {request.supplier_email}</span>{request.status === 'sent' ? <span className="invoice-badge">{request.invoice_number} generated</span> : <button className="primary inline" onClick={() => sendProcurement(request.id)}>Approve & send order</button>}</div>
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
                                            <td>{supplier.company_name}</td>
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
                                            <td>{transaction.medicine_name ?? transaction.medicine_id}</td>
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

                {activeTab === 'finance' && dashboardData && <section className="workspace-grid"><div className="panel"><div className="section-title">Sales record</div><h3>Retail sales of this pharmacy</h3><div className="stats-grid compact-grid"><StatCard label="Sales total" value={`₹${(financials?.sales_total ?? 0).toLocaleString()}`} tone="teal" /><StatCard label="Bills generated" value={financials?.sales_count ?? 0} tone="blue" /></div><p className="muted">Every completed sale has an itemised buyer bill and is included in this total.</p></div><div className="panel"><div className="section-title">Purchase record</div><h3>Supplier orders of this pharmacy</h3><div className="stats-grid compact-grid"><StatCard label="Purchase total" value={`₹${(financials?.purchases_total ?? 0).toLocaleString()}`} tone="gold" /><StatCard label="Purchase orders" value={financials?.purchase_count ?? 0} tone="red" /></div><table className="data-table"><thead><tr><th>Order</th><th>Supplier</th><th>Date</th><th>Amount</th><th>Status</th></tr></thead><tbody>{purchaseOrders.map(order => <tr key={order.id}><td>{order.po_number}</td><td>{order.supplier_name}</td><td>{order.order_date}</td><td>₹{order.total_amount.toLocaleString()}</td><td>{order.status}</td></tr>)}</tbody></table></div></section>}

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
